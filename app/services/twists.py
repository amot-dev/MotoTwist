from copy import deepcopy
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points
from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import logger
from app.models import Twist, User
from app.settings import settings
from app.schemas import Coordinate, TwistListItem, Waypoint


async def get_twists_for_list(session: AsyncSession, user: User) -> list[TwistListItem]:
    """
    Get the Twists in proper format to be consumed by the Twist List template.

    :param session: The session to use for database transactions.
    :param user: The user initiating the request.
    :return: A list of TwistListItems containing the required data.
    """
    if user:
        is_author_expression = (Twist.author_id == user.id)
    else:
        is_author_expression = literal(False)

    results = await session.execute(
        select(
            Twist.id,
            Twist.name,
            Twist.is_paved,
            is_author_expression.label("is_author")
        )
        .order_by(Twist.name)
    )
    return [
        TwistListItem(
            id=result.id,
            name=result.name,
            is_paved=result.is_paved,
            is_author=result.is_author
        ) for result in results.all()
    ]


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