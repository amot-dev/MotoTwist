from pathlib import Path
from sqlalchemy import inspect

from models import PavedRating, UnpavedRating

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