from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from humanize import ordinal
import json
from sqlalchemy import delete, func, select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.config import logger
from app.database import get_db
from app.models import Twist, PavedRating, UnpavedRating, User
from app.services.ratings import calculate_average_rating, RATING_CRITERIA_PAVED, RATING_CRITERIA_UNPAVED
from app.schemas import RatingListItem
from app.users import current_active_user, current_active_user_optional
from app.utility import is_form_value_string, raise_http


templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="/twists/{twist_id}/ratings",
    tags=["Ratings"]
)


@router.post("/", response_class=HTMLResponse)
async def create_rating(
    request: Request,
    twist_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Create a new rating for the given Twist.
    """
    try:
        result = await session.execute(
            select(
                Twist.is_paved,
                Twist.author_id,
                User.name.label("author_name")
            )
            .join(Twist.author)
            .where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    logger.debug(f"Attempting to rate Twist with id '{twist_id}'")
    form_data = await request.form()

    if twist.is_paved:
        Rating = PavedRating
        criteria_list = RATING_CRITERIA_PAVED
    else:
        Rating = UnpavedRating
        criteria_list = RATING_CRITERIA_UNPAVED
    valid_criteria = {criteria["name"] for criteria in criteria_list}

    # Build the dictionary for the new rating object
    new_rating_data: dict[str, date | int] = {}
    for key, value in form_data.items():
        if not is_form_value_string(value):
            raise_http(f"Invalid value for '{key.replace("_", " ").title()}' criterion", status_code=422)

        # If the key from the form is a valid rating name, add it to the dict
        if key in valid_criteria:
            try:
                new_rating_data[key] = int(value)
            except (ValueError, TypeError) as e:
                # Handle cases where a rating value isn't a valid number
                raise_http(f"Invalid value for '{key.replace("_", " ").title()}' criterion", status_code=422, exception=e)

        # Handle the rating date separately
        if key == "rating_date":
            try:
                new_rating_data["rating_date"] = date.fromisoformat(value)
            except ValueError as e:
                raise_http("Invalid date format", status_code=422, exception=e)

    # Check if we actually collected any ratings
    if not any(key in valid_criteria for key in new_rating_data):
        raise_http("No valid rating data submitted", status_code=422)

    # Create the new rating instance, linking it to the twist
    new_rating = Rating(**new_rating_data, author=user, twist_id=twist_id)
    session.add(new_rating)
    await session.commit()
    logger.debug(f"Created rating '{new_rating}'")

    # Set a header to trigger a client-side event after the swap, passing a message
    events = {
        "flashMessage": "Twist rated successfully!",
        "closeModal": ""
    }
    response = templates.TemplateResponse("fragments/ratings/dropdown.html", {
        "request": request,
        "twist_id": twist_id,
        "twist_author_name": twist.author_name,
        "can_delete": user.id == twist.author_id,
        "average_ratings": await calculate_average_rating(session, twist_id, twist.is_paved, round_to=1)
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.delete("/{rating_id}", response_class=HTMLResponse)
async def delete_rating(
    request: Request,
    twist_id: int,
    rating_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Delete a rating from the given Twist.
    """
    try:
        result = await session.scalars(
            select(Twist.is_paved).where(Twist.id == twist_id)
        )
        twist_is_paved = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    Rating = PavedRating if twist_is_paved else UnpavedRating

    if not user.is_superuser:
        try:
            result = await session.scalars(
                select(Rating.author_id).where(Rating.id == rating_id)
            )
            author_id = result.one()
        except NoResultFound:
            raise_http(f"Rating with id '{rating_id}' not found for Twist with id '{twist_id}'", status_code=404)
        except MultipleResultsFound:
            raise_http(f"Multiple Ratings with id '{rating_id}' found for Twist with id '{twist_id}'", status_code=500)

        if user.id != author_id:
            raise_http("You do not have permission to delete this Rating", status_code=403)

    # Delete the Rating
    result = await session.execute(
        delete(Rating).where(Rating.id == rating_id, Rating.twist_id == twist_id)
    )
    if result.rowcount == 0:
        raise_http(f"Rating with id '{rating_id}' not found for Twist with id '{twist_id}'", status_code=404)

    await session.commit()
    logger.debug(f"Deleted rating with id '{rating_id}' from Twist with id '{twist_id}'")

    # Empty response to "delete" the card
    result = await session.execute(
        select(func.count()).select_from(Rating).where(Rating.twist_id == twist_id)
    )
    remaining_ratings_count = result.scalar_one()
    if remaining_ratings_count > 0:
        response = HTMLResponse(content="")
    else:
        response = HTMLResponse(content="<p>No ratings yet</p>")

    # Set a header to trigger a client-side event after the swap, passing a message
    events = {
        "flashMessage": "Rating removed successfully!"
    }
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/templates/dropdown", tags=["Templates"], response_class=HTMLResponse)
async def render_dropdown(
    request: Request,
    twist_id: int,
    user: User | None = Depends(current_active_user_optional),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing a dropdown with the average ratings for a given Twist.
    """
    try:
        result = await session.execute(
            select(
                Twist.is_paved,
                Twist.author_id,
                User.name.label("author_name")
            )
            .join(Twist.author)
            .where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    return templates.TemplateResponse("fragments/ratings/dropdown.html", {
        "request": request,
        "twist_id": twist_id,
        "twist_author_name": twist.author_name,
        "can_delete": user.id == twist.author_id if user else False,
        "average_ratings": await calculate_average_rating(session, twist_id, twist.is_paved, round_to=1)
    })


@router.get("/templates/rate-modal", tags=["Templates"], response_class=HTMLResponse)
async def render_rate_modal(
    request: Request,
    twist_id: int,
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing a modal to rate a given Twist.
    """
    try:
        result = await session.execute(
            select(Twist.id, Twist.name, Twist.is_paved).where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    today = date.today()
    tomorrow = today + timedelta(days=1)

    return templates.TemplateResponse("fragments/ratings/rate_modal.html", {
        "request": request,
        "twist": twist,
        "today": today,
        "tomorrow": tomorrow,
        "criteria_list": RATING_CRITERIA_PAVED if twist.is_paved else RATING_CRITERIA_UNPAVED
    })


@router.get("/templates/view-modal", tags=["Templates"], response_class=HTMLResponse)
async def render_view_modal(
    request: Request,
    twist_id: int,
    user: User | None = Depends(current_active_user_optional),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing a modal to view the ratings for a given Twist.
    """
    try:
        result = await session.scalars(
            select(Twist).where(Twist.id == twist_id).options(
                load_only(Twist.name, Twist.is_paved),
                selectinload(Twist.paved_ratings)
                        .selectinload(PavedRating.author)
                        .load_only(User.name),
                selectinload(Twist.unpaved_ratings)
                    .selectinload(UnpavedRating.author)
                    .load_only(User.name)
            )
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    if twist.is_paved:
        ratings = twist.paved_ratings
        criteria_list = RATING_CRITERIA_PAVED
    else:
        ratings = twist.unpaved_ratings
        criteria_list = RATING_CRITERIA_UNPAVED
    criteria_names = {criteria["name"] for criteria in criteria_list}

    # Sort ratings with most recent first
    sorted_ratings = sorted(ratings, key=lambda r: r.rating_date, reverse=True) if ratings else []

    # Structure data for the template
    ratings_for_template: list[RatingListItem] = []
    for rating in sorted_ratings:
        ratings_dict = {
            key: value for key, value in rating.__dict__.items()
            if key in criteria_names and isinstance(value, int)
        }
        # Pre-format the date for easier display in the template
        ordinal_day = ordinal(rating.rating_date.day)
        formatted_date = rating.rating_date.strftime(f"%B {ordinal_day}, %Y")

        ratings_for_template.append({
            "id": rating.id,
            "author_name": rating.author.name,
            "can_delete": user.id == rating.author_id if user else False,
            "formatted_date": formatted_date,
            "ratings": ratings_dict
        })

    # Pass the request, twist, and ratings to the template
    return templates.TemplateResponse("fragments/ratings/view_modal.html", {
        "request": request,
        "twist": twist,
        "ratings": ratings_for_template
    })