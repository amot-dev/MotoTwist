from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
import json
from sqlalchemy import delete, select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.config import logger
from app.database import get_db
from app.models import Twist, User
from app.schemas.twists import TwistBasic, TwistCreateForm, TwistDropdown, TwistFilterParams, TwistGeometry
from app.services.twists import render_delete_modal, render_list, render_single_list_item, render_twist_dropdown, simplify_route, snap_waypoints_to_route
from app.settings import settings
from app.users import current_active_user, current_active_user_optional
from app.utility import raise_http


router = APIRouter(
    prefix="/twists",
    tags=["Twists"]
)


@router.post("/", response_class=HTMLResponse)
async def create_twist(
    request: Request,
    twist_data: TwistCreateForm,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Create a new Twist.
    """
    # Process route and waypoints
    simplified_route = simplify_route(twist_data.route_geometry)
    snapped_waypoints = snap_waypoints_to_route(twist_data.waypoints, simplified_route)

    # Create the new Twist
    twist_dict = twist_data.model_dump()
    twist_dict.update({
        "author": user,
        "waypoints": snapped_waypoints,
        "route_geometry": simplified_route,
        "simplification_tolerance_m": settings.TWIST_SIMPLIFICATION_TOLERANCE_M
    })
    twist = Twist(**twist_dict)
    session.add(twist)
    await session.commit()
    logger.debug(f"Created Twist '{twist}' for User '{user.id}'")

    # Render the twist list fragment with the new data
    events = {
        "flashMessage": "Twist created successfully!",
        "twistAdded":  str(twist.id),
        "closeModal": ""
    }
    response = await render_single_list_item(request, session, user, twist.id)
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

    # Empty response to "delete" the list item
    events = {
        "flashMessage": "Twist deleted successfully!",
        "twistDeleted":  str(twist_id),
        "closeModal": ""
    }
    response = HTMLResponse(content="")
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/{twist_id}/geometry", response_class=JSONResponse)
async def get_twist_geometry(
    request: Request,
    twist_id: int,
    session: AsyncSession = Depends(get_db)
) -> TwistGeometry:
    """
    Serve JSON containing the geometry data for a given Twist.
    """
    try:
        result = await session.execute(
            select(*TwistGeometry.fields).where(Twist.id == twist_id)
        )
        twist_geometry = TwistGeometry.model_validate(result.one())
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple Twists found for id '{twist_id}'", status_code=500)

    return twist_geometry


@router.get("/templates/list", tags=["Templates"], response_class=HTMLResponse)
async def serve_list(
    request: Request,
    search: str | None = Query(None),
    ownership: Literal["own", "all"] = Query("all"),
    rated: Literal["rated", "unrated", "all"] = Query("all"),
    visibility: Literal["visible", "hidden", "all"] = Query("all"),
    visible_ids: list[int] | None = Query(None),
    user: User | None = Depends(current_active_user_optional),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing the sorted list of Twists.
    """
    # Unfortunately, Pydantic doesn't play nicely with visible_ids being a list when used as a Dependency
    filter = TwistFilterParams(
        search=search,
        ownership=ownership,
        rated=rated,
        visibility=visibility,
        visible_ids=visible_ids
    )

    events = {
        "twistsLoaded": ""
    }
    response = response = await render_list(request, session, user, filter)
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/{twist_id}/templates/dropdown", tags=["Templates"], response_class=HTMLResponse)
async def serve_dropdown(
    request: Request,
    twist_id: int,
    user: User | None = Depends(current_active_user_optional),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing the Twist dropdown for a given Twist.
    """
    try:
        result = await session.execute(
            select(*TwistDropdown.fields)
            .join(Twist.author)
            .where(Twist.id == twist_id)
        )
        twist = TwistDropdown.model_validate(result.one())
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple twists found for id '{twist_id}'", status_code=500)

    return await render_twist_dropdown(request, session, user, twist)


@router.get("/{twist_id}/templates/delete-modal", tags=["Templates"], response_class=HTMLResponse)
async def serve_delete_modal(
    request: Request,
    twist_id: int,
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing the Twist deletion confirmation modal.
    """
    try:
        result = await session.execute(
            select(*TwistBasic.fields).where(Twist.id == twist_id)
        )
        twist = TwistBasic.model_validate(result.one())
    except NoResultFound:
        raise_http(f"Twist with id '{twist_id}' not found", status_code=404)
    except MultipleResultsFound:
        raise_http(f"Multiple Twists found for id '{twist_id}'", status_code=500)

    return await render_delete_modal(request, twist)