import json
import logging


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                **{
                    key: getattr(record, key)
                    for key in ("document_id", "stage", "mode", "error_type")
                    if hasattr(record, key)
                },
            }
        )


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
