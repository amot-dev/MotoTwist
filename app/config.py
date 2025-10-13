import logging.config
from typing import Any

from app.settings import settings

# Configure logging
LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(level_custom)-10s %(asctime)s %(name_custom)-20s %(message)s",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": settings.LOG_LEVEL,
        "handlers": ["default"],
    },
}
logging.config.dictConfig(LOGGING_CONFIG)

# Prettify records for formatter
old_factory = logging.getLogRecordFactory()
def record_factory(*args: Any, **kwargs: Any):
    record = old_factory(*args, **kwargs)
    record.level_custom = f"[{record.levelname}]"
    record.name_custom = f"({record.name}):"
    return record
logging.setLogRecordFactory(record_factory)

# Set app logger
logger = logging.getLogger("mototwist")