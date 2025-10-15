from datetime import date
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from pydantic import BaseModel
from sqlalchemy import Boolean, Date, ForeignKey, inspect, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator
from typing import Any, Type
from uuid import UUID

from app.schemas.types import Coordinate, Waypoint


Base = declarative_base()


class SerializationMixin:
    """Provides a `to_dict` method to SQLAlchemy models."""
    def to_dict(self) -> dict[str, Any]:
        """
        Converts the model instance into a dictionary,
        serializing special types like UUID and date.
        """
        inspection_object = inspect(type(self))
        assert inspection_object != None

        columns = [c.name for c in inspection_object.columns]

        data: dict[str, Any] = {}
        for column in columns:
            value = getattr(self, column)

            # Handle special Python types
            if isinstance(value, UUID):
                data[column] = str(value)
            elif isinstance(value, date):
                data[column] = value.isoformat()
            else:
                data[column] = value

        return data


class PydanticJSONB(TypeDecorator[list[BaseModel]]):
    """
    A SQLAlchemy TypeDecorator to store lists of Pydantic models as JSONB.

    Usage:
    waypoints: Mapped[list[Waypoint]] = mapped_column(PydanticJson(Waypoint))
    """
    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_type: Type[BaseModel], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.pydantic_type = pydantic_type

    def process_bind_param(self, value: list[BaseModel] | None, dialect: Any) -> list[dict[Any, Any]] | None:
        """
        Called when sending data TO the database.
        Converts a list of Pydantic models to a list of dicts.
        """
        if value is None:
            return None
        return [item.model_dump(mode='json') for item in value]

    def process_result_value(self, value: list[dict[Any, Any]] | None, dialect: Any) -> list[BaseModel] | None:
        """
        Called when receiving data FROM the database.
        Converts a list of dicts back to a list of Pydantic models.
        """
        if value is None:
            return None
        return [self.pydantic_type.model_validate(item) for item in value]


class User(SQLAlchemyBaseUserTableUUID, SerializationMixin, Base):
    __tablename__ = "users"

    # Data
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Children
    twists: Mapped[list["Twist"]] = relationship("Twist", back_populates="author")
    paved_ratings: Mapped[list["PavedRating"]] = relationship("PavedRating", back_populates="author")
    unpaved_ratings: Mapped[list["UnpavedRating"]] = relationship("UnpavedRating", back_populates="author")


class Twist(SerializationMixin, Base):
    __tablename__ = "twists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Parents
    author_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    author: Mapped[User] = relationship("User", back_populates="twists")

    # Data
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    is_paved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    waypoints: Mapped[list[Waypoint]] = mapped_column(PydanticJSONB(Waypoint), nullable=False)
    route_geometry: Mapped[list[Coordinate]] = mapped_column(PydanticJSONB(Coordinate), nullable=False)
    simplification_tolerance_m: Mapped[int] = mapped_column(SmallInteger)

    # Children
    paved_ratings: Mapped[list["PavedRating"]] = relationship("PavedRating", back_populates="twist")
    unpaved_ratings: Mapped[list["UnpavedRating"]] = relationship("UnpavedRating", back_populates="twist")

    def __repr__(self):
        paved = "Paved" if self.is_paved else "Unpaved"
        return f"[{self.id}] {self.name} ({paved})"


class PavedRating(SerializationMixin, Base):
    __tablename__ = "paved_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Parents
    author_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    author: Mapped[User] = relationship("User", back_populates="paved_ratings")

    twist_id: Mapped[int] = mapped_column(Integer, ForeignKey("twists.id", ondelete="CASCADE"))
    twist: Mapped[Twist] = relationship("Twist", back_populates="paved_ratings")

    # Metadata
    rating_date: Mapped[date] = mapped_column(Date, default=date.today)

    # Data
    traffic: Mapped[int] = mapped_column(SmallInteger, doc="Level of vehicle traffic on the road")
    scenery: Mapped[int] = mapped_column(SmallInteger, doc="Visual appeal of surroundings")
    pavement: Mapped[int] = mapped_column(SmallInteger, doc="Quality of road surface")
    twistyness: Mapped[int] = mapped_column(SmallInteger, doc="Tightness and frequency of turns")
    intensity: Mapped[int] = mapped_column(SmallInteger, doc="Overall riding energy the road draws out, from mellow to adrenaline-pumping")

    def __repr__(self):
        return f"[{self.id}] (Paved)"


class UnpavedRating(SerializationMixin, Base):
    __tablename__ = "unpaved_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Parents
    author_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    author: Mapped[User] = relationship("User", back_populates="unpaved_ratings")

    twist_id: Mapped[int] = mapped_column(Integer, ForeignKey("twists.id", ondelete="CASCADE"))
    twist: Mapped[Twist] = relationship("Twist", back_populates="unpaved_ratings")

    # Metadata
    rating_date: Mapped[date] = mapped_column(Date, default=date.today)

    # Data
    traffic: Mapped[int] = mapped_column(SmallInteger, doc="Frequency of other vehicles or trail users")
    scenery: Mapped[int] = mapped_column(SmallInteger, doc="Visual appeal of surroundings")
    surface_consistency: Mapped[int] = mapped_column(SmallInteger, doc="Predictability of traction across the route")
    technicality: Mapped[int] = mapped_column(SmallInteger, doc="Challenge level from terrain features like rocks, ruts, sand, or mud")
    flow: Mapped[int] = mapped_column(SmallInteger, doc="Smoothness of the trail without constant disruptions or awkward sections")

    def __repr__(self):
        return f"[{self.id}] (Unpaved)"