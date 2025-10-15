from pydantic import BaseModel


class AverageRating(BaseModel):
    rating: float
    desc: str


class RatingCriterion(BaseModel):
    name: str
    desc: str | None


class RatingListItem(BaseModel):
    id: int
    author_name: str
    can_delete_rating: bool
    formatted_date: str
    ratings: dict[str, int]