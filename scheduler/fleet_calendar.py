"""Shared charger timeline for fleet-wide planning."""

from copy import deepcopy


class FleetCalendar:
    """
    One charger per station: tracks when the pump is free again.
    All buses share this during planning.
    """

    def __init__(self, station_ids: list[str]):
        self._free_after = {sid: 0 for sid in station_ids}

    def copy(self) -> "FleetCalendar":
        clone = FleetCalendar(list(self._free_after.keys()))
        clone._free_after = deepcopy(self._free_after)
        return clone

    def free_after(self, station_id: str) -> int:
        return self._free_after[station_id]

    def reserve(
        self,
        station_id: str,
        arrival_time: int,
        duration_minutes: int,
    ) -> tuple[int, int, int]:
        """
        Book the charger. Returns (arrival, charge_start, charge_end).
        wait = charge_start - arrival
        """
        charge_start = max(arrival_time, self._free_after[station_id])
        wait = charge_start - arrival_time
        charge_end = charge_start + duration_minutes
        self._free_after[station_id] = charge_end
        return arrival_time, charge_start, charge_end, wait

    def total_slack(self) -> int:
        """Sum of free-after times — diagnostic only."""
        return sum(self._free_after.values())
