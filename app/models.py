import datetime
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Date
from sqlalchemy.orm import relationship

from database import Base

class Twist(Base):
    __tablename__ = "twists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    file_path = Column(String(255), unique=True, nullable=False)
    is_paved = Column(Boolean, default=True, nullable=False)

    paved_ratings = relationship("PavedRating", back_populates="twist")
    unpaved_ratings = relationship("UnpavedRating", back_populates="twist")
    

class PavedRating(Base):
    __tablename__ = "paved_ratings"

    id = Column(Integer, primary_key=True)
    rating_date = Column(Date, default=datetime.date.today)
    smoothness = Column(Integer)
    scenery = Column(Integer)

    twist_id = Column(Integer, ForeignKey("twists.id"))
    twist = relationship("Twist", back_populates="paved_ratings")

class UnpavedRating(Base):
    __tablename__ = "unpaved_ratings"

    id = Column(Integer, primary_key=True)
    rating_date = Column(Date, default=datetime.date.today)
    technicality = Column(Integer)
    flow = Column(Integer)

    twist_id = Column(Integer, ForeignKey("twists.id"))
    twist = relationship("Twist", back_populates="unpaved_ratings")