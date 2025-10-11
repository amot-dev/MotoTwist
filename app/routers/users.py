from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_users.exceptions import InvalidPasswordException, UserNotExists
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import logger
from app.database import get_db
from app.models import User
from app.schemas import UserUpdate
from app.settings import *
from app.users import current_active_user, get_user_manager, UserManager
from app.utility import *


templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="/users",
    tags=["User Management"]
)


@router.put("/", response_class=HTMLResponse)
async def update_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str | None = Form(None),
    password_confirmation: str | None = Form(None),
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
) -> HTMLResponse:
    user_updates = UserUpdate()

    if name and name != user.name:
        logger.debug(f"Changing name for {user.id} from {user.name} to {name}")
        user_updates.name = name

    if email and email.lower() != user.email:
        # Check if the new email is already taken by another user
        try:
            await user_manager.get_by_email(email)
            raise_http("This email address is already in use", status_code=409)
        except UserNotExists:
            logger.debug(f"Changing email for {user.id} from {user.email} to {email.lower()}")
            user_updates.email = email.lower()

    if password:
        if password != password_confirmation:
            raise_http("Passwords do not match", status_code=422)
        logger.debug(f"Changing password for {user.id}")
        user_updates.password = password

    # Commit changes only if there were changes
    if user_updates.model_dump(exclude_unset=True):
        try:
            await user_manager.update(user_updates, user, request=request)
        except InvalidPasswordException as e:
            raise_http("Invalid password", status_code=422, exception=e)

    events = {
        "flashMessage": "Profile updated!",
        "updateProfileModal": ""
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": user
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.delete("/", response_class=HTMLResponse)
async def delete_user(
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
) -> HTMLResponse:
    await user_manager.delete(user, request=request)

    events = {
        "flashMessage": "Account deleted!",
        "closeModal": ""
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": None
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.post("/deactivate", response_class=HTMLResponse)
async def deactivate_user(
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
) -> HTMLResponse:
    await user_manager.update(UserUpdate(is_active=False), user, request=request)

    events = {
        "flashMessage": "Account deactivated!",
        "closeModal": ""
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": None
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/templates/profile-modal", tags=["Templates"], response_class=HTMLResponse)
async def render_profile_modal(request: Request, user: User = Depends(current_active_user), session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """
    Returns HTMX for the current user's profile
    """

    return templates.TemplateResponse("fragments/users/profile_modal.html", {
        "request": request,
        "user": user
    })