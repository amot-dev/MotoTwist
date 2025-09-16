from pydantic import BaseModel, Field

class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)  # Latitude must be between -90 and 90
    lng: float = Field(..., ge=-180, le=180) # Longitude must be between -180 and 180

class Waypoint(Coordinate):
    name: str

class TwistCreate(BaseModel):
    name: str
    is_paved: bool
    waypoints: list[Waypoint] = Field(..., min_length=2)
    route_geometry: list[Coordinate]