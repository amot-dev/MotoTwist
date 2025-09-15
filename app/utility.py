from fastapi import HTTPException
from math import radians, sin, cos, sqrt, atan2
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

# def haversine_distance(lat1, lon1, lat2, lon2):
#     """
#     Calculates the distance between two points on Earth using the Haversine formula.
#     Returns the distance in kilometers.
#     """
#     R = 6371.0  # Earth radius in kilometers

#     lat1_rad = radians(lat1)
#     lon1_rad = radians(lon1)
#     lat2_rad = radians(lat2)
#     lon2_rad = radians(lon2)

#     dlon = lon2_rad - lon1_rad
#     dlat = lat2_rad - lat1_rad

#     a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
#     c = 2 * atan2(sqrt(a), sqrt(1 - a))

#     distance = R * c
#     return distance

# def fix_waypoints_onto_track(gpx: gpxpy.gpx.GPX) -> gpxpy.gpx.GPX:
#     """
#     Maps waypoints in a GPX object to its primary track.
#     - The first waypoint is mapped to the first trackpoint.
#     - The last waypoint is mapped to the last trackpoint.
#     - Intermediate waypoints are mapped to their nearest trackpoint.

#     Returns the modified GPX object.
#     """
#     # 1. Basic validation
#     if not gpx.tracks or not gpx.waypoints:
#         # Not enough data to perform the mapping
#         return gpx

#     # 2. Flatten all trackpoints from all segments into a single list
#     all_trackpoints = [point for segment in gpx.tracks[0].segments for point in segment.points]

#     if not all_trackpoints:
#         # The track exists but has no points
#         return gpx

#     num_waypoints = len(gpx.waypoints)

#     # 3. Handle the first waypoint
#     first_trackpoint = all_trackpoints[0]
#     gpx.waypoints[0].latitude = first_trackpoint.latitude
#     gpx.waypoints[0].longitude = first_trackpoint.longitude

#     # 4. Handle the last waypoint (if there is more than one)
#     if num_waypoints > 1:
#         last_trackpoint = all_trackpoints[-1]
#         gpx.waypoints[-1].latitude = last_trackpoint.latitude
#         gpx.waypoints[-1].longitude = last_trackpoint.longitude

#     # 5. Handle intermediate waypoints
#     if num_waypoints > 2:
#         # Iterate through waypoints from the second to the second-to-last
#         for i in range(1, num_waypoints - 1):
#             waypoint = gpx.waypoints[i]

#             closest_trackpoint = None
#             min_distance = float('inf')

#             # Find the closest trackpoint for the current waypoint
#             for trackpoint in all_trackpoints:
#                 distance = haversine_distance(
#                     waypoint.latitude, waypoint.longitude,
#                     trackpoint.latitude, trackpoint.longitude
#                 )
#                 if distance < min_distance:
#                     min_distance = distance
#                     closest_trackpoint = trackpoint

#             # Update waypoint coordinates to match the closest trackpoint
#             if closest_trackpoint:
#                 waypoint.latitude = closest_trackpoint.latitude
#                 waypoint.longitude = closest_trackpoint.longitude

#     return gpx