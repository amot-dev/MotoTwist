from asyncio import gather
from datetime import date
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from io import BytesIO
import json
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped
from typing import cast
from uuid import UUID

from app.database import get_db
from app.models import PavedRating, Twist, UnpavedRating, User
from app.users import current_admin_user


templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="/debug",
    tags=["Debug"]
)


@router.get("/", response_class=HTMLResponse)
async def render_debug_page(
    request: Request,
    admin: User = Depends(current_admin_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve the debug page with database statistics.
    """
    # Define the queries for each statistic
    user_count_query = select(func.count(
        cast(Mapped[UUID], User.id)
    ))

    admin_count_query = select(func.count(
        cast(Mapped[UUID], User.id)
    )).where(
        cast(Mapped[bool], User.is_superuser)
    )

    inactive_count_query = select(func.count(
        cast(Mapped[UUID], User.id)
    )).where(
        cast(Mapped[bool], User.is_active) == False
    )

    twist_count_query = select(func.count(Twist.id))
    paved_rating_count_query = select(func.count(PavedRating.id))
    unpaved_rating_count_query = select(func.count(UnpavedRating.id))

    # Execute all queries concurrently for better performance
    results = await gather(
        session.execute(user_count_query),
        session.execute(admin_count_query),
        session.execute(inactive_count_query),
        session.execute(twist_count_query),
        session.execute(paved_rating_count_query),
        session.execute(unpaved_rating_count_query)
    )

    # Extract the scalar value from each result
    user_count = results[0].scalar_one()
    admin_count = results[1].scalar_one()
    inactive_count = results[2].scalar_one()
    twist_count = results[3].scalar_one()
    rating_count = results[4].scalar_one()

    return templates.TemplateResponse("debug.html", {
        "request": request,
        "user_count": user_count,
        "admin_count": admin_count,
        "inactive_count": inactive_count,
        "twist_count": twist_count,
        "rating_count": rating_count
    })


@router.post("/save", response_class=StreamingResponse)
async def save_state(
    request: Request,
    admin: User = Depends(current_admin_user),
    session: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Save the entire database state to a single JSON file for download.
    """

    # Fetch all data from the database in parallel
    results = await gather(
        session.execute(select(User)),
        session.execute(select(Twist)),
        session.execute(select(PavedRating)),
        session.execute(select(UnpavedRating))
    )

    # Serialize the data using SerializationMixin methods
    db_state = {
        "users": [user.to_dict() for user in results[0].scalars().all()],
        "twists": [twist.to_dict() for twist in results[1].scalars().all()],
        "paved_ratings": [paved_rating.to_dict() for paved_rating in results[2].scalars().all()],
        "unpaved_ratings": [unpaved_rating.to_dict() for unpaved_rating in results[3].scalars().all()],
    }

    # Convert the Python dictionary to a JSON string
    json_data = json.dumps(db_state, indent=2)

    # Create a file-like object in memory to stream the response
    json_stream = BytesIO(json_data.encode("utf-8"))

    return StreamingResponse(
        content=json_stream,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=\"mototwist_debug_db.json\""
        }
    )


@router.post("/load", response_class=RedirectResponse)
async def load_state(
    request: Request,
    json_file: UploadFile = File(...),
    admin: User = Depends(current_admin_user),
    session: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """
    Wipes the current database state and loads a new state from an uploaded JSON file.
    """
    contents = await json_file.read()
    data = json.loads(contents)

    # await session.execute(delete(PavedRating))
    # await session.execute(delete(UnpavedRating))
    # await session.execute(delete(Twist))
    await session.execute(delete(User))
    
    users_data = data.get("users", [])
    twists_data = data.get("twists", [])
    paved_ratings_data = data.get("paved_ratings", [])
    unpaved_ratings_data = data.get("unpaved_ratings", [])

    # Create model instances, converting types from string back to Python objects
    users_to_create = [
        User(**{
            **user, "id": UUID(user["id"])
        }) for user in users_data
    ]
    twists_to_create = [
        Twist(**{
            **twist,
            "author_id": UUID(twist["author_id"])
        }) for twist in twists_data
    ]
    paved_ratings_to_create = [
        PavedRating(**{
            **rating,
            "author_id": UUID(rating["author_id"]),
            "rating_date": date.fromisoformat(rating["rating_date"])
        }) for rating in paved_ratings_data
    ]
    unpaved_ratings_to_create = [
        UnpavedRating(**{
            **rating,
            "author_id": UUID(rating["author_id"]),
            "rating_date": date.fromisoformat(rating["rating_date"])
        }) for rating in unpaved_ratings_data
    ]

    # Add all new objects to the session for insertion
    session.add_all(users_to_create)
    session.add_all(twists_to_create)
    session.add_all(paved_ratings_to_create)
    session.add_all(unpaved_ratings_to_create)
    await session.commit()

    request.session["flash"] = "Data loaded!"
    return RedirectResponse(url="/", status_code=303)