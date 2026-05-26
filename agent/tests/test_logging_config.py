import json
import logging

from app.config import settings
from app.logging_config import JsonFormatter, configure_logging


def test_json_formatter_emits_single_line_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.request_id = "abc-123"
    record.path = "structured"
    line = formatter.format(record)
    assert "\n" not in line
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "abc-123"
    assert payload["path"] == "structured"


def test_configure_logging_text_mode_uses_plain_formatter(monkeypatch):
    monkeypatch.setattr(settings, "log_format", "text")
    configure_logging()
    handler = logging.getLogger().handlers[0]
    assert not isinstance(handler.formatter, JsonFormatter)


def test_configure_logging_json_mode_uses_json_formatter(monkeypatch):
    monkeypatch.setattr(settings, "log_format", "json")
    configure_logging()
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler.formatter, JsonFormatter)
