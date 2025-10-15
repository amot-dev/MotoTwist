from fastapi_users import schemas
from pydantic import BaseModel
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


class UserCreateForm(BaseModel):
    name: str
    email: str
    password: str
    password_confirmation: str


class UserUpdateForm(BaseModel):
    name: str
    email: str
    password: str | None = None
    password_confirmation: str | None = None