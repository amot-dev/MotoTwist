from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper
from typing import cast

from app.models import PavedRating, UnpavedRating
from app.schemas import AverageRating, RatingCriterion
from app.utility import *


# Criteria columns
RATING_EXCLUDED_COLUMNS = {"id", "author_id", "twist_id", "rating_date"}
RATING_CRITERIA_PAVED: list[RatingCriterion] = [
    {"name": col.name, "desc": col.doc}
    for col in cast(Mapper[PavedRating], inspect(PavedRating)).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]
RATING_CRITERIA_UNPAVED: list[RatingCriterion] = [
    {"name": col.name, "desc": col.doc}
    for col in cast(Mapper[UnpavedRating], inspect(UnpavedRating)).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]


async def calculate_average_rating(session: AsyncSession, twist_id: int, twist_is_paved: bool, round_to: int) -> dict[str, AverageRating]:
    """
    Calculate the average ratings for a Twist.

    :param session: The session to use for database transactions.
    :param twist_id: The id of the Twist for which to calculate average ratings.
    :param twist_is_paved: Whether or not the Twist is paved.
    :param round_to: The number of decimal places to round to.
    :return: A dictionary of each criteria and its average rating.
    """
    if twist_is_paved:
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
    result = await session.execute(
        select(*query_expressions).where(target_model.twist_id == twist_id)
    )
    averages = result.first()

    return {
        key: cast(AverageRating, {
            "rating": round(value, round_to),
            "desc": descriptions.get(key, "")
        })
        for key, value in averages._asdict().items()  # pyright: ignore [reportPrivateUsage]
        if value is not None
    } if averages else {}