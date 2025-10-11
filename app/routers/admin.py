
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_users.exceptions import UserNotExists
import json
from secrets import choice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped
from string import ascii_letters, digits
from typing import cast
from uuid import UUID

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserUpdate
from app.settings import *
from app.users import current_admin_user, get_user_manager, UserManager
from app.utility import *


templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="/admin",
    tags=["Administration"]
)


@router.post("/users", response_class=HTMLResponse)
async def create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    is_superuser: bool = Form(False),
    admin: User = Depends(current_admin_user),
    user_manager: UserManager = Depends(get_user_manager)
) -> HTMLResponse:
    """
    Creates a new user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    try:
        await user_manager.get_by_email(email)
        print("HUH")
        raise_http("This email address is already in use", status_code=409)
    except UserNotExists:
        pass

    # Create the user with a long, random, unusable password. The user will never need to know this password
    placeholder_password = "".join(choice(ascii_letters + digits) for _ in range(32))
    user_data = UserCreate(
        name=name,
        email=email.lower(),
        password=placeholder_password,
        is_active=True,
        is_superuser=is_superuser,
        is_verified=True,
    )
    user = await user_manager.create(user_data, request=request)

    # Generate a password-reset token for the new user
    await user_manager.forgot_password(user)

    events = {
        "flashMessage": "User created!"
    }
    response = templates.TemplateResponse("fragments/admin/settings_user.html", {
        "request": request,
        "user": user,
        "reset_password_link": f"{settings.MOTOTWIST_BASE_URL}/reset-password?token={user_manager.generated_token}"
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.delete("/users/{user_id}", response_class=HTMLResponse)
async def delete_user(
    request: Request,
    user_id: UUID,
    admin: User = Depends(current_admin_user),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Deletes a  user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    try:
        user = await user_manager.get(user_id)
    except UserNotExists:
        raise_http(f"User with id '{user_id}' not found", status_code=404)

    # Prevent last active admin from being deleted
    if user.is_superuser and user.is_active:
        result = await session.scalars(
            select(func.count(
                cast(Mapped[UUID], User.id)
            )).where(
                cast(Mapped[bool], User.is_active),
                cast(Mapped[bool], User.is_superuser)
            )
        )
        admin_count = result.one()

        if admin_count <= 1:
            raise_http("Cannot delete the last administrator", status_code=403)

    await user_manager.delete(user, request=request)

    events = {
        "flashMessage": "User deleted!",
    }
    response = HTMLResponse(content="")
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.post("/users/{user_id}/toggle/active", response_class=HTMLResponse)
async def toggle_user_active(
    request: Request,
    user_id: UUID,
    admin: User = Depends(current_admin_user),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Toggles the active state for a given user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    try:
        user = await user_manager.get(user_id)
    except UserNotExists:
        raise_http(f"User with id '{user_id}' not found", status_code=404)

    # Prevent last active admin from being disabled
    if user.is_superuser and user.is_active:
        result = await session.scalars(
            select(func.count(
                cast(Mapped[UUID], User.id)
            )).where(
                cast(Mapped[bool], User.is_active),
                cast(Mapped[bool], User.is_superuser)
            )
        )
        admin_count = result.one()

        if admin_count <= 1:
            raise_http("Cannot disable the last administrator", status_code=403)

    user_updates = UserUpdate()
    user_updates.is_active = not user.is_active
    await user_manager.update(user_updates, user, request=request)

    return templates.TemplateResponse("fragments/admin/settings_user.html", {
        "request": request,
        "user": user
    })


@router.post("/users/{user_id}/toggle/admin", response_class=HTMLResponse)
async def toggle_user_admin(
    request: Request,
    user_id: UUID,
    admin: User = Depends(current_admin_user),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Toggles the superuser state for a given user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)
    
    try:
        user = await user_manager.get(user_id)
    except UserNotExists:
        raise_http(f"User with id '{user_id}' not found", status_code=404)

    # Prevent last active admin from losing privileges
    if user.is_superuser:
        result = await session.scalars(
            select(func.count(
                cast(Mapped[UUID], User.id)
            )).where(
                cast(Mapped[bool], User.is_active),
                cast(Mapped[bool], User.is_superuser)
            )
        )
        admin_count = result.one()

        if admin_count <= 1:
            raise_http("Cannot remove privileges from the last administrator", status_code=403)

    user_updates = UserUpdate()
    user_updates.is_superuser = not user.is_superuser
    await user_manager.update(user_updates, user, request=request)

    return templates.TemplateResponse("fragments/admin/settings_user.html", {
        "request": request,
        "user": user
    })


@router.get("/templates/settings-modal", tags=["Templates"], response_class=HTMLResponse)
async def render_settings_modal(
    request: Request,
    admin: User = Depends(current_admin_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Returns HTMX for the admin settings
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    result = await session.scalars(
        select(User)
    )
    users = result.all()

    return templates.TemplateResponse("fragments/admin/settings_modal.html", {
        "request": request,
        "users": users
    })