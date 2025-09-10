from sqlalchemy import func
from sqlalchemy.orm import Session

from config import *
from database import SessionLocal
from models import Twist, PavedRating, UnpavedRating

def get_db():
    """
    Dependency to get a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def calculate_average_rating(db: Session, twist: Twist, round_to: int) -> dict[str, float]:
    """
    Calculates the average ratings for a twist.
    """
    if twist.is_paved:
        target_model = PavedRating
        criteria_list = RATING_CRITERIA_PAVED
    else:
        target_model = UnpavedRating
        criteria_list = RATING_CRITERIA_UNPAVED
    criteria_columns = [getattr(target_model, criteria["name"]) for criteria in criteria_list]

    # Create a lookup dictionary for descriptions for easy access
    descriptions = {criteria["name"]: criteria["desc"] for criteria in criteria_list}

    # Query averages for target ratings columns for this twist
    query_expressions = [func.avg(col).label(col.key) for col in criteria_columns]
    averages = db.query(*query_expressions).filter(target_model.twist_id == twist.id).first()

    return {
        key: {
            "rating": round(value, round_to),
            "desc": descriptions.get(key, "")
        }
        for key, value in averages._asdict().items()
        if value is not None
    } if averages else {}