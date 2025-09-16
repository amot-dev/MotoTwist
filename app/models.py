import datetime
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base

class Twist(Base):
    __tablename__ = "twists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    is_paved = Column(Boolean, default=True, nullable=False)

    waypoints = Column(JSONB, nullable=False)
    route_geometry = Column(JSONB, nullable=False)

    paved_ratings = relationship("PavedRating", back_populates="twist")
    unpaved_ratings = relationship("UnpavedRating", back_populates="twist")

    def __repr__(self):
        paved = "Paved" if self.is_paved else "Unpaved"
        return f"[{self.id}] {self.name} ({paved})"
    

class PavedRating(Base):
    __tablename__ = "paved_ratings"

    id = Column(Integer, primary_key=True)
    rating_date = Column(Date, default=datetime.date.today)

    traffic = Column(Integer, doc="Level of vehicle traffic on the road")
    scenery = Column(Integer, doc="Visual appeal of surroundings")
    pavement = Column(Integer, doc="Quality of road surface")
    twistyness = Column(Integer, doc="Tightness and frequency of turns")
    intensity = Column(Integer, doc="Overall riding energy the road draws out, from mellow to adrenaline-pumping")

    twist_id = Column(Integer, ForeignKey("twists.id"))
    twist = relationship("Twist", back_populates="paved_ratings")

    def __repr__(self):
        return f"[{self.id}] (Paved)"

class UnpavedRating(Base):
    __tablename__ = "unpaved_ratings"

    id = Column(Integer, primary_key=True)
    rating_date = Column(Date, default=datetime.date.today)

    traffic = Column(Integer, doc="Frequency of other vehicles or trail users")
    scenery = Column(Integer, doc="Visual appeal of surroundings")
    surface_consistency = Column(Integer, doc="Predictability of traction across the route")
    technicality = Column(Integer, doc="Challenge level from terrain features like rocks, ruts, sand, or mud")
    flow = Column(Integer, doc="Smoothness of the trail without constant disruptions or awkward sections")

    twist_id = Column(Integer, ForeignKey("twists.id"))
    twist = relationship("Twist", back_populates="unpaved_ratings")

    def __repr__(self):
        return f"[{self.id}] (Unpaved)"