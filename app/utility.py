from copy import deepcopy
from fastapi import HTTPException
import math
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import *
from database import SessionLocal
from models import Twist, PavedRating, UnpavedRating

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

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the distance between two points on Earth using the Haversine formula.
    Returns the distance in kilometers.
    """
    R = 6371.0  # Earth radius in kilometers

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

def snap_waypoints_to_route(waypoints_data, route_geometry_data):
    """
    Maps waypoints in a list of dictionaries to a route track.
    - The first waypoint is mapped to the first trackpoint.
    - The last waypoint is mapped to the last trackpoint.
    - Intermediate waypoints are mapped to their nearest trackpoint.

    Returns a new list of modified waypoints.
    """
    if not route_geometry_data or not waypoints_data or len(waypoints_data) < 2:
        return waypoints_data

    # Create a deep copy to avoid modifying the original list
    snapped_waypoints = deepcopy(waypoints_data)
    num_waypoints = len(snapped_waypoints)
    num_trackpoints = len(route_geometry_data)

    # Handle the first waypoint
    first_trackpoint = route_geometry_data[0]
    snapped_waypoints[0]['lat'] = first_trackpoint['lat']
    snapped_waypoints[0]['lng'] = first_trackpoint['lng']

    # Handle the last waypoint
    last_trackpoint = route_geometry_data[-1]
    snapped_waypoints[-1]['lat'] = last_trackpoint['lat']
    snapped_waypoints[-1]['lng'] = last_trackpoint['lng']

    # Handle intermediate waypoints with forward search
    last_match_index = 0
    if num_waypoints > 2:
        # Iterate through waypoints from the second to the second-to-last
        for i in range(1, num_waypoints - 1):
            waypoint = snapped_waypoints[i]

            min_distance = float('inf')
            closest_trackpoint_index = last_match_index

            # Start searching from the last matched trackpoint index
            for j in range(last_match_index, num_trackpoints):
                trackpoint = route_geometry_data[j]
                distance = haversine_distance(
                    waypoint['lat'], waypoint['lng'],
                    trackpoint['lat'], trackpoint['lng']
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_trackpoint_index = j

            # Update waypoint to the closest point found
            closest_trackpoint = route_geometry_data[closest_trackpoint_index]
            waypoint['lat'] = closest_trackpoint['lat']
            waypoint['lng'] = closest_trackpoint['lng']

            # Update the starting point for the next search
            last_match_index = closest_trackpoint_index

    return snapped_waypoints