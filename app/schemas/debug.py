from pydantic import BaseModel, Field

from app.models import Twist

class SeedRatingsForm(BaseModel):
    rating_count: int = Field(..., gt=0)
    popular_twist_name: str = Field(..., max_length=Twist.NAME_MAX_LENGTH)
    popular_rating_count: int = Field(..., gt=0)
    distribution_focus: float = Field(default=2.0, gt=1.0)