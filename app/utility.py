from copy import deepcopy
from fastapi import HTTPException
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper
from starlette.datastructures import UploadFile
from typing import cast, NoReturn, TypeGuard

from config import logger
from models import PavedRating, UnpavedRating
from settings import settings
from schemas import AverageRating, Coordinate, RatingCriterion, Waypoint


# Criteria columns
RATING_EXCLUDED_COLUMNS = {"id", "twist_id", "rating_date"}
RATING_CRITERIA_PAVED: list[RatingCriterion] = [
    {"name": col.name, "desc": col.doc}
    for col in cast(Mapper[PavedRating], inspect(PavedRating)).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]
RATING_CRITERIA_UNPAVED: list[RatingCriterion] = [
    {"name": col.name, "desc": col.doc}
    for col in cast(Mapper[UnpavedRating], inspect(UnpavedRating)).columns
    if col.name not in RATING_EXCLUDED_COLUMNS
]


def raise_http(detail: str, status_code: int = 500, exception: Exception | None = None) -> NoReturn:
    """
    Log an error and its stack trace, then raise an HTTPException.

    :param detail: The error message to send to the client.
    :param status_code: Optional HTTP status code. Defaults to 500.
    :param exception: Optional Exception object from which to create stack trace. Defaults to None.
    :raises HTTPException: Always.
    """
    if exception:
        logger.exception(detail)
        raise HTTPException(status_code=status_code, detail=detail) from exception
    else:
        logger.error(detail)
        raise HTTPException(status_code=status_code, detail=detail)


def is_form_value_string(value: UploadFile | str | None) -> TypeGuard[str]:
    """
    Type Guard to validate form values as strings.

    :param value: The form value to validate.
    :return: True if the value is a string, False otherwise.
    """
    """Returns True if the form value is a string, acting as a type guard."""
    return value is not None and isinstance(value, str)


async def calculate_average_rating(session: AsyncSession, twist_id: int, twist_is_paved: bool, round_to: int) -> dict[str, AverageRating]:
    """
    Calculate the average ratings for a Twist.

    :param session: The session to use for database transactions.
    :param twist_id: The id of the Twist for which to calculate average ratings.
    :param twist_is_paved: Whether or not the Twist is paved.
    :param round_to: The number of decimal places to round to.
    :return: A dictionary of each criteria and its average rating.
    """
    if twist_is_paved:
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
    result = await session.execute(
        select(*query_expressions).where(target_model.twist_id == twist_id)
    )
    averages = result.first()

    return {
        key: cast(AverageRating, {
            "rating": round(value, round_to),
            "desc": descriptions.get(key, "")
        })
        for key, value in averages._asdict().items()  # pyright: ignore [reportPrivateUsage]
        if value is not None
    } if averages else {}


def snap_waypoints_to_route(waypoints: list[Waypoint], route_geometry: list[Coordinate]) -> list[Waypoint]:
    """
    Map a list of Waypoints to a route track of Coordinates.
    - The first waypoint is mapped to the first trackpoint.
    - The last waypoint is mapped to the last trackpoint.
    - Intermediate waypoints are mapped to their nearest trackpoint.

    :param waypoints: The list of Waypoints to snap to the route.
    :param route_geometry: The list of Coordinates making up the route to snap to.
    :return: A new list of modified Waypoints.
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



def simplify_route(coordinates: list[Coordinate]) -> list[Coordinate]:
    """
    Simplify a route's coordinates based off the `TWIST_SIMPLIFICATION_TOLERANCE_M` setting. Reduces storage space for database.

    :param coordinates: The list of Coordinates to simplify.
    :return: A new list of simplified Coordinates.
    """
    # Approximation for 1 degree of latitude in meters
    METERS_PER_DEGREE_APPROX = 111132

    # Only simplify if more than 2 points
    if len(coordinates) < 2:
        return coordinates

    logger.info(f"Simplifying Twist route with tolerance of {settings.TWIST_SIMPLIFICATION_TOLERANCE_M}m")
    epsilon = settings.TWIST_SIMPLIFICATION_TOLERANCE_M / METERS_PER_DEGREE_APPROX

    # Simplify route
    line = LineString([(c.lat, c.lng) for c in coordinates])
    simplified_line = line.simplify(epsilon, preserve_topology=True)
    simplified_coordinates = [Coordinate(lat=x, lng=y) for x, y in simplified_line.coords]

    return simplified_coordinates