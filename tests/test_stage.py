from unittest.mock import patch

from visionapi.sae_pb2 import Detection, SaeMessage

from cleaningstatusfilter.config import (CleaningStatusFilterConfig,
                                         MirrorDetectionConfig, RedisConfig)
from cleaningstatusfilter.stage import run_stage


@patch('cleaningstatusfilter.mirrordetection.Model')
@patch('cleaningstatusfilter.mirrordetection.time.time')
@patch('cleaningstatusfilter.stage.CleaningStatusFilterConfig')
@patch('cleaningstatusfilter.stage.RedisConsumer')
@patch('cleaningstatusfilter.stage.RedisPublisher')
def test_smoke(mock_redis_publisher, mock_redis_consumer, mock_config, mock_time, mock_model):
    mock_config.return_value = CleaningStatusFilterConfig(
        log_level='WARNING',
        mirror_detection=MirrorDetectionConfig(
            y_up_threshold=0.4,
            y_down_threshold=0.8,
            required_stable_readings=2,
            interval_s=1,
            model={'weights_path': ''}
        ),
        redis=RedisConfig(
            output_stream_prefix='forward_output',
            detection_output_stream_prefix='mirror_det_output'
        )
    )

    # Make sure that every input message is visually checked (see the interval_s config parameter above)
    def iter_time():
        current_time = 2000
        while True:
            yield current_time
            current_time += 2000

    mock_time.side_effect = iter_time()

    publisher_mock = mock_redis_publisher.return_value 
    
    mock_redis_consumer.return_value.return_value.__iter__.return_value = iter([
        ('videosource:stream1', _make_sae_msg_bytes(1)),
        ('videosource:stream1', _make_sae_msg_bytes(2)),
        ('videosource:stream1', _make_sae_msg_bytes(3)),
    ])

    model = mock_model.return_value
    model.names = {0: 'mirror', 1: 'non-mirror'}

    model.side_effect = [
        [_make_detection(0.9, 0)],
        [_make_detection(0.9, 0)],
        [_make_detection(0.9, 0)],
    ]

    run_stage()

    # Assert that one SAE message was forwarded and all mirror detections were output into the separate stream
    assert [call.args[0] for call in publisher_mock.call_args_list] == [
        'mirror_det_output:stream1',
        'mirror_det_output:stream1',
        'forward_output:stream1',
        'mirror_det_output:stream1',
    ]

    # Assert that the third message was forwarded
    msg = SaeMessage()
    msg.ParseFromString(publisher_mock.call_args_list[2].args[1])
    assert msg.frame.timestamp_utc_ms == 3


def _make_detection(center_y: float, class_id: int) -> Detection:
    detection = Detection()
    detection.bounding_box.min_x=0.1
    detection.bounding_box.min_y=max(center_y - 0.1, 0)
    detection.bounding_box.max_x=0.2
    detection.bounding_box.max_y=min(center_y + 0.1, 1)
    detection.confidence=0.9
    detection.class_id=class_id
    return detection

def _make_sae_msg_bytes(timestamp: int):
    sae_msg = SaeMessage()
    sae_msg.frame.timestamp_utc_ms = timestamp
    sae_msg.frame.shape.width = 5
    sae_msg.frame.shape.height = 5
    sae_msg.frame.shape.channels = 1
    sae_msg.frame.frame_data = b'\x00' * (5 * 5 * 1)  # Dummy data
    return sae_msg.SerializeToString()