from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi_users.exceptions import InvalidPasswordException, UserNotExists
import json
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.config import logger
from app.database import get_db
from app.models import User
from app.schemas.users import UserCreate, UserCreateForm, UserUpdate, UserUpdateForm
from app.services.admin import is_last_active_admin
from app.users import current_active_user, get_user_manager, InvalidUsernameException, UserManager
from app.utility import raise_http


templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post("", response_class=Response)
async def create_user(
    request: Request,
    user_form: Annotated[UserCreateForm, Form()],
    user_manager: UserManager = Depends(get_user_manager)
) -> Response:
    """
    Create a new user. Self-serve.
    """
    try:
        await user_manager.get_by_email(user_form.email)
        raise_http("This email address is already in use", status_code=409)
    except UserNotExists:
        pass

    if user_form.password != user_form.password_confirmation:
        raise_http("Passwords do not match", status_code=422)

    user_data = UserCreate(
        name=user_form.name,
        email=user_form.email.lower(),
        password=user_form.password,
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )

    try:
        await user_manager.create(user_data, request=request)
    except InvalidUsernameException as e:
        raise_http("Invalid username", status_code=422, exception=e)
    except InvalidPasswordException as e:
        raise_http("Invalid password", status_code=422, exception=e)

    request.session["flash"] = "User created!"
    return Response(headers={"HX-Redirect": "/"})


@router.put("", response_class=HTMLResponse)
async def update_user(
    request: Request,
    user_form: Annotated[UserUpdateForm, Form()],
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager)
) -> HTMLResponse:
    """
    Update the current user. Self-serve.
    """
    user_updates = UserUpdate()

    if user_form.name and user_form.name != user.name:
        logger.debug(f"Changing name for {user.id} from {user.name} to {user_form.name}")
        user_updates.name = user_form.name

    if user_form.email and user_form.email.lower() != user.email:
        # Check if the new email is already taken by another user
        try:
            await user_manager.get_by_email(user_form.email)
            raise_http("This email address is already in use", status_code=409)
        except UserNotExists:
            logger.debug(f"Changing email for {user.id} from {user.email} to {user_form.email.lower()}")
            user_updates.email = user_form.email.lower()

    if user_form.password != user_form.password_confirmation:
        raise_http("Passwords do not match", status_code=422)

    if user_form.password:
        logger.debug(f"Changing password for {user.id}")
        user_updates.password = user_form.password

    # Commit changes only if there were changes
    if user_updates.model_dump(exclude_unset=True):
        try:
            await user_manager.update(user_updates, user, request=request)
            flash_message = "Profile updated!"
        except InvalidUsernameException as e:
            raise_http("Invalid username", status_code=422, exception=e)
        except InvalidPasswordException as e:
            raise_http("Invalid password", status_code=422, exception=e)
    else:
        flash_message = "No changes made"

    events = {
        "flashMessage": flash_message,
        "updateProfileModal": ""
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": user
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.delete("", response_class=HTMLResponse)
async def delete_user(
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Delete the current user. Self-serve.
    """
    # Prevent last active admin from being deleted
    if await is_last_active_admin(session, user):
        raise_http("Cannot delete the last active administrator", status_code=403)

    await user_manager.delete(user, request=request)

    events = {
        "flashMessage": "Account deleted!",
        "authChange": "",
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
    session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Deactivate the current user. Self-serve.
    """
    # Prevent last active admin from being disabled
    if await is_last_active_admin(session, user):
        raise_http("Cannot disable the last active administrator", status_code=403)

    await user_manager.update(UserUpdate(is_active=False), user, request=request)

    events = {
        "flashMessage": "Account deactivated!",
        "authChange": "",
        "closeModal": ""
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": None
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/templates/profile-modal", tags=["Templates"], response_class=HTMLResponse)
async def render_profile_modal(
    request: Request,
    user: User = Depends(current_active_user)
) -> HTMLResponse:
    """
    Serve an HTML fragment containing the current user's profile modal.
    """

    events = {
        "profileLoaded": ""
    }
    response = templates.TemplateResponse("fragments/users/profile_modal.html", {
        "request": request,
        "user": user
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response