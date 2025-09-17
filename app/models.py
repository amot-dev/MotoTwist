from datetime import date
from sqlalchemy import Boolean, ForeignKey, Integer, SmallInteger, String, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from schemas import CoordinateDict, WaypointDict

class Twist(Base):
    __tablename__ = "twists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    is_paved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    waypoints: Mapped[list[WaypointDict]] = mapped_column(JSONB, nullable=False)
    route_geometry: Mapped[list[CoordinateDict]] = mapped_column(JSONB, nullable=False)
    simplification_tolerance_m: Mapped[int] = mapped_column(SmallInteger)

    paved_ratings: Mapped[list["PavedRating"]] = relationship("PavedRating", back_populates="twist")
    unpaved_ratings: Mapped[list["UnpavedRating"]] = relationship("UnpavedRating", back_populates="twist")

    def __repr__(self):
        paved = "Paved" if self.is_paved else "Unpaved"
        return f"[{self.id}] {self.name} ({paved})"

class PavedRating(Base):
    __tablename__ = "paved_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rating_date: Mapped[date] = mapped_column(Date, default=date.today)

    traffic: Mapped[int] = mapped_column(SmallInteger, doc="Level of vehicle traffic on the road")
    scenery: Mapped[int] = mapped_column(SmallInteger, doc="Visual appeal of surroundings")
    pavement: Mapped[int] = mapped_column(SmallInteger, doc="Quality of road surface")
    twistyness: Mapped[int] = mapped_column(SmallInteger, doc="Tightness and frequency of turns")
    intensity: Mapped[int] = mapped_column(SmallInteger, doc="Overall riding energy the road draws out, from mellow to adrenaline-pumping")

    twist_id: Mapped[int] = mapped_column(Integer, ForeignKey("twists.id", ondelete="CASCADE"))
    twist: Mapped[Twist] = relationship("Twist", back_populates="paved_ratings")

    def __repr__(self):
        return f"[{self.id}] (Paved)"

class UnpavedRating(Base):
    __tablename__ = "unpaved_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rating_date: Mapped[date] = mapped_column(Date, default=date.today)

    traffic: Mapped[int] = mapped_column(SmallInteger, doc="Frequency of other vehicles or trail users")
    scenery: Mapped[int] = mapped_column(SmallInteger, doc="Visual appeal of surroundings")
    surface_consistency: Mapped[int] = mapped_column(SmallInteger, doc="Predictability of traction across the route")
    technicality: Mapped[int] = mapped_column(SmallInteger, doc="Challenge level from terrain features like rocks, ruts, sand, or mud")
    flow: Mapped[int] = mapped_column(SmallInteger, doc="Smoothness of the trail without constant disruptions or awkward sections")

    twist_id: Mapped[int] = mapped_column(Integer, ForeignKey("twists.id", ondelete="CASCADE"))
    twist: Mapped[Twist] = relationship("Twist", back_populates="unpaved_ratings")

    def __repr__(self):
        return f"[{self.id}] (Unpaved)"