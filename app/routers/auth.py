from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi_users.authentication import RedisStrategy
from fastapi_users.exceptions import InvalidResetPasswordToken, UserInactive, UserNotExists
import json
import uuid

from app.models import User
from app.users import auth_backend, current_active_user, get_user_manager, get_redis_strategy, UserManager
from app.utility import *

templates = Jinja2Templates(directory="templates")
router = APIRouter(
    prefix="",
    tags=["Authentication"]
)

@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: RedisStrategy[User, uuid.UUID] = Depends(get_redis_strategy),
) -> HTMLResponse:
    """
    Logs a user in and updates the auth widget.
    """
    user = await user_manager.authenticate(credentials)

    # Handle failed login
    if not user:
        raise_http("Invalid email or password", status_code=401)

    events = {
        "closeModal": "",
        "flashMessage": f"Welcome back, {user.name}!"
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": user
    })

    # Create the session cookie and attach it to a response
    cookie_response = await auth_backend.login(strategy, user)

    # Copy cookie into template response
    cookie = cookie_response.headers.get("Set-Cookie")
    if cookie:
        response.headers["Set-Cookie"] = cookie

    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/logout", response_class=HTMLResponse)
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_active_user),
    strategy: RedisStrategy[User, uuid.UUID] = Depends(get_redis_strategy),
) -> HTMLResponse:
    """
    Logs a user out and updates the auth widget.
    """
    # Get the session token from the request cookie
    token = request.cookies.get("mototwist")
    if token is None:
        raise_http("No session cookie found", status_code=401)

    await auth_backend.logout(strategy, user, token)

    events = {
        "flashMessage": f"See you soon, {user.name}!"
    }
    response = templates.TemplateResponse("fragments/auth/widget.html", {
        "request": request,
        "user": None
    })
    response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


@router.get("/reset-password", response_class=HTMLResponse)
async def render_set_password_page(
    request: Request,
    token: str
):
    """
    Displays the page for a user to set their password.
    """

    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token
    })


@router.post("/reset-password", response_class=HTMLResponse)
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirmation: str = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Handles the password set form submission.
    """
    if password != password_confirmation:
        raise_http("Passwords do not match", status_code=422)

    try:
        await user_manager.reset_password(token, password, request=request)
    except (InvalidResetPasswordToken, UserInactive, UserNotExists):
        raise_http("This link is invalid or has expired", status_code=400)

    request.session["flash"] = "Password updated successfully!"
    return RedirectResponse(url="/", status_code=303)