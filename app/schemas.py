from fastapi_users import schemas
from pydantic import BaseModel, Field
from typing import TypedDict
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


class AverageRating(TypedDict):
    rating: float
    desc: str


class RatingCriterion(TypedDict):
    name: str
    desc: str | None


class RatingListItem(TypedDict):
    id: int
    author_name: str
    can_delete: bool
    formatted_date: str
    ratings: dict[str, int]


class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)  # Latitude must be between -90 and 90
    lng: float = Field(..., ge=-180, le=180) # Longitude must be between -180 and 180

class CoordinateDict(TypedDict):
    lat: float
    lng: float


class Waypoint(Coordinate):
    name: str

class WaypointDict(CoordinateDict):
    name: str


class TwistCreate(BaseModel):
    name: str
    is_paved: bool
    waypoints: list[Waypoint] = Field(..., min_length=2)
    route_geometry: list[Coordinate]


class TwistGeometryData(TypedDict):
    waypoints: list[WaypointDict]
    route_geometry: list[CoordinateDict]


class TwistListItem(TypedDict):
    id: int
    name: str
    is_paved: bool
    is_author: bool