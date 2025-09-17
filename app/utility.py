from copy import deepcopy
from fastapi import HTTPException
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import *
from database import SessionLocal
from models import Twist, PavedRating, UnpavedRating
from schemas import Coordinate, Waypoint

def get_db():
    """
    Dependency to get a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def raise_http(detail: str, status_code: int = 500, exception: Exception = None) -> None:
    """
    Logs an error and its stack trace, then raises an HTTPException.
    """
    if exception:
        logger.exception(detail)
        raise HTTPException(status_code=status_code, detail=detail) from exception
    else:
        logger.error(detail)
        raise HTTPException(status_code=status_code, detail=detail)

async def calculate_average_rating(db: Session, twist: Twist, round_to: int) -> dict[str, float]:
    """
    Calculates the average ratings for a twist.
    """
    if twist.is_paved:
        target_model = PavedRating
        criteria_list = RATING_CRITERIA_PAVED
    else:
        target_model = UnpavedRating
        criteria_list = RATING_CRITERIA_UNPAVED
    criteria_columns = [getattr(target_model, criteria["name"]) for criteria in criteria_list]

    # Create a lookup dictionary for descriptions for easy access
    descriptions = {criteria["name"]: criteria["desc"] for criteria in criteria_list}

    # Query averages for target ratings columns for this twist
    query_expressions = [func.avg(col).label(col.key) for col in criteria_columns]
    averages = db.query(*query_expressions).filter(target_model.twist_id == twist.id).first()

    return {
        key: {
            "rating": round(value, round_to),
            "desc": descriptions.get(key, "")
        }
        for key, value in averages._asdict().items()
        if value is not None
    } if averages else {}

def snap_waypoints_to_route(waypoints: list[Waypoint], route_geometry: list[Coordinate]) -> list[Waypoint]:
    """
    Maps a list of Waypoints to a route track of Coordinates.
    - The first waypoint is mapped to the first trackpoint.
    - The last waypoint is mapped to the last trackpoint.
    - Intermediate waypoints are mapped to their nearest trackpoint.

    Returns a new list of modified Waypoints.
    """
    if not route_geometry or not waypoints or len(waypoints) < 2:
        return waypoints

    # Create a deep copy to avoid modifying the original list
    snapped_waypoints = deepcopy(waypoints)
    line = LineString([(coord.lat, coord.lng) for coord in route_geometry])

    # Handle the first waypoint
    first_coord = line.coords[0]
    snapped_waypoints[0].lat = first_coord[0]
    snapped_waypoints[0].lng = first_coord[1]

    # Handle the last waypoint
    last_coord = line.coords[-1]
    snapped_waypoints[-1].lat = last_coord[0]
    snapped_waypoints[-1].lng = last_coord[1]

    # Handle intermediate waypoints
    if len(snapped_waypoints) > 2:
        for i in range(1, len(snapped_waypoints) - 1):
            waypoint = snapped_waypoints[i]
            point = Point(waypoint.lat, waypoint.lng)

            # Find the nearest point on the line to the waypoint's location
            snapped_point = nearest_points(line, point)[0]

            # Update the waypoint's coordinates
            waypoint.lat = snapped_point.x
            waypoint.lng = snapped_point.y

    return snapped_waypoints

def simplify_route(coordinates: list[Coordinate], epsilon: float | None = None) -> (list[Coordinate], int | None):
    """
    Simplifies a route's coordinates, returning the new list and tolerance in meters.
    The tolerance is taken from the provided `epsilon` (in degrees) or falls back
    to the global `TWIST_SIMPLIFICATION_TOLERANCE_M` setting if epsilon is None.
    """
    # Approximation for 1 degree of latitude in meters
    METERS_PER_DEGREE_APPROX = 111132

    # Only simplify if more than 2 points
    if len(coordinates) < 2:
        return (coordinates, None)

    # Calculate epsilon from env if not given
    if epsilon is None:
        if not TWIST_SIMPLIFICATION_TOLERANCE_M:
            logger.debug("Twist simplification skipped due to unset tolerance")
            return (coordinates, None)

        logger.info(f"Simplifying Twist route with tolerance of {TWIST_SIMPLIFICATION_TOLERANCE_M}m")
        epsilon = TWIST_SIMPLIFICATION_TOLERANCE_M / METERS_PER_DEGREE_APPROX

    # Simplify route
    line = LineString([(c.lat, c.lng) for c in coordinates])
    simplified_line = line.simplify(epsilon, preserve_topology=True)
    simplified_coordinates = [Coordinate(lat=x, lng=y) for x, y in simplified_line.coords]

    return (simplified_coordinates, TWIST_SIMPLIFICATION_TOLERANCE_M)