from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, RedisStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
import redis.asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
import uuid

from database import get_db
from models import User
from settings import settings
from schemas import UserCreate


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.MOTOTWIST_SECRET_KEY
    verification_token_secret = settings.MOTOTWIST_SECRET_KEY

    async def create(self, user_create: UserCreate, safe: bool = False, request: Request | None = None) -> User: # pyright: ignore [reportIncompatibleMethodOverride]
        # If a name isn't provided, create one from the email
        if user_create.name is None:
            user_create.name = user_create.email.partition("@")[0]

        # Call the original create method to finish the process
        created_user = await super().create(user_create, safe, request)

        return created_user


async def get_user_db(
    session: AsyncSession = Depends(get_db)
) -> AsyncGenerator[SQLAlchemyUserDatabase[User, uuid.UUID], None]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[User, uuid.UUID] = Depends(get_user_db)
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)



cookie_transport = CookieTransport(cookie_name="mototwist", cookie_max_age=3600)
redis_client = redis.asyncio.from_url(settings.REDIS_URL, decode_responses=True)  # pyright: ignore [reportUnknownMemberType]

def get_redis_strategy() -> RedisStrategy[User, uuid.UUID]:
    """Dependency to get the Redis authentication strategy."""
    return RedisStrategy(redis_client, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="cookie-auth",
    transport=cookie_transport,
    get_strategy=get_redis_strategy
)


fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
current_user_optional = fastapi_users.current_user(active=True, optional=True)