import json
import logging

from shared.logging_config import JsonFormatter


def test_json_formatter_keeps_structured_context() -> None:
    record = logging.LogRecord(
        name="etl.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="table_completed",
        args=(),
        exc_info=None,
    )
    record.run_id = "run-123"
    record.rows_out = 42

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "table_completed"
    assert payload["run_id"] == "run-123"
    assert payload["rows_out"] == 42
