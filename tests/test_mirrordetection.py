from cleaningstatusfilter.mirrordetection import MirrorDetector, MirrorStatus
from cleaningstatusfilter.config import MirrorDetectionConfig, ModelConfig
from visionapi.sae_pb2 import Detection, SaeMessage
from unittest.mock import MagicMock, patch

@patch('cleaningstatusfilter.mirrordetection.Model')
@patch('cleaningstatusfilter.mirrordetection.time.time')
def test_mirror_up(mock_time, mock_model):
    model = MagicMock()
    model.names = {0: 'mirror', 1: 'non-mirror'}
    mock_model.return_value = model

    testee = MirrorDetector(MirrorDetectionConfig(
        y_up_threshold=0.4,
        y_down_threshold=0.8,
        required_stable_readings=2,
        interval_s=1,
        model=ModelConfig(weights_path='')
    ))

    model.side_effect = [
        [_make_detection(0.1, 0)],
        [_make_detection(0.1, 0)],
        [_make_detection(0.1, 0)],
        [_make_detection(0.1, 0)],
    ]

    mock_time.return_value = 2000

    # First UP reading does not change status
    assert testee.detect_status(_make_sae_message()).mirror_status == MirrorStatus.UNKNOWN

    mock_time.return_value = 4000

    # Second UP reading does not change status (we need 2 stable readings to change)
    assert testee.detect_status(_make_sae_message()).mirror_status == MirrorStatus.UNKNOWN

    mock_time.return_value = 6000

    # Third UP reading changes stable status to UP
    assert testee.detect_status(_make_sae_message()).mirror_status == MirrorStatus.UP

def _make_detection(center_y: float, class_id: int) -> Detection:
    detection = Detection()
    detection.bounding_box.min_x=0.1
    detection.bounding_box.min_y=max(center_y - 0.1, 0)
    detection.bounding_box.max_x=0.2
    detection.bounding_box.max_y=min(center_y + 0.1, 1)
    detection.confidence=0.9
    detection.class_id=class_id
    return detection

def _make_sae_message() -> SaeMessage:
    sae_msg = SaeMessage()
    sae_msg.frame.shape.width = 640
    sae_msg.frame.shape.height = 480
    sae_msg.frame.shape.channels = 3
    sae_msg.frame.frame_data = b'\x00' * (640 * 480 * 3)  # Dummy data
    return sae_msg