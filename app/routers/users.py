from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_users.exceptions import InvalidPasswordException, UserNotExists
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
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
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    has_changes = False

    if name and name != user.name:
        user.name = name
        has_changes = True

    if email and email.lower() != user.email:
        # Check if the new email is already taken by another user
        try:
            await user_manager.get_by_email(email)
            raise_http("This email address is already in use", status_code=409)
        except UserNotExists:
            user.email = email.lower()
            has_changes = True

    if password:
        if password != password_confirmation:
            raise_http("Passwords do not match", status_code=422)

        # Use the user_manager to validate password complexity
        try:
            await user_manager.validate_password(password, user)
        except InvalidPasswordException as e:
            raise_http("Invalid password", status_code=422, exception=e)

        # Hash the new password and update the user model
        user.hashed_password = user_manager.password_helper.hash(password)
        has_changes = True

    # Commit changes only if there were changes
    if has_changes:
        session.add(user)
        await session.commit()

    events = {
        "flashMessage": "Profile updated!"
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": user
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