from pydantic import BaseModel


class UserCreateFormAdmin(BaseModel):
    name: str
    email: str
    is_superuser: bool = False