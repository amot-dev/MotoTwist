from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Label, literal
from sqlalchemy.orm.attributes import InstrumentedAttribute
from typing import ClassVar, Literal
from uuid import UUID

from app.models import Twist, User
from app.schemas.types import Coordinate, Waypoint


class TwistCreateForm(BaseModel):
    name: str
    is_paved: bool
    waypoints: list[Waypoint] = Field(..., min_length=2)
    route_geometry: list[Coordinate] = Field(..., min_length=2)


class TwistFilterParams(BaseModel):
    search: str | None = None
    ownership: Literal["all", "own"] = "all"
    rated: Literal["all", "rated", "unrated"] = "all"
    visibility: Literal["all", "visible", "hidden"] = "all"

    visible_ids: list[int] | None = None


class TwistUltraBasic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fields: ClassVar = (Twist.id, Twist.is_paved)

    id: int
    is_paved: bool


class TwistBasic(TwistUltraBasic):
    model_config = ConfigDict(from_attributes=True)

    fields: ClassVar = TwistUltraBasic.fields + (Twist.name,)

    name: str


class TwistGeometry(TwistBasic):
    model_config = ConfigDict(from_attributes=True)

    fields: ClassVar = TwistBasic.fields + (Twist.waypoints, Twist.route_geometry)

    waypoints: list[Waypoint]
    route_geometry: list[Coordinate]


class TwistListItem(TwistBasic):
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def get_fields(cls, user: User | None) -> tuple[InstrumentedAttribute[int], InstrumentedAttribute[bool], InstrumentedAttribute[str], Label[bool]]:
        """
        Determine database fields needed to populate this model,
        including dynamic expressions based on the current user.

        :param user: Optional user viewing the Twist list.
        :return: A tuple of all database fields needed to populate this model.
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


class TwistDropdown(TwistUltraBasic):
    model_config = ConfigDict(from_attributes=True)

    fields: ClassVar = TwistUltraBasic.fields + (Twist.author_id, User.name.label("author_name"))

    author_id: UUID
    author_name: str