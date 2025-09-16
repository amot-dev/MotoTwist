from datetime import date, timedelta
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from humanize import ordinal
import json
import os
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
import uuid
import uvicorn

from config import *
from database import apply_migrations, wait_for_db
from models import Twist, PavedRating, UnpavedRating
from schemas import TwistCreate
from utility import *

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="TODO")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Catches Pydantic's validation errors and returns a neat HTTPException.
    """
    raise_http("Error validating data", status_code=422, exception=exc)

@app.get("/", response_class=HTMLResponse)
async def render_index(request: Request, db: Session = Depends(get_db)):
    """
    This endpoint serves the main page of the application.
    """

    flash_message = request.session.pop('flash', None)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "flash": flash_message
    })

@app.post("/twist", response_class=HTMLResponse)
async def create_twist(
    request: Request,
    twist_data: TwistCreate,
    db: Session = Depends(get_db)
):
    """
    Handles the creation of a new Twist.
    """
    snapped_waypoints = snap_waypoints_to_route(twist_data.waypoints, twist_data.route_geometry)

    # Convert Pydantic model lists to dictionary lists before saving to JSONB columns
    waypoints_for_db = [wp.model_dump() for wp in snapped_waypoints]
    geometry_for_db = [coord.model_dump() for coord in twist_data.route_geometry]

    twist = Twist(
        name=twist_data.name,
        is_paved=twist_data.is_paved,
        waypoints=waypoints_for_db,
        route_geometry=geometry_for_db
    )
    db.add(twist)
    db.commit()
    logger.debug(f"Created twist with id '{twist.id}'")

    # Render the twist list fragment with the new data
    twists = db.query(Twist.id, Twist.name, Twist.is_paved).order_by(Twist.name).all()

    events = {
        "twistAdded":  str(twist.id),
        "flashMessage": "Twist created successfully!"
    }
    response = templates.TemplateResponse("fragments/twist_list.html", {
        "request": request,
        "twists": twists
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response

@app.delete("/twists/{twist_id}", response_class=HTMLResponse)
async def delete_twist(request: Request, twist_id: int, db: Session = Depends(get_db)):
    """
    Deletes a twist and all related ratings.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)

    logger.debug(f"Attempting to delete twist '{twist.name}'")

    twist_id = twist.id
    db.delete(twist)
    db.commit()

    logger.debug(f"Deleted twist with id '{twist_id}'")

    # Render the twist list fragment with the new data
    twists = db.query(Twist.id, Twist.name, Twist.is_paved).order_by(Twist.name).all()

    events = {
        "twistDeleted":  str(twist_id),
        "flashMessage": "Twist deleted successfully!"
    }

    # Empty response to "delete" the list item
    response = HTMLResponse(content="")
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response

@app.get("/twists/{twist_id}/geometry", response_class=JSONResponse)
async def get_twist_data(twist_id: int, db: Session = Depends(get_db)):
    """
    Fetches the geometry data for a given twist_id and returns it as JSON.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)

    return {
        "waypoints": twist.waypoints,
        "route_geometry": twist.route_geometry
    }

@app.post("/twists/{twist_id}/rate", response_class=HTMLResponse)
async def rate_twist(request: Request, twist_id: int, db: Session = Depends(get_db)):
    """
    Handles the creation of a new rating.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)
    logger.debug(f"Attempting to rate twist '{twist.name}'")

    form_data = await request.form()

    if twist.is_paved:
        Rating = PavedRating
        criteria_list = RATING_CRITERIA_PAVED
        paved_str = "paved"
    else:
        Rating = UnpavedRating
        criteria_list = RATING_CRITERIA_UNPAVED
        paved_str = "unpaved"
    valid_criteria = {criteria["name"] for criteria in criteria_list}

    # Build the dictionary for the new rating object
    new_rating_data = {}
    for key, value in form_data.items():
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
        raise_http("No valid rating data submitted", status_code=422, exception=e)

    # Create the new rating instance, linking it to the twist
    new_rating = Rating(**new_rating_data, twist_id=twist_id)
    db.add(new_rating)
    db.commit()
    logger.debug(f"Created {paved_str} rating with id '{new_rating.id}'")

    # Set a header to trigger a client-side event after the swap, passing a message
    events = {
        "flashMessage": "Twist rated successfully!"
    }
    response = templates.TemplateResponse("fragments/rating_dropdown.html", {
        "request": request,
        "twist_id": twist_id,
        "average_ratings": await calculate_average_rating(db, twist, round_to=1)
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response

@app.delete("/twists/{twist_id}/ratings/{rating_id}")
async def delete_twist_rating(request: Request, twist_id: int, rating_id: int, db: Session = Depends(get_db)):
    """
    Deletes a twist rating.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)

    if twist.is_paved:
        Rating = PavedRating
        paved_str = "paved"
    else:
        Rating = UnpavedRating
        paved_str = "unpaved"

    # Delete the rating
    logger.debug(f"Attempting to delete {paved_str} rating '{rating_id}' from twist '{twist.name}'")
    delete_count = db.query(Rating).filter(Rating.id == rating_id, Rating.twist_id == twist_id).delete(synchronize_session=False)

    # Undo the empty transaction if nothing was deleted
    if delete_count == 0:
        db.rollback()
        raise_http("Rating not found for this twist", status_code=404)
    db.commit()

    # Empty response to "delete" the card
    remaining_ratings_count = db.query(Rating).filter(Rating.twist_id == twist_id).count()
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
async def render_twist_list(request: Request, db: Session = Depends(get_db)):
    """
    Returns an HTML fragment containing the sorted list of twists.
    """
    twists = db.query(Twist.id, Twist.name, Twist.is_paved).order_by(Twist.name).all()

    # Set a header to trigger a client-side event after the swap
    events = {
        "twistsLoaded": {}
    }
    response = templates.TemplateResponse("fragments/twist_list.html", {
        "request": request,
        "twists": twists
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response

@app.get("/rating-dropdown/{twist_id}", response_class=HTMLResponse)
async def render_rating_dropdown(request: Request, twist_id: int, db: Session = Depends(get_db)):
    """
    Gets the average ratings for a twist and returns an HTML fragment for the HTMX-powered dropdown.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)

    return templates.TemplateResponse("fragments/rating_dropdown.html", {
        "request": request,
        "twist_id": twist_id,
        "average_ratings": await calculate_average_rating(db, twist, round_to=1)
    })

@app.get("/modal-rate-twist/{twist_id}", response_class=HTMLResponse)
async def render_modal_rate_twist(request: Request, twist_id: int, db: Session = Depends(get_db)):
    """
    Gets the details for a twist and returns an HTML form fragment for the HTMX-powered modal.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)

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
async def render_modal_view_twist_ratings(twist_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Gets the ratings for a twist and returns an HTML fragment for the HTMX-powered modal.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)

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
    ratings_for_template = []
    for rating in sorted_ratings:
        ratings_dict = {
            key: value for key, value in rating.__dict__.items()
            if key in criteria_names
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
async def render_modal_delete_twist(request: Request, twist_id: int, db: Session = Depends(get_db)):
    """
    Returns an HTML fragment for the twist deletion confirmation modal.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise_http("Twist not found", status_code=404)

    return templates.TemplateResponse("fragments/modal_delete_twist.html", {
        "request": request,
        "twist": twist
    })


if __name__ == "__main__":
    wait_for_db()
    apply_migrations()
    logger.info("Starting MotoTwist...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(os.environ.get("UVICORN_RELOAD", "FALSE").upper() == "TRUE"),
        log_config=None # Explicitly disable Uvicorn's default logging config
    )