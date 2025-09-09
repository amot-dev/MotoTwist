import datetime
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import gpxpy
from pathlib import Path
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
import uuid

from database import SessionLocal, engine
from models import Twist, PavedRating, UnpavedRating

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="TODO")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

GPX_STORAGE_PATH = Path("/gpx")
GPX_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
RATING_EXCLUDED_COLUMNS = {"id", "twist_id", "rating_date"}

def get_db():
    """
    Dependency to get a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    """
    This endpoint serves the main page of the application.
    """
    twists = db.query(Twist.id, Twist.name, Twist.is_paved).order_by(Twist.name).all()

    # Get PavedRating column names and descriptions using inspection
    rating_criteria_paved = [
        {"name": col.name, "desc": col.doc}
        for col in inspect(PavedRating).columns
        if col.name not in RATING_EXCLUDED_COLUMNS
    ]

    # Get UnpavedRating column names and descriptions using inspection
    rating_criteria_unpaved = [
        {"name": col.name, "desc": col.doc}
        for col in inspect(UnpavedRating).columns
        if col.name not in RATING_EXCLUDED_COLUMNS
    ]

    flash_message = request.session.pop('flash', None)
    new_twist = request.session.pop("new_twist", None)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "twists": twists,
        "rating_critera_paved": rating_criteria_paved,
        "rating_critera_unpaved": rating_criteria_unpaved,
        "flash": flash_message,
        "new_twist": new_twist
    })

@app.post("/twists/create")
async def create_twist(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    is_paved_str: str = Form(..., alias="is_paved"),
    file: UploadFile = File(...)
):
    """
    Handles the creation of a new Twist.
    """
    is_paved = is_paved_str.lower() == "true"
    contents = await file.read()

    try:
        gpx = gpxpy.parse(contents)
        print(gpx.name)
        # Basic validation: ensure there's at least one track or route
        if not gpx.tracks and not gpx.routes:
            raise ValueError("GPX file is empty or contains no tracks/routes.")
    except Exception as e:
        # If gpxpy.parse fails or our check fails, it's not a valid GPX file
        request.session["flash"] = "Error: Invalid or empty GPX file."
        return RedirectResponse(url="/", status_code=303)

    # Generate a unique filename to prevent overwriting files
    unique_filename = f"{uuid.uuid4().hex}.gpx"
    save_path = GPX_STORAGE_PATH / unique_filename

    with open(save_path, "wb") as buffer:
        buffer.write(contents)
    
    twist = Twist(
        name=name,
        file_path=str(save_path),
        is_paved=is_paved
    )
    db.add(twist)
    db.commit()

    # Set a success flash message and redirect
    request.session["flash"] = "Twist created successfully!"
    request.session["new_twist"] = twist.id
    return RedirectResponse(url="/", status_code=303)

@app.get("/twists/{twist_id}")
async def get_twist_ratings(twist_id: int, db: Session = Depends(get_db)):
    """
    Fetches the name and is_paved for a given twist_id and returns them.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise HTTPException(status_code=404, detail="Twist not found")
    
    return {"name": twist.name, "is_paved": twist.is_paved}

@app.get("/twists/{twist_id}/gpx")
async def get_twist(twist_id: int, db: Session = Depends(get_db)):
    """
    Fetches the GPX file for a given twist_id and returns its raw content.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise HTTPException(status_code=404, detail="Twist not found")

    return FileResponse(path=twist.file_path, media_type="application/gpx+xml")

@app.post("/twists/{twist_id}/rate")
async def rate_twist(request: Request, twist_id: int, db: Session = Depends(get_db)):
    """
    Handles the creation of a new rating.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise HTTPException(status_code=404, detail="Twist not found")

    form_data = await request.form()
    target_model = PavedRating if twist.is_paved else UnpavedRating

    valid_criteria = {
        col.name for col in inspect(target_model).columns 
        if col.name not in RATING_EXCLUDED_COLUMNS
    }

    # Build the dictionary for the new rating object
    new_rating_data = {}
    for key, value in form_data.items():
        # If the key from the form is a valid rating name, add it to our dict
        if key in valid_criteria:
            try:
                # Convert rating value to an integer
                new_rating_data[key] = int(value)
            except (ValueError, TypeError):
                # Handle cases where a rating value isn't a valid number
                request.session["flash"] = f"Error: Invalid value for {key}."
                return RedirectResponse(url="/", status_code=303)

        # Handle the rating date separately
        if key == 'rating_date':
            try:
                new_rating_data['rating_date'] = datetime.date.fromisoformat(value)
            except ValueError:
                request.session["flash"] = "Error: Invalid date format."
                return RedirectResponse(url="/", status_code=303)

    # Check if we actually collected any ratings
    if not any(key in valid_criteria for key in new_rating_data):
        request.session["flash"] = "Error: No valid rating data submitted."
        return RedirectResponse(url="/", status_code=303)

    # Create the new rating instance, linking it to the twist
    new_rating = target_model(**new_rating_data, twist_id=twist_id)
    db.add(new_rating)
    db.commit()

    # Set a success flash message and redirect
    request.session["flash"] = "Twist rated successfully!"
    return RedirectResponse(url="/", status_code=303)

@app.get("/twists/{twist_id}/ratings")
async def get_twist_ratings(twist_id: int, db: Session = Depends(get_db)):
    """
    Getches the ratings for a given twist_id and returns them.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise HTTPException(status_code=404, detail="Twist not found")
    
    if twist.is_paved:
        ratings = twist.paved_ratings
        target_model = PavedRating
    else:
        ratings = twist.unpaved_ratings
        target_model = UnpavedRating
    if not ratings:
        return []
    
    # Sort ratings with most recent first
    sorted_ratings = sorted(ratings, key=lambda rating: rating.rating_date, reverse=True)

    criteria_names = {
        col.name for col in inspect(target_model).columns
        if col.name not in RATING_EXCLUDED_COLUMNS
    }

    response_list = []
    for rating in sorted_ratings:
        ratings_dict = {
            key: value for key, value in rating.__dict__.items()
            if key in criteria_names
        }
        
        response_list.append({
            "rating_date": rating.rating_date,
            "ratings": ratings_dict
        })
        
    return response_list

@app.get("/twists/{twist_id}/averages")
async def get_twist_ratings(twist_id: int, db: Session = Depends(get_db)):
    """
    Fetches the average ratings for a given twist_id and returns them.
    """
    twist = db.query(Twist).filter(Twist.id == twist_id).first()
    if not twist:
        raise HTTPException(status_code=404, detail="Twist not found")
    
    # Determine which model to inspect
    target_model = PavedRating if twist.is_paved else UnpavedRating

    # Dynamically discover all columns from the model, excluding the ones we don't want
    all_columns = inspect(target_model).columns
    target_cols = [
        col for col in all_columns
        if col.name not in RATING_EXCLUDED_COLUMNS
    ]

    # Query averages for target ratings columns for this twist
    query_expressions = [func.avg(col).label(col.key) for col in target_cols]
    averages = db.query(*query_expressions).filter(target_model.twist_id == twist_id).first()

    # Build response, excluding None values
    if averages:
        response_data = {
            key: round(value, 2)
            for key, value in averages._asdict().items()
            if value is not None
        }
    else:
        response_data = {}

    return response_data