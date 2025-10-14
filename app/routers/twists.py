from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
from sqlalchemy import delete, select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from typing import cast

from app.config import logger
from app.database import get_db
from app.models import Twist, User
from app.services.twists import get_twists_for_list, simplify_route, snap_waypoints_to_route
from app.settings import settings
from app.schemas import CoordinateDict, TwistCreate, TwistGeometryData, WaypointDict
from app.users import current_active_user, current_active_user_optional
from app.utility import raise_http


templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="/twists",
    tags=["Twists"]
)


@router.post("/", response_class=HTMLResponse)
async def create_twist(
    request: Request,
    twist_data: TwistCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Create a new Twist.
    """
    simplified_route = simplify_route(twist_data.route_geometry)
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
        author=user,
        name=twist_data.name,
        is_paved=twist_data.is_paved,
        waypoints=waypoints_for_db,
        route_geometry=geometry_for_db,
        simplification_tolerance_m=settings.TWIST_SIMPLIFICATION_TOLERANCE_M
    )
    session.add(twist)
    await session.commit()
    logger.debug(f"Created Twist '{twist}' for User '{user.id}'")

    # Render the twist list fragment with the new data
    twists = await get_twists_for_list(session, user)

    events = {
        "flashMessage": "Twist created successfully!",
        "twistAdded":  str(twist.id),
        "closeModal": ""
    }
    response = templates.TemplateResponse("fragments/twists/list.html", {
        "request": request,
        "twists": twists
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.delete("/{twist_id}", response_class=HTMLResponse)
async def delete_twist(
    request: Request,
    twist_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Delete a Twist and all related ratings.
    """

    # If not admin, check if the user authored the Twist (and can delete it)
    if not user.is_superuser:
        try:
            result = await session.scalars(
                select(Twist.author_id).where(Twist.id == twist_id)
            )
            author_id = result.one()
        except NoResultFound:
            raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
        except MultipleResultsFound:
            raise_http(f"Multiple Twists found for id '{twist_id}'", status_code=500)

        if user.id != author_id:
            raise_http("You do not have permission to delete this Twist", status_code=403)

    # Delete the Twist
    result = await session.execute(
        delete(Twist).where(Twist.id == twist_id)
    )
    if result.rowcount == 0:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)

    await session.commit()
    logger.debug(f"Deleted Twist with id '{twist_id}'")

    events = {
        "flashMessage": "Twist deleted successfully!",
        "twistDeleted":  str(twist_id),
        "closeModal": ""
    }

    # Empty response to "delete" the list item
    response = HTMLResponse(content="")
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/{twist_id}/geometry", response_class=JSONResponse)
async def get_twist_geometry(
    request: Request,
    twist_id: int,
    session: AsyncSession = Depends(get_db)
) -> TwistGeometryData:
    """
    Serve JSON containing the geometry data for a given Twist.
    """
    try:
        result = await session.execute(
            select(Twist.waypoints, Twist.route_geometry).where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple Twists found for id '{twist_id}'", status_code=500)

    return {
        "waypoints": twist.waypoints,
        "route_geometry": twist.route_geometry
    }


@router.get("/templates/list", tags=["Templates"], response_class=HTMLResponse)
async def render_list(
    request: Request,
    user: User | None = Depends(current_active_user_optional),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing the sorted list of Twists.
    """
    twists = await get_twists_for_list(session, user)

    # Set a header to trigger a client-side event after the swap
    events = {
        "twistsLoaded": ""
    }
    response = templates.TemplateResponse("fragments/twists/list.html", {
        "request": request,
        "twists": twists
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/{twist_id}/templates/delete-modal", tags=["Templates"], response_class=HTMLResponse)
async def render_delete_modal(
    request: Request,
    twist_id: int,
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing the Twist deletion confirmation modal.
    """
    try:
        result = await session.execute(
            select(Twist.id, Twist.name).where(Twist.id == twist_id)
        )
        twist = result.one()
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple Twists found for id '{twist_id}'", status_code=500)

    return templates.TemplateResponse("fragments/twists/delete_modal.html", {
        "request": request,
        "twist": twist
    })