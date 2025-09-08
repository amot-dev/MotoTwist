import datetime
from typing import List
from pydantic import BaseModel

class SegmentBase(BaseModel):
    name: str
    file_path: str
    is_paved: bool

class SegmentCreate(SegmentBase):
    pass

class Segment(SegmentBase):
    id: int
    # A segment will have one of these two lists populated
    paved_ratings: List[PavedRating] = []
    unpaved_ratings: List[UnpavedRating] = []

    class Config:
        orm_mode = True


class PavedRatingBase(BaseModel):
    smoothness: int
    scenery: int

class PavedRatingCreate(PavedRatingBase):
    pass

class PavedRating(PavedRatingBase):
    id: int
    rating_date: datetime.date
    segment_id: int

    class Config:
        orm_mode = True


class UnpavedRatingBase(BaseModel):
    technicality: int
    flow: int

class UnpavedRatingCreate(UnpavedRatingBase):
    pass

class UnpavedRating(UnpavedRatingBase):
    id: int
    rating_date: datetime.date
    segment_id: int

    class Config:
        orm_mode = True