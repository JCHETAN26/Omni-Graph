import json
import logging

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from .config import settings
from .models import PromptEvent
from .workflow import build_response

logger = logging.getLogger(__name__)


def create_consumer() -> KafkaConsumer | None:
    try:
        return KafkaConsumer(
            settings.prompt_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.consumer_group,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )
    except NoBrokersAvailable:
        logger.warning("Kafka broker is unavailable at %s", settings.kafka_bootstrap_servers)
        return None


def poll_forever() -> None:
    consumer = create_consumer()
    if consumer is None:
        return

    logger.info("Agent consumer started topic=%s", settings.prompt_topic)
    for message in consumer:
        event = PromptEvent.model_validate(message.value)
        response = build_response(event)
        logger.info(
            "Processed request_id=%s redactions=%s sources=%s answer=%s",
            event.request_id,
            event.redaction_count,
            len(response.sources),
            response.answer,
        )
