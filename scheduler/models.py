from dataclasses import dataclass
from typing import List
from enum import Enum


# ---------------------------
# Enums
# ---------------------------

class Direction(Enum):
    FORWARD = "forward"
    REVERSE = "reverse"


# ---------------------------
# Global Configuration
# ---------------------------

@dataclass
class World:
    battery_range_km: int
    charging_time_minutes: int
    speed_kmph: int


# ---------------------------
# Scenario Weights
# ---------------------------

@dataclass
class Weights:
    individual: float
    operator: float
    overall: float


# ---------------------------
# Infrastructure
# ---------------------------

@dataclass
class Station:
    id: str
    chargers: int


@dataclass
class RouteSegment:
    from_station: str
    to_station: str
    distance_km: int


@dataclass
class Route:
    id: str
    stations: List[str]
    segments: List[RouteSegment]

    def distance_between(self, frm: str, to: str) -> int:
        for segment in self.segments:
            if (
                segment.from_station == frm
                and segment.to_station == to
            ):
                return segment.distance_km

        raise ValueError(
            f"No segment found between {frm} and {to}"
        )


# ---------------------------
# Buses
# ---------------------------

@dataclass
class Bus:
    id: str
    operator: str
    direction: Direction
    departure_time_minutes: int


# ---------------------------
# Scenario
# ---------------------------

@dataclass
class Scenario:
    id: str
    name: str
    description: str
    weights: Weights
    buses: List[Bus]


# ---------------------------
# Scheduling Output
# ---------------------------

@dataclass
class ChargingEvent:
    station: str
    arrival_time: int
    charge_start_time: int
    charge_end_time: int
    wait_time: int
    charge_duration_minutes: int = 0
    outgoing_leg_km: int = 0


@dataclass
class BusSchedule:
    bus_id: str
    route_plan: List[str]
    charging_events: List[ChargingEvent]
    final_arrival_time: int
    total_wait_time: int