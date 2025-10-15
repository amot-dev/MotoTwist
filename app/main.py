from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import json
import os
from sqlalchemy import func, select
from starlette.middleware.sessions import SessionMiddleware
import sys
from time import time
from typing import Awaitable, Callable
import uvicorn

from app.config import logger, tags_metadata
from app.database import apply_migrations, create_automigration, get_db, wait_for_db
from app.models import User
from app.routers import admin, auth, debug, ratings, twists, users
from app.schemas.users import UserCreate
from app.settings import Settings, settings
from app.users import current_active_user_optional, get_user_db, UserManager
from app.utility import raise_http, sort_schema_names, update_schema_name


@asynccontextmanager
async def lifespan(app: FastAPI):
    async for session in get_db():
        # Create initial admin user
        result = await session.execute(
            select(func.count()).select_from(User)
        )
        user_count = result.scalar_one()
        if user_count == 0:
            user_data = UserCreate(
                email=settings.MOTOTWIST_ADMIN_EMAIL,
                password=settings.MOTOTWIST_ADMIN_PASSWORD,
                is_active=True,
                is_superuser=True,
                is_verified=True,
            )
            user_db = await anext(get_user_db(session))
            user_manager = UserManager(user_db)
            await user_manager.create(user_data)
            logger.info(f"Admin user '{settings.MOTOTWIST_ADMIN_EMAIL}' created")
        else:
            logger.info("Admin user creation skipped")

    yield

    # Runs on shutdown
    logger.info("Shutting down...")


app = FastAPI(lifespan=lifespan, openapi_tags=tags_metadata)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> None:
    """
    Catches Pydantic's validation errors and returns a neat HTTPException.
    """
    raise_http("Error validating data", status_code=422, exception=exc)


@app.middleware("http")
async def log_process_time(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start_time = time()
    response = await call_next(request)
    process_time = (time() - start_time) * 1000

    logger.debug(f"Request processing took {process_time:.2f}ms")

    return response


app.add_middleware(SessionMiddleware, secret_key=settings.MOTOTWIST_SECRET_KEY)


@app.get("/", tags=["Index", "Templates"], response_class=HTMLResponse)
async def render_index_page(
    request: Request,
    user: User | None = Depends(current_active_user_optional)
) -> HTMLResponse:
    """
    Serve the main page of MotoTwist.

    :param request: FastAPI request.
    :param user: Optional logged in user.
    :return: TemplateResponse containing main page.
    """
    # Add a flash message if it exists in the session
    flash_message: str = request.session.pop("flash", None)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "flash_message": flash_message,
        "settings": settings
    })


@app.get("/latest-version", tags=["Templates"], response_class=HTMLResponse)
async def get_latest_version(request: Request) -> HTMLResponse:
    """
    Serve an HTML fragment containing the latest version from GitHub, or "Unchecked" if running a dev build.

    :param request: FastAPI request.
    :raises HTTPException: Unable to read from the GitHub API.
    :return: TemplateResponse containing version HTML fragment.
    """
    # Default version indicates a development environment
    if settings.MOTOTWIST_VERSION == Settings.model_fields["MOTOTWIST_VERSION"].default:
        return HTMLResponse(
            content="<strong title='To limit use of the GitHub API, the latest version is not checked on dev builds'>Unchecked</strong>"
        )

    url = f"https://api.github.com/repos/{settings.MOTOTWIST_UPSTREAM}/releases/latest"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses
            data = response.json()
            latest_version = data.get("tag_name")
    except httpx.HTTPStatusError as e:
        # Handle cases where the repo is not found or there are no releases
        raise_http("Could not read latest version from GitHub API",
            status_code=e.response.status_code,
            exception=e
        )

    if settings.MOTOTWIST_VERSION != latest_version:
        events = {
            "flashMessage": f"MotoTwist {latest_version} is now available!"
        }
        response = templates.TemplateResponse("fragments/new_version.html", {
            "request": request,
            "latest_version": latest_version,
            "upstream": settings.MOTOTWIST_UPSTREAM
        })
        response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
        return response
    return HTMLResponse(content=f"<strong>{latest_version}</strong>")


app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(debug.router)
app.include_router(ratings.router)
app.include_router(twists.router)
app.include_router(users.router)

update_schema_name(app, auth.login, "UserLoginForm")
update_schema_name(app, debug.load_state, "StateLoadUploadFile")
sort_schema_names(app)

if __name__ == "__main__":
    wait_for_db()

    # Check if the create-migration command was given
    if len(sys.argv) > 1 and sys.argv[1] == "create-migration":
        # Make sure a message was also provided
        if len(sys.argv) < 3:
            logger.error("create-migration requires a message")
            print("Usage: python main.py create-migration <your_message_here>", file=sys.stderr)
            sys.exit(1)

        # Get the message from the third argument
        migration_message = sys.argv[2]

        # Create migration and exit
        create_automigration(migration_message)
        sys.exit(0)

    apply_migrations()
    logger.info("Starting MotoTwist...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=(os.environ.get("UVICORN_RELOAD", "FALSE").upper() == "TRUE"),
        log_config=None # Explicitly disable Uvicorn's default logging config
    )