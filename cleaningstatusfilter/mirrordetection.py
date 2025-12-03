import logging
import time
from enum import Enum
from typing import List, NamedTuple, Optional

from google.protobuf.json_format import MessageToJson
from prometheus_client import Gauge
from visionapi.common_pb2 import MessageType
from visionapi.sae_pb2 import Detection, SaeMessage
from visionlib.pipeline.tools import get_raw_frame_data

from .config import LogLevel, MirrorDetectionConfig
from .model import Model

logger = logging.getLogger(__name__)

MIRROR_POSITION = Gauge('cleaning_status_filter_mirror_y_pos', 'The relative position of the detected mirror in the vertical image dimension')


class MirrorStatus(str, Enum):
    UP = 'UP'
    DOWN = 'DOWN'
    UNKNOWN = 'UNKNOWN'


class DetectionResult(NamedTuple):
    mirror_status: MirrorStatus
    inference_result: Optional[SaeMessage]


class MirrorDetector:
    def __init__(self, config: MirrorDetectionConfig, log_level: LogLevel = LogLevel.INFO):
        logger.setLevel(log_level.value)
        self._config = config

        self._stable_readings_counter = 0
        self._previous_status = MirrorStatus.UNKNOWN
        self._current_stable_status = MirrorStatus.UNKNOWN
        self._previous_inference_time = 0

        self._model = Model(config.model, log_level)

    def detect_status(self, sae_msg: SaeMessage) -> DetectionResult:
        current_time = time.time()

        # Return established status if inference interval has not expired
        if current_time - self._previous_inference_time < self._config.interval_s:
            return DetectionResult(self._current_stable_status, None)

        frame_data = get_raw_frame_data(sae_msg.frame)
        if frame_data is None:
            logger.warning(f'Message has no valid frame data: {MessageToJson(sae_msg)}')
            return DetectionResult(MirrorStatus.UNKNOWN, None)

        self._previous_inference_time = current_time

        # Run image through detection model
        inference_start = time.time_ns()
        detections = self._model(frame_data)
        inference_time_us = (time.time_ns() - inference_start) // 1000

        # Determine stable status
        new_status = self._get_status_from_inference_result(detections)
        logger.debug(f'Current mirror position is {new_status}')

        if new_status != self._previous_status:
            self._stable_readings_counter = 0
        else:
            self._stable_readings_counter += 1
        
        if self._stable_readings_counter >= self._config.required_stable_readings and self._current_stable_status != new_status:
            self._current_stable_status = new_status
            self._stable_readings_counter = 0
            logger.debug(f'Mirror position changed status to {new_status}')

        self._previous_status = new_status

        # Create message
        mirror_msg = SaeMessage()
        mirror_msg.frame.CopyFrom(sae_msg.frame)
        mirror_msg.type = MessageType.SAE
        mirror_msg.metrics.detection_inference_time_us = inference_time_us
        for class_id, class_name in self._model.names.items():
            mirror_msg.model_metadata.class_names[class_id] = class_name
        mirror_msg.detections.extend(detections)

        return DetectionResult(self._current_stable_status, mirror_msg)
    
    def _get_status_from_inference_result(self, detections: List[Detection]) -> MirrorStatus:
        # We cannot make any assumption about the status if no mirror or multiple mirrors are detected
        if len(detections) == 0 or len(detections) > 1:
            return MirrorStatus.UNKNOWN
        
        # There is exactly one mirror -> check if the class is indeed 'mirror'
        det = detections[0]
        if self._model.names[det.class_id] != 'mirror':
            return MirrorStatus.UNKNOWN
        
        # We have a mirror -> check its position against the configured thresholds
        # Keep in mind that y counts from the top of the image (i.e. image top row is y=0)
        mirror_center_y = (det.bounding_box.min_y + det.bounding_box.max_y) / 2
        logger.debug(f'mirror_center_y: {mirror_center_y}')
        MIRROR_POSITION.set(mirror_center_y)
        if mirror_center_y > self._config.y_down_threshold:
            return MirrorStatus.DOWN
        
        if mirror_center_y < self._config.y_up_threshold:
            return MirrorStatus.UP
        
        # The position is in the undefined space inbetween thresholds
        return MirrorStatus.UNKNOWN
        



