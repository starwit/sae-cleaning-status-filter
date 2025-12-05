from typing import Dict, List
from unittest.mock import patch
import pytest

from visionapi.sae_pb2 import Detection, SaeMessage

from cleaningstatusfilter.config import (CleaningStatusFilterConfig,
                                         MirrorDetectionConfig, RedisConfig)
from cleaningstatusfilter.stage import run_stage

@pytest.fixture(autouse=True)
def disable_prometheus():
    # We don't want to start the Prometheus server during tests
    with patch('cleaningstatusfilter.stage.start_http_server'):
        yield

@pytest.fixture
def set_config():
    with patch('cleaningstatusfilter.stage.CleaningStatusFilterConfig') as mock_config:
        def _set_config(mirror_det: MirrorDetectionConfig):
            mock_config.return_value = CleaningStatusFilterConfig(
                log_level='WARNING',
                mirror_detection=mirror_det,
                redis=RedisConfig(
                    stream_id='stream1',
                    output_stream_prefix='forward_output',
                    detection_output_stream_prefix='mirror_det_output'
                ),
            )
        yield _set_config

@pytest.fixture
def publisher_mock():
    with patch('cleaningstatusfilter.stage.ValkeyPublisher') as mock_publisher:
        yield mock_publisher.return_value.__enter__.return_value

@pytest.fixture
def inject_consumer_messages():
    with patch('cleaningstatusfilter.stage.ValkeyConsumer') as mock_consumer:
        def _inject_messages(messages):
            mock_consumer.return_value.__enter__.return_value.return_value.__iter__.return_value = iter(messages)
        yield _inject_messages

@pytest.fixture
def config_mock_model():
    with patch('cleaningstatusfilter.mirrordetection.Model') as mock_model:
        def _config_mock_model(names: Dict[int, str], detection_results: List[Detection]):
            mock_model.return_value.names = names
            mock_model.return_value.side_effect = detection_results
        yield _config_mock_model

@pytest.fixture
def set_time_readings():
    with patch('cleaningstatusfilter.mirrordetection.time.time') as mock_time:
        def _set_time_readings(readings: List[float]):
            mock_time.side_effect = readings
        yield _set_time_readings


def test_smoke(set_config, publisher_mock, inject_consumer_messages, config_mock_model, set_time_readings):
    set_config(MirrorDetectionConfig(
        y_up_threshold=0.4,
        y_down_threshold=0.8,
        required_stable_readings=2,
        interval_s=1,
        model={'weights_path': ''}
    ))

    set_time_readings([
        2000,
        4000,
        6000,
    ])

    # Mock three messages for the component to read from redis
    inject_consumer_messages([
        ('videosource:stream1', _make_sae_msg_bytes(1)),
        ('videosource:stream1', _make_sae_msg_bytes(2)),
        ('videosource:stream1', _make_sae_msg_bytes(3)),
    ])

    config_mock_model(
        names={0: 'mirror', 1: 'non-mirror'},
        detection_results=[
            [_make_detection(0.9, 0)],
            [_make_detection(0.9, 0)],
            [_make_detection(0.9, 0)],
        ]
    )

    run_stage()

    # Assert that one SAE message was forwarded and all mirror detections were output into the separate mirror detection stream
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