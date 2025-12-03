import pytest

def test_rediswriter_import():
    try:
        from cleaningstatusfilter.config import CleaningStatusFilterConfig
    except ImportError as e:
        pytest.fail(f"Failed to import MyStage: {e}")

    assert CleaningStatusFilterConfig is not None, "CleaningStatusFilterConfig should be imported successfully"