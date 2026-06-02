import json

from scheduler.models import (
    World,
    Weights,
    Station,
    Route,
    RouteSegment,
    Bus,
    Scenario,
    Direction,
)
from scheduler.utils import time_to_minutes


def load_world(path: str) -> World:
    with open(path, "r") as f:
        data = json.load(f)

    return World(**data)


def load_stations(path: str) -> list[Station]:
    with open(path, "r") as f:
        data = json.load(f)

    return [
        Station(**station)
        for station in data
    ]


def load_route(path: str) -> Route:
    with open(path, "r") as f:
        data = json.load(f)

    segments = [
        RouteSegment(
            from_station=edge["from"],
            to_station=edge["to"],
            distance_km=edge["distance_km"]
        )
        for edge in data["edges"]
    ]

    stations = [
        station["id"]
        for station in data["stations"]
    ]

    return Route(
        id=data["route_id"],
        stations=stations,
        segments=segments
    )


def load_scenario(path: str) -> Scenario:
    with open(path, "r") as f:
        data = json.load(f)

    weights = Weights(**data["weights"])

    buses = [
    Bus(
    id=bus["id"],
    operator=bus["operator"],
    direction=Direction(bus["direction"]),
    departure_time_minutes=time_to_minutes(
        bus["departure_time"]
    ),

)
    for bus in data["buses"]
    ]

    return Scenario(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        weights=weights,
        buses=buses
    )