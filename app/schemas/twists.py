from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Label, literal
from sqlalchemy.orm.attributes import InstrumentedAttribute
from typing import ClassVar
from uuid import UUID

from app.models import Twist, User
from app.schemas.types import Coordinate, Waypoint


class TwistCreateForm(BaseModel):
    name: str
    is_paved: bool
    waypoints: list[Waypoint] = Field(..., min_length=2)
    route_geometry: list[Coordinate]


class TwistBasic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fields: ClassVar = (Twist.id, Twist.name, Twist.is_paved)

    id: int
    name: str
    is_paved: bool


class TwistGeometry(TwistBasic):
    model_config = ConfigDict(from_attributes=True)

    fields: ClassVar = TwistBasic.fields + (Twist.waypoints, Twist.route_geometry)

    waypoints: list[Waypoint]
    route_geometry: list[Coordinate]


class TwistListItem(TwistBasic):
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def get_fields(cls, user: User | None) -> tuple[InstrumentedAttribute[int], InstrumentedAttribute[str], InstrumentedAttribute[bool], Label[bool]]:
        """
        Returns a tuple of all fields needed to populate this model,
        including dynamic expressions based on the current user.
        """
        if user:
            author_expression = (Twist.author_id == user.id)
        else:
            author_expression = literal(False)

        # Combine the parent's static fields with the new dynamic one
        return cls.fields + (
            author_expression.label("viewer_is_author"),
        )

    viewer_is_author: bool


class TwistDropdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fields: ClassVar = (Twist.id, Twist.is_paved, Twist.author_id, User.name.label("author_name"))

    id: int
    author_id: UUID
    is_paved: bool
    author_name: str