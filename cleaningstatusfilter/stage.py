import logging
import signal
import threading

from prometheus_client import Counter, Histogram, start_http_server
from visionlib.pipeline import ValkeyConsumer
from visionlib.pipeline import ValkeyPublisher

from .config import CleaningStatusFilterConfig
from .cleaningstatusfilter import CleaningStatusFilter

logger = logging.getLogger(__name__)

REDIS_PUBLISH_DURATION = Histogram('cleaning_status_filter_redis_publish_duration', 'The time it takes to push a message onto the Redis stream',
                                   buckets=(0.0025, 0.005, 0.0075, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25))
FRAME_COUNTER = Counter('cleaning_status_filter_frame_counter', 'How many frames have been consumed from the Redis input stream')

def run_stage():

    stop_event = threading.Event()

    # Register signal handlers
    def sig_handler(signum, _):
        signame = signal.Signals(signum).name
        print(f'Caught signal {signame} ({signum}). Exiting...')
        stop_event.set()

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    # Load config from settings.yaml / env vars
    CONFIG = CleaningStatusFilterConfig()

    logger.setLevel(CONFIG.log_level.value)

    logger.info(f'Starting prometheus metrics endpoint on port {CONFIG.prometheus_port}')

    start_http_server(CONFIG.prometheus_port)

    logger.info(f'Starting cleaning status filter stage. Config: {CONFIG.model_dump_json(indent=2)}')

    cleaning_status_filter = CleaningStatusFilter(CONFIG)

    consumer_ctx = ValkeyConsumer(CONFIG.redis.host, CONFIG.redis.port, 
                            stream_keys=[f'{CONFIG.redis.input_stream_prefix}:{CONFIG.redis.stream_id}'])
    publisher_ctx = ValkeyPublisher(CONFIG.redis.host, CONFIG.redis.port)
    
    with consumer_ctx as iter_messages, publisher_ctx as publish:
        for stream_key, proto_data in iter_messages():
            if stop_event.is_set():
                break

            if stream_key is None:
                continue

            stream_id = stream_key.split(':')[1]

            FRAME_COUNTER.inc()

            filter_result = cleaning_status_filter.get(proto_data)

            if filter_result is None:
                continue
            
            if (payload := filter_result.forward_proto_bytes) is not None:
                with REDIS_PUBLISH_DURATION.time():
                    publish(f'{CONFIG.redis.output_stream_prefix}:{stream_id}', payload)
            
            if (payload := filter_result.detection_proto_bytes) is not None:
                publish(f'{CONFIG.redis.detection_output_stream_prefix}:{stream_id}', payload)

            
            