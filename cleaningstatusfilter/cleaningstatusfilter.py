import logging
from typing import List, NamedTuple, Optional

from prometheus_client import Histogram, Summary
from shapely import Point, Polygon
from shapely.geometry import shape
from visionapi.sae_pb2 import SaeMessage

from .config import CleaningStatusFilterConfig
from .mirrordetection import MirrorDetector, MirrorStatus

logging.basicConfig(format='%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(message)s')
logger = logging.getLogger(__name__)

GET_DURATION = Histogram('cleaning_status_filter_get_duration', 'The time it takes to deserialize the proto until returning the tranformed result as a serialized proto',
                         buckets=(0.0025, 0.005, 0.0075, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25))
PROTO_SERIALIZATION_DURATION = Summary('cleaning_status_filter_proto_serialization_duration', 'The time it takes to create a serialized output proto')
PROTO_DESERIALIZATION_DURATION = Summary('cleaning_status_filter_proto_deserialization_duration', 'The time it takes to deserialize an input proto')


class FilterResult(NamedTuple):
    forward_proto_bytes: Optional[bytes]
    detection_proto_bytes: Optional[bytes]


class CleaningStatusFilter:
    def __init__(self, config: CleaningStatusFilterConfig) -> None:
        self._config = config
        logger.setLevel(self._config.log_level.value)

        self._mirror_detector = MirrorDetector(config.mirror_detection, config.log_level)
        self._no_cleaning_areas: List[Polygon] = [shape(area) for area in config.no_cleaning_areas]

    def __call__(self, input_proto) -> FilterResult:
        return self.get(input_proto)
    
    @GET_DURATION.time()
    def get(self, input_proto) -> FilterResult:
        sae_msg = self._unpack_proto(input_proto)
        # If we are in a configured no cleaning area, do not forward anything
        if self._in_no_cleaning_area(sae_msg):
            return FilterResult(None, None)        

        # Check visual mirror status
        result = self._mirror_detector.detect_status(sae_msg)

        # We only forward the original message if the cleaning equipment is deployed, i.e. in the down position
        forward_message = None
        if result.mirror_status == MirrorStatus.DOWN:
            forward_message = input_proto

        return FilterResult(forward_message, self._pack_proto(result.inference_result))
        
    @PROTO_DESERIALIZATION_DURATION.time()
    def _unpack_proto(self, sae_message_bytes):
        sae_msg = SaeMessage()
        sae_msg.ParseFromString(sae_message_bytes)

        return sae_msg
    
    def _in_no_cleaning_area(self, sae_msg: SaeMessage) -> bool:
        if not sae_msg.frame.HasField('camera_location'):
            return False
        
        cam_loc = sae_msg.frame.camera_location
        point = Point(cam_loc.longitude, cam_loc.latitude)
        
        return any([area.contains(point) for area in self._no_cleaning_areas])
    
    @PROTO_SERIALIZATION_DURATION.time()
    def _pack_proto(self, sae_msg: Optional[SaeMessage]):
        return sae_msg.SerializeToString() if sae_msg is not None else None