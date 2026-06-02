from dataclasses import dataclass

from scheduler.models import BusSchedule
from scheduler.utils import minutes_to_time


@dataclass
class TimelineRow:
    bus_id: str
    station: str
    event: str
    start_minutes: int
    end_minutes: int
    start_time: str
    end_time: str
    duration_minutes: int
    wait_minutes: int | None = None


@dataclass
class StationRow:
    station: str
    bus_id: str
    arrival_time: str
    charge_start_time: str
    charge_end_time: str
    wait_minutes: int


def _row(
    bus_id: str,
    station: str,
    event: str,
    start: int,
    end: int,
    wait: int | None = None,
) -> TimelineRow:
    return TimelineRow(
        bus_id=bus_id,
        station=station,
        event=event,
        start_minutes=start,
        end_minutes=end,
        start_time=minutes_to_time(start),
        end_time=minutes_to_time(end),
        duration_minutes=end - start,
        wait_minutes=wait,
    )


def _travel_rows(
    schedule: BusSchedule,
    origin: str,
    destination: str,
    start_time: int,
    end_time: int,
) -> list[TimelineRow]:
    return [
        _row(
            schedule.bus_id,
            f"{origin} → {destination}",
            "travel",
            start_time,
            end_time,
        )
    ]


def build_bus_timetable(
    schedules: list[BusSchedule],
    departure_times: dict[str, int],
    direction_endpoints: dict[str, tuple[str, str]],
) -> dict[str, list[TimelineRow]]:
    timetables: dict[str, list[TimelineRow]] = {}

    for schedule in schedules:
        rows: list[TimelineRow] = []
        origin, destination = direction_endpoints[schedule.bus_id]
        current_time = departure_times[schedule.bus_id]
        current_station = origin

        rows.append(
            _row(
                schedule.bus_id,
                origin,
                "depart",
                current_time,
                current_time,
            )
        )

        for event in schedule.charging_events:
            if event.arrival_time > current_time:
                rows.extend(
                    _travel_rows(
                        schedule,
                        current_station,
                        event.station,
                        current_time,
                        event.arrival_time,
                    )
                )

            if event.wait_time > 0:
                rows.append(
                    _row(
                        schedule.bus_id,
                        event.station,
                        "wait",
                        event.arrival_time,
                        event.charge_start_time,
                        wait=event.wait_time,
                    )
                )

            mins = event.charge_duration_minutes or (
                event.charge_end_time - event.charge_start_time
            )
            charge_label = f"charge (full, {mins} min)"
            rows.append(
                _row(
                    schedule.bus_id,
                    event.station,
                    charge_label,
                    event.charge_start_time,
                    event.charge_end_time,
                )
            )

            current_time = event.charge_end_time
            current_station = event.station

        if schedule.final_arrival_time > current_time:
            rows.extend(
                _travel_rows(
                    schedule,
                    current_station,
                    destination,
                    current_time,
                    schedule.final_arrival_time,
                )
            )

        rows.append(
            _row(
                schedule.bus_id,
                destination,
                "arrive",
                schedule.final_arrival_time,
                schedule.final_arrival_time,
            )
        )

        timetables[schedule.bus_id] = rows

    return timetables


def build_station_view(
    schedules: list[BusSchedule],
) -> dict[str, list[StationRow]]:
    station_view: dict[str, list[StationRow]] = {}

    for schedule in schedules:
        for event in schedule.charging_events:
            station_view.setdefault(event.station, []).append(
                StationRow(
                    station=event.station,
                    bus_id=schedule.bus_id,
                    arrival_time=minutes_to_time(
                        event.arrival_time
                    ),
                    charge_start_time=minutes_to_time(
                        event.charge_start_time
                    ),
                    charge_end_time=minutes_to_time(
                        event.charge_end_time
                    ),
                    wait_minutes=event.wait_time,
                )
            )

    for station in station_view:
        station_view[station].sort(
            key=lambda row: row.charge_start_time
        )

    return station_view


def build_summary_table(
    schedules: list[BusSchedule],
) -> list[dict]:
    return [
        {
            "bus_id": schedule.bus_id,
            "plan": " → ".join(schedule.route_plan),
            "final_arrival": minutes_to_time(
                schedule.final_arrival_time
            ),
            "total_wait_minutes": schedule.total_wait_time,
            "charge_stops": len(schedule.charging_events),
        }
        for schedule in schedules
    ]
