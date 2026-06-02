"""Centralized rule-evaluation context construction."""

from __future__ import annotations

from collections import defaultdict

from scheduler.models import Bus, BusSchedule


def build_bus_context(
    schedule: BusSchedule,
    operator_delay: int,
    departure_time_minutes: int,
) -> dict:
    return {
        "wait_time": schedule.total_wait_time,
        "operator_delay": operator_delay,
        "network_delay": (
            schedule.final_arrival_time - departure_time_minutes
        ),
    }


def build_fleet_context(
    schedules: list[BusSchedule],
    buses: list[Bus],
) -> dict:
    bus_by_id = {b.id: b for b in buses}
    operator_totals: dict[str, int] = defaultdict(int)
    total_wait = 0
    max_bus_wait = 0
    makespan = 0

    for schedule in schedules:
        total_wait += schedule.total_wait_time
        max_bus_wait = max(max_bus_wait, schedule.total_wait_time)
        bus = bus_by_id[schedule.bus_id]
        operator_totals[bus.operator] += schedule.total_wait_time
        trip = schedule.final_arrival_time - bus.departure_time_minutes
        makespan = max(makespan, trip)

    return {
        "wait_time": total_wait,
        "operator_delay": (
            max(operator_totals.values()) if operator_totals else 0
        ),
        "network_delay": makespan,
    }
