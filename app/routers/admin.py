from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_users.exceptions import UserNotExists
import json
from secrets import choice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from string import ascii_letters, digits
from typing import Annotated
from uuid import UUID

from app.database import get_db
from app.models import User
from app.schemas.admin import UserCreateFormAdmin
from app.schemas.users import UserCreate, UserUpdate
from app.services.admin import is_last_active_admin
from app.settings import settings
from app.users import InvalidUsernameException, UserManager, current_admin_user, get_user_manager
from app.utility import raise_http


templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="/admin",
    tags=["Administration"]
)


@router.post("/users", response_class=HTMLResponse)
async def create_user(
    request: Request,
    user_form: Annotated[UserCreateFormAdmin, Form()],
    admin: User = Depends(current_admin_user),
    user_manager: UserManager = Depends(get_user_manager)
) -> HTMLResponse:
    """
    Create a new user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    try:
        await user_manager.get_by_email(user_form.email)
        raise_http("This email address is already in use", status_code=409)
    except UserNotExists:
        pass

    # Create the user with a long, random, unusable password. The user will never need to know this password
    placeholder_password = "".join(choice(ascii_letters + digits) for _ in range(32))
    user_data = UserCreate(
        name=user_form.name,
        email=user_form.email.lower(),
        password=placeholder_password,
        is_active=True,
        is_superuser=user_form.is_superuser,
        is_verified=True,
    )
    try:
        user = await user_manager.create(user_data, request=request)
    except InvalidUsernameException as e:
        raise_http("Invalid username", status_code=422, exception=e)

    # Generate a password-reset token for the new user
    await user_manager.forgot_password(user)

    events = {
        "flashMessage": "User created!",
        "resetForm": ""
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
    Delete a user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    try:
        user = await user_manager.get(user_id)
    except UserNotExists:
        raise_http(f"User with id '{user_id}' not found", status_code=404)

    # Prevent last active admin from being deleted
    if await is_last_active_admin(session, user):
        raise_http("Cannot delete the last active administrator", status_code=403)

    await user_manager.delete(user, request=request)

    events = {
        "flashMessage": "User deleted!",
        "authChange": ""
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
    Toggle the active state for a given user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    try:
        user = await user_manager.get(user_id)
    except UserNotExists:
        raise_http(f"User with id '{user_id}' not found", status_code=404)

    # Prevent last active admin from being disabled
    if await is_last_active_admin(session, user):
        raise_http("Cannot disable the last active administrator", status_code=403)

    user_updates = UserUpdate()
    user_updates.is_active = not user.is_active
    await user_manager.update(user_updates, user, request=request)

    events = {
        "authChange": ""
    }
    response = templates.TemplateResponse("fragments/admin/settings_user.html", {
        "request": request,
        "user": user
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.post("/users/{user_id}/toggle/admin", response_class=HTMLResponse)
async def toggle_user_admin(
    request: Request,
    user_id: UUID,
    admin: User = Depends(current_admin_user),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Toggle the superuser state for a given user.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)
    
    try:
        user = await user_manager.get(user_id)
    except UserNotExists:
        raise_http(f"User with id '{user_id}' not found", status_code=404)

    # Prevent last active admin from losing privileges
    if await is_last_active_admin(session, user):
        raise_http("Cannot remove privileges from the last active administrator", status_code=403)

    user_updates = UserUpdate()
    user_updates.is_superuser = not user.is_superuser
    await user_manager.update(user_updates, user, request=request)

    events = {
        "authChange": ""
    }
    response = templates.TemplateResponse("fragments/admin/settings_user.html", {
        "request": request,
        "user": user
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/templates/settings-modal", tags=["Templates"], response_class=HTMLResponse)
async def render_settings_modal(
    request: Request,
    admin: User = Depends(current_admin_user),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing the admin settings modal.
    """

    if not admin.is_superuser:
        raise_http("Unauthorized", status_code=401)

    result = await session.scalars(
        select(User).order_by(User.name)
    )
    users = result.all()

    return templates.TemplateResponse("fragments/admin/settings_modal.html", {
        "request": request,
        "users": users
    })