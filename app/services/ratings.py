from datetime import date, timedelta
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from humanize import ordinal
from sqlalchemy import false, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper
from typing import cast, Literal

from app.models import PavedRating, Twist, UnpavedRating, User
from app.schemas.ratings import AverageRating, RatingCriterion, RatingListItem
from app.schemas.twists import TwistBasic, TwistUltraBasic


# Criteria columns
RATING_EXCLUDED_COLUMNS = {"id", "author_id", "twist_id", "rating_date"}
RATING_CRITERIA_PAVED: list[RatingCriterion] = [
    RatingCriterion(name=col.name, desc=col.doc)
    for col in cast(Mapper[PavedRating], inspect(PavedRating)).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]
RATING_CRITERIA_UNPAVED: list[RatingCriterion] = [
    RatingCriterion(name=col.name, desc=col.doc)
    for col in cast(Mapper[UnpavedRating], inspect(UnpavedRating)).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]


async def calculate_average_rating(
    session: AsyncSession,
    user: User | None,
    twist: TwistUltraBasic,
    filter: Literal["all", "own"],
    round_to: int
) -> dict[str, AverageRating]:
    """
    Calculate the average ratings for a Twist.

    :param session: The session to use for database transactions.
    :param twist_id: The id of the Twist for which to calculate average ratings.
    :param twist_is_paved: Whether or not the Twist is paved.
    :param round_to: The number of decimal places to round to.
    :return: A dictionary of each criteria and its average rating.
    """
    if twist.is_paved:
        target_model = PavedRating
        criteria_list = RATING_CRITERIA_PAVED
    else:
        target_model = UnpavedRating
        criteria_list = RATING_CRITERIA_UNPAVED
    criteria_columns = [getattr(target_model, criteria.name) for criteria in criteria_list]

    # Create a lookup dictionary for descriptions for easy access
    descriptions = {criteria.name: criteria.desc for criteria in criteria_list}

    # Query averages for target ratings columns for this twist
    statement = select(*[func.avg(col).label(col.key) for col in criteria_columns]).where(target_model.twist_id == twist.id)

    # Filtering
    if filter == "own":
        statement = statement.where(target_model.author_id == user.id) if user else statement.where(false())

    result = await session.execute(
        statement
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


templates = Jinja2Templates(directory="templates")


async def render_averages(
    request: Request,
    session: AsyncSession,
    user: User | None,
    twist: TwistUltraBasic,
    ownership: Literal["all", "own"] = "all",
) -> HTMLResponse:
    """
    Build and return the TemplateResponse for the ratings averages.
    """
    return templates.TemplateResponse("fragments/ratings/averages.html", {
        "request": request,
        "average_ratings": await calculate_average_rating(session, user, twist, ownership, round_to=1)
    })


async def render_rate_modal(
    request: Request,
    twist: TwistBasic,
    today: date
) -> HTMLResponse:
    """
    Build and return the TemplateResponse for the rate modal.
    """
    tomorrow = today + timedelta(days=1)

    return templates.TemplateResponse("fragments/ratings/rate_modal.html", {
        "request": request,
        "twist": twist,
        "today": today,
        "tomorrow": tomorrow,
        "criteria_list": RATING_CRITERIA_PAVED if twist.is_paved else RATING_CRITERIA_UNPAVED
    })


async def render_view_modal(
    request: Request,
    user: User | None,
    twist: Twist,
    ratings: list[PavedRating],
    criteria_list: list[RatingCriterion]
) -> HTMLResponse:
    """
    Build and return the TemplateResponse for the rate modal.
    """
    criteria_names = {criteria.name for criteria in criteria_list}

    # Structure data for the template
    ratings_for_template: list[RatingListItem] = []
    for rating in ratings:
        ratings_dict = {
            key: value for key, value in rating.__dict__.items()
            if key in criteria_names and isinstance(value, int)
        }
        # Pre-format the date for easier display in the template
        ordinal_day = ordinal(rating.rating_date.day)
        formatted_date = rating.rating_date.strftime(f"%B {ordinal_day}, %Y")

        # Check if the user is allowed to delete the rating
        can_delete_rating = (user.is_superuser or user.id == rating.author_id) if user else False

        ratings_for_template.append(RatingListItem(
            id=rating.id,
            author_name=rating.author.name,
            can_delete_rating=can_delete_rating,
            formatted_date=formatted_date,
            ratings=ratings_dict
        ))

    return templates.TemplateResponse("fragments/ratings/view_modal.html", {
        "request": request,
        "twist": twist,
        "ratings": ratings_for_template
    })