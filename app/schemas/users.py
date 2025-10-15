from fastapi_users import schemas
from uuid import UUID


class UserRead(schemas.BaseUser[UUID]):
    name: str
    pass

class UserCreate(schemas.BaseUserCreate):
    name: str | None = None
    pass

class UserUpdate(schemas.BaseUserUpdate):
    name: str | None = None
    pass