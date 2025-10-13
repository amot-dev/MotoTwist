from datetime import date
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import Boolean, ForeignKey, Integer, SmallInteger, String, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID

from app.schemas import CoordinateDict, WaypointDict


Base = declarative_base()


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    # Data
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Children
    twists: Mapped[list["Twist"]] = relationship("Twist", back_populates="author")
    paved_ratings: Mapped[list["PavedRating"]] = relationship("PavedRating", back_populates="author")
    unpaved_ratings: Mapped[list["UnpavedRating"]] = relationship("UnpavedRating", back_populates="author")


class Twist(Base):
    __tablename__ = "twists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Parents
    author_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    author: Mapped[User] = relationship("User", back_populates="twists")

    # Data
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    is_paved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    waypoints: Mapped[list[WaypointDict]] = mapped_column(JSONB, nullable=False)
    route_geometry: Mapped[list[CoordinateDict]] = mapped_column(JSONB, nullable=False)
    simplification_tolerance_m: Mapped[int] = mapped_column(SmallInteger)

    # Children
    paved_ratings: Mapped[list["PavedRating"]] = relationship("PavedRating", back_populates="twist")
    unpaved_ratings: Mapped[list["UnpavedRating"]] = relationship("UnpavedRating", back_populates="twist")

    def __repr__(self):
        paved = "Paved" if self.is_paved else "Unpaved"
        return f"[{self.id}] {self.name} ({paved})"


class PavedRating(Base):
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


class UnpavedRating(Base):
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