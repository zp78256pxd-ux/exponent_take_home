"""
Version 2 — incremental fleet scheduler (default).

Bus-by-bus decisions on a shared FleetCalendar: forward fleet, then reverse.
Fast, deterministic, production-friendly.
"""

from __future__ import annotations

from collections import defaultdict

from scheduler.fleet_calendar import FleetCalendar
from scheduler.context_builder import build_bus_context, build_fleet_context
from scheduler.fleet_optimizer import bus_orders
from scheduler.models import Bus, BusSchedule, Weights
from scheduler.rule_engine import RuleEngine


class FleetSequentialScheduler:
    """V2: one bus commits a plan, then the calendar advances."""

    def __init__(self, scheduler: object):
        self._scheduler = scheduler

    def _bus_order(self, buses: list[Bus]) -> list[Bus]:
        return bus_orders(buses)[0][1]

    def _station_load(
        self,
        calendar: FleetCalendar,
    ) -> int:
        return calendar.total_slack()

    def _pick_plan_for_bus(
        self,
        bus: Bus,
        plans: list[list[str]],
        calendar: FleetCalendar,
        weights: Weights,
    ) -> tuple[list[str], BusSchedule]:
        engine = RuleEngine(weights)
        best_plan = plans[0]
        best_schedule: BusSchedule | None = None
        best_key: tuple | None = None

        for plan in plans:
            trial_cal = calendar.copy()
            schedule = self._scheduler._simulate_plan_on_calendar(
                bus,
                plan,
                trial_cal,
            )
            bus_ctx = build_bus_context(
                schedule,
                schedule.total_wait_time,
                bus.departure_time_minutes,
            )
            trial_cal_after = trial_cal.copy()
            key = (
                schedule.total_wait_time,
                len(plan),
                -engine.evaluate(bus_ctx),
                self._station_load(trial_cal_after),
            )
            if best_key is None or key < best_key:
                best_key = key
                best_plan = list(plan)
                best_schedule = schedule

        assert best_schedule is not None
        committed = self._scheduler._simulate_plan_on_calendar(
            bus,
            best_plan,
            calendar,
        )
        return best_plan, committed

    def schedule(
        self,
        buses: list[Bus],
        plans: list[list[str]],
        weights: Weights,
    ) -> tuple[
        dict[str, list[str]],
        list[BusSchedule],
        dict,
        dict[str, list[dict]],
    ]:
        bus_order = self._bus_order(buses)
        calendar = FleetCalendar(self._scheduler._station_ids)
        assignment: dict[str, list[str]] = {}
        schedules: list[BusSchedule] = []
        plan_evaluations: dict[str, list[dict]] = {}
        running_wait = 0

        for bus in bus_order:
            plan_evaluations[bus.id] = (
                self.plan_evaluations_for_bus(
                    bus,
                    plans,
                    weights,
                    calendar.copy(),
                    running_wait,
                )
            )
            plan, schedule = self._pick_plan_for_bus(
                bus,
                plans,
                calendar,
                weights,
            )
            assignment[bus.id] = plan
            schedules.append(schedule)
            running_wait += schedule.total_wait_time

        context = build_fleet_context(schedules, buses)
        operator_waits: dict[str, int] = defaultdict(int)
        bus_by_id = {b.id: b for b in buses}
        for schedule in schedules:
            operator_waits[
                bus_by_id[schedule.bus_id].operator
            ] += schedule.total_wait_time

        meta = {
            "bus_order": "forward_then_reverse",
            "total_wait": context["wait_time"],
            "operator_waits": dict(operator_waits),
            "rule_score": RuleEngine(weights).evaluate(context),
        }
        return assignment, schedules, meta, plan_evaluations

    def plan_evaluations_for_bus(
        self,
        bus: Bus,
        plans: list[list[str]],
        weights: Weights,
        calendar: FleetCalendar,
        fleet_total_wait: int,
    ) -> list[dict]:
        engine = RuleEngine(weights)
        evaluations: list[dict] = []

        for plan in plans:
            trial_cal = calendar.copy()
            schedule = self._scheduler._simulate_plan_on_calendar(
                bus,
                plan,
                trial_cal,
            )
            bus_ctx = build_bus_context(
                schedule,
                schedule.total_wait_time,
                bus.departure_time_minutes,
            )
            evaluations.append(
                {
                    "plan": list(plan),
                    "score": engine.evaluate(bus_ctx),
                    "context": bus_ctx,
                    "schedule": schedule,
                    "wait_time": schedule.total_wait_time,
                    "fleet_total_wait": fleet_total_wait,
                }
            )

        evaluations.sort(
            key=lambda item: (
                item["wait_time"],
                len(item["plan"]),
                -item["score"],
            )
        )
        return evaluations
