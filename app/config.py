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

# Twist simplification tolerance
def calculate_tolerance_from_m(tolerance_m_str: str) -> int | None:
    try:
        tolerance_m = int(tolerance_m_str.strip().rstrip("mM"))
        return tolerance_m
    except Exception:
        logger.exception(f"Invalid value '{tolerance_m_str}' in TWIST_SIMPLIFICATION_TOLERANCE_M")
TWIST_SIMPLIFICATION_TOLERANCE_M=calculate_tolerance_from_m(os.environ.get("TWIST_SIMPLIFICATION_TOLERANCE_M", "0"))

# OSM and OSRM
OSM_URL = os.environ.get("OSM_URL", "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")

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