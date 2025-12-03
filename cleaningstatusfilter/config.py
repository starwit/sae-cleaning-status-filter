from pathlib import Path
from typing import Annotated, List, Self

from geojson_pydantic import Polygon
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated
from visionlib.pipeline.settings import LogLevel, YamlConfigSettingsSource


class ModelConfig(BaseModel):
    weights_path: Path
    device: str = 'cpu'
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    fp16: bool = False
    nms_agnostic: bool = True
    inference_size: tuple[int, int] = (640, 640)


class RedisConfig(BaseModel):
    host: str = 'localhost'
    port: Annotated[int, Field(ge=1, le=65536)] = 6379
    stream_id: str = 'stream1'
    input_stream_prefix: str = 'videosource'
    output_stream_prefix: str = 'cleaningstatusfilter'
    detection_output_stream_prefix: str = 'cleaningstatusfilterdetection'


class MirrorDetectionConfig(BaseModel):
    y_up_threshold: Annotated[float, Field(ge=0, le=1)]
    y_down_threshold: Annotated[float, Field(ge=0, le=1)]
    required_stable_readings: Annotated[int, Field(ge=1)] = 5
    interval_s: Annotated[float, Field(gt=0)] = 1
    model: ModelConfig

    @model_validator(mode='after')
    def check_thresholds(self) -> Self:
        if self.y_up_threshold > self.y_down_threshold:
            raise ValueError('`y_up_threshold` needs to be smaller than or equal to `y_down_threshold` (y is anchored at the image top)')
        return self


class CleaningStatusFilterConfig(BaseSettings):
    log_level: LogLevel = LogLevel.WARNING
    mirror_detection: MirrorDetectionConfig
    no_cleaning_areas: List[Polygon] = []
    redis: RedisConfig = RedisConfig()
    prometheus_port: Annotated[int, Field(ge=1024, le=65536)] = 8000

    model_config = SettingsConfigDict(env_nested_delimiter='__')

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls), file_secret_settings)