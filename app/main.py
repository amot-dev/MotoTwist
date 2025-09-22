from contextlib import asynccontextmanager
from datetime import date, timedelta
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_users.authentication import RedisStrategy
import httpx
from humanize import ordinal
import json
import os
from sqlalchemy import delete, func, select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload
import sys
from time import time
from typing import Awaitable, Callable
import uuid
import uvicorn

from config import logger
from database import apply_migrations, create_automigration, get_db, wait_for_db
from models import Twist, PavedRating, UnpavedRating, User
from settings import *
from schemas import CoordinateDict, RatingListItem, TwistCreate, TwistGeometryData, UserCreate, WaypointDict
from users import auth_backend, current_active_user, current_user_optional, get_user_db, get_user_manager, get_redis_strategy, UserManager
from utility import *


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create initial admin user
    async for session in get_db():
        result = await session.execute(
            select(func.count()).select_from(User)
        )
        user_count = result.scalar_one()
        if user_count == 0:
            user_data = UserCreate(
                email=settings.MOTOTWIST_ADMIN_EMAIL,
                password=settings.MOTOTWIST_ADMIN_PASSWORD,
                is_active=True,
                is_superuser=True,
                is_verified=True,
            )
            user_db = await anext(get_user_db(session))
            user_manager = UserManager(user_db)
            await user_manager.create(user_data)
            logger.info(f"Admin user '{settings.MOTOTWIST_ADMIN_EMAIL}' created")
        else:
            logger.info("Admin user creation skipped")

    yield

    # Runs on shutdown
    logger.info("Shutting down...")


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> None:
    """
    Catches Pydantic's validation errors and returns a neat HTTPException.
    """
    raise_http("Error validating data", status_code=422, exception=exc)


@app.middleware("http")
async def log_process_time(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    start_time = time()
    response = await call_next(request)
    process_time = (time() - start_time) * 1000

    logger.debug(f"Request processing took {process_time:.2f}ms")

    return response


@app.get("/", response_class=HTMLResponse)
async def render_index(request: Request, user: User | None = Depends(current_user_optional)) -> HTMLResponse:
    """
    Serves the main page of the application.
    """
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": settings.MOTOTWIST_VERSION,
        "upstream": settings.MOTOTWIST_UPSTREAM,
        "user": user,
        "osm_url": settings.OSM_URL,
        "osrm_url": settings.OSRM_URL
    })


@app.get("/latest-version", response_class=HTMLResponse)
async def get_latest_version(request: Request) -> HTMLResponse:
    """
    Get the latest version from GitHub and return an HTML fragment.
    """
    # Default version indicates a development environment
    if settings.MOTOTWIST_VERSION == Settings.model_fields["MOTOTWIST_VERSION"].default:
        return HTMLResponse(
            content="<strong title='To limit use of the GitHub API, the latest version is not checked on dev builds'>Unchecked</strong>"
        )

    url = f"https://api.github.com/repos/{settings.MOTOTWIST_UPSTREAM}/releases/latest"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses
            data = response.json()
            latest_version = data.get("tag_name")
    except httpx.HTTPStatusError as e:
        # Handle cases where the repo is not found or there are no releases
        raise_http("Could not read latest version from GitHub API",
            status_code=e.response.status_code,
            exception=e
        )

    if settings.MOTOTWIST_VERSION != latest_version:
        events = {
            "flashMessage": f"MotoTwist {latest_version} is now available!"
        }
        response = templates.TemplateResponse("fragments/new_version.html", {
            "request": request,
            "latest_version": latest_version,
            "upstream": settings.MOTOTWIST_UPSTREAM
        })
        response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
        return response
    return HTMLResponse(content=f"<strong>{latest_version}</strong>")


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: RedisStrategy[User, uuid.UUID] = Depends(get_redis_strategy),
) -> HTMLResponse:
    """
    Logs a user in and updates the auth widget.
    """
    user = await user_manager.authenticate(credentials)

    # Handle failed login
    if not user:
        raise_http("Invalid email or password", status_code=401)

    events = {
        "closeModal": "",
        "flashMessage": f"Welcome back, {user.name}!"
    }
    response = templates.TemplateResponse("fragments/auth_widget.html", {
        "request": request,
        "user": user
    })

    # Create the session cookie and attach it to a response
    cookie_response = await auth_backend.login(strategy, user)

    # Copy cookie into template response
    cookie = cookie_response.headers.get("Set-Cookie")
    if cookie:
        response.headers["Set-Cookie"] = cookie

    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@app.get("/logout", response_class=HTMLResponse)
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_active_user),
    strategy: RedisStrategy[User, uuid.UUID] = Depends(get_redis_strategy),
) -> HTMLResponse:
    """
    Logs a user out and updates the auth widget.
    """
    # Get the session token from the request cookie
    token = request.cookies.get("mototwist")
    if token is None:
        raise_http("No session cookie found", status_code=401)

    await auth_backend.logout(strategy, user, token)

    events = {
        "flashMessage": f"See you soon, {user.name}!"
    }
    response = templates.TemplateResponse("fragments/auth_widget.html", {
        "request": request,
        "user": None
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@app.post("/twist", response_class=HTMLResponse)
async def create_twist(
    request: Request,
    twist_data: TwistCreate,
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Handles the creation of a new Twist.
    """
    simplified_route, tolerance = simplify_route(twist_data.route_geometry)
    snapped_waypoints = snap_waypoints_to_route(twist_data.waypoints, simplified_route)

    # Convert Pydantic model lists to dictionary lists before saving to JSONB columns
    waypoints_for_db = [
        cast(WaypointDict, wp.model_dump())
        for wp in snapped_waypoints
    ]
    geometry_for_db = [
        cast(CoordinateDict, coord.model_dump())
        for coord in simplified_route
    ]

    # Create the new Twist
    twist = Twist(
        name=twist_data.name,
        is_paved=twist_data.is_paved,
        waypoints=waypoints_for_db,
        route_geometry=geometry_for_db,
        simplification_tolerance_m=tolerance
    )
    session.add(twist)
    await session.commit()
    logger.debug(f"Created Twist '{twist}'")

    # Render the twist list fragment with the new data
    results = await session.execute(
        select(Twist.id, Twist.name, Twist.is_paved).order_by(Twist.name)
    )
    twists = results.all()

    events = {
        "twistAdded":  str(twist.id),
        "closeModal": "",
        "flashMessage": "Twist created successfully!"
    }
    response = templates.TemplateResponse("fragments/twist_list.html", {
        "request": request,
        "twists": twists
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@app.delete("/twists/{twist_id}", response_class=HTMLResponse)
async def delete_twist(request: Request, twist_id: int, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Deletes a twist and all related ratings.
    """
    result = await session.execute(
        delete(Twist).where(Twist.id == twist_id)
    )
    if result.rowcount == 0:
        raise_http("Twist not found", status_code=404)

    await session.commit()
    logger.debug(f"Deleted Twist with id '{twist_id}'")

    events = {
        "twistDeleted":  str(twist_id),
        "closeModal": "",
        "flashMessage": "Twist deleted successfully!"
    }

    # Empty response to "delete" the list item
    response = HTMLResponse(content="")
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@app.get("/twists/{twist_id}/geometry", response_class=JSONResponse)
async def get_twist_data(request: Request, twist_id: int, session: AsyncSession = Depends(get_db)) -> TwistGeometryData:
    """
    Fetches the geometry data for a given twist_id and returns it as JSON.
    """
    try:
        result = await session.execute(
            select(Twist.waypoints, Twist.route_geometry).where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    return {
        "waypoints": twist.waypoints,
        "route_geometry": twist.route_geometry
    }


@app.post("/twists/{twist_id}/rate", response_class=HTMLResponse)
async def rate_twist(request: Request, twist_id: int, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Handles the creation of a new rating.
    """
    try:
        result = await session.scalars(
            select(Twist).where(Twist.id == twist_id).options(
                load_only(Twist.id, Twist.name, Twist.is_paved)
            )
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    logger.debug(f"Attempting to rate Twist '{twist}'")
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
    new_rating = Rating(**new_rating_data, twist_id=twist_id)
    session.add(new_rating)
    await session.commit()
    logger.debug(f"Created rating '{new_rating}'")

    # Set a header to trigger a client-side event after the swap, passing a message
    events = {
        "closeModal": "",
        "flashMessage": "Twist rated successfully!"
    }
    response = templates.TemplateResponse("fragments/rating_dropdown.html", {
        "request": request,
        "twist_id": twist_id,
        "average_ratings": await calculate_average_rating(session, twist.id, twist.is_paved, round_to=1)
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@app.delete("/twists/{twist_id}/ratings/{rating_id}", response_class=HTMLResponse)
async def delete_twist_rating(request: Request, twist_id: int, rating_id: int, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Deletes a twist rating.
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

    result = await session.execute(
        delete(Rating).where(Rating.id == rating_id, Rating.twist_id == twist_id)
    )
    if result.rowcount == 0:
        raise_http("Rating with id '{rating_id}' not found for Twist with id '{twist_id}'", status_code=404)

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


@app.get("/twist-list", response_class=HTMLResponse)
async def render_twist_list(request: Request, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Returns an HTML fragment containing the sorted list of twists.
    """
    results = await session.execute(
        select(Twist.id, Twist.name, Twist.is_paved).order_by(Twist.name)
    )
    twists = results.all()

    # Set a header to trigger a client-side event after the swap
    events = {
        "twistsLoaded": ""
    }
    response = templates.TemplateResponse("fragments/twist_list.html", {
        "request": request,
        "twists": twists
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@app.get("/rating-dropdown/{twist_id}", response_class=HTMLResponse)
async def render_rating_dropdown(request: Request, twist_id: int, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Gets the average ratings for a twist and returns an HTML fragment for the HTMX-powered dropdown.
    """
    try:
        result = await session.execute(
            select(Twist.id, Twist.is_paved).where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    return templates.TemplateResponse("fragments/rating_dropdown.html", {
        "request": request,
        "twist_id": twist_id,
        "average_ratings": await calculate_average_rating(session, twist.id, twist.is_paved, round_to=1)
    })


@app.get("/modal-rate-twist/{twist_id}", response_class=HTMLResponse)
async def render_modal_rate_twist(request: Request, twist_id: int, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Gets the details for a twist and returns an HTML form fragment for the HTMX-powered modal.
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

    return templates.TemplateResponse("fragments/modal_rate_twist.html", {
        "request": request,
        "twist": twist,
        "today": today,
        "tomorrow": tomorrow,
        "criteria_list": RATING_CRITERIA_PAVED if twist.is_paved else RATING_CRITERIA_UNPAVED
    })


@app.get("/modal-view-twist-ratings/{twist_id}", response_class=HTMLResponse)
async def render_modal_view_twist_ratings(twist_id: int, request: Request, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Gets the ratings for a twist and returns an HTML fragment for the HTMX-powered modal.
    """
    try:
        result = await session.scalars(
            select(Twist).where(Twist.id == twist_id).options(
                load_only(Twist.name, Twist.is_paved).
                selectinload(Twist.paved_ratings),
                selectinload(Twist.unpaved_ratings)
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
            "formatted_date": formatted_date,
            "ratings": ratings_dict
        })

    # Pass the request, twist, and ratings to the template
    return templates.TemplateResponse("fragments/modal_view_twist_ratings.html", {
        "request": request,
        "twist": twist,
        "ratings": ratings_for_template
    })


@app.get("/modal-delete-twist/{twist_id}", response_class=HTMLResponse)
async def render_modal_delete_twist(request: Request, twist_id: int, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Returns an HTML fragment for the twist deletion confirmation modal.
    """
    try:
        result = await session.execute(
            select(Twist.id, Twist.name).where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    return templates.TemplateResponse("fragments/modal_delete_twist.html", {
        "request": request,
        "twist": twist
    })


if __name__ == "__main__":
    wait_for_db()

    # Check if the create-migration command was given
    if len(sys.argv) > 1 and sys.argv[1] == "create-migration":
        # Make sure a message was also provided
        if len(sys.argv) < 3:
            logger.error("create-migration requires a message")
            print("Usage: python main.py create-migration <your_message_here>", file=sys.stderr)
            sys.exit(1)

        # Get the message from the third argument
        migration_message = sys.argv[2]

        # Create migration and exit
        create_automigration(migration_message)
        sys.exit(0)

    apply_migrations()
    logger.info("Starting MotoTwist...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(os.environ.get("UVICORN_RELOAD", "FALSE").upper() == "TRUE"),
        log_config=None # Explicitly disable Uvicorn's default logging config
    )