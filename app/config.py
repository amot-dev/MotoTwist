import logging.config
import os
from pathlib import Path
from sqlalchemy import inspect

from models import PavedRating, UnpavedRating

# Configure logging
LOGGING_CONFIG = {
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
        "level": os.environ.get("LOG_LEVEL", "INFO").upper(),
        "handlers": ["default"],
    },
}
logging.config.dictConfig(LOGGING_CONFIG)

# Prettify records for formatter
old_factory = logging.getLogRecordFactory()
def record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    record.level_custom = "[{}]".format(record.levelname)
    record.name_custom = "({}):".format(record.name)
    return record
logging.setLogRecordFactory(record_factory)

# Set app logger
logger = logging.getLogger("mototwist")

# GPX storage path (don't change unless you know what you're doing)
GPX_STORAGE_PATH = Path("/gpx")
GPX_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# Criteria columns
RATING_EXCLUDED_COLUMNS = {"id", "twist_id", "rating_date"}
RATING_CRITERIA_PAVED = [
    {"name": col.name, "desc": col.doc}
    for col in inspect(PavedRating).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]
RATING_CRITERIA_UNPAVED = [
    {"name": col.name, "desc": col.doc}
    for col in inspect(UnpavedRating).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]