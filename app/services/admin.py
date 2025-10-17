
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped
from typing import cast
from uuid import UUID

from app.models import User


async def is_last_active_admin(session: AsyncSession, user: User) -> bool:
    """
    Check if the given user is the last active administrator.

    :param session: The session to use for database transactions.
    :param user_id: The user to check.
    :return: True if the user is the last active admin.
    """
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
        return admin_count <= 1
    return False