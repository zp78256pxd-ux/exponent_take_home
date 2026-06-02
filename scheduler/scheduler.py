import time

"""
Bus Charging Scheduler — layered versions.

Version 2 (default): incremental fleet scheduling on FleetCalendar.
Version 3 (optional): global optimization via mode=\"v3\" API.
Version 4: warm-start from V2 + coordinate descent + swaps + delta evaluation.
"""

from scheduler.charging import full_charge_minutes
from scheduler.fleet_optimizer import FleetOptimizer, bus_orders
from scheduler.fleet_sequential import FleetSequentialScheduler
from scheduler.models import (
    Bus,
    BusSchedule,
    ChargingEvent,
    Scenario,
    Station,
    World,
    Route,
)
from scheduler.planner import generate_valid_plans
from scheduler.version import (
    V2_CHARGING_MODE,
    V2_SCHEDULER_VERSION,
    V2_VERSION_LABEL,
    V2_VERSION_NAME,
    V4_CHARGING_MODE,
    V4_ENGINE_LABEL,
    V4_SCHEDULER_VERSION,
    V4_VERSION_LABEL,
    V4_VERSION_NAME,
)


CHARGING_STATIONS = ["A", "B", "C", "D"]
FORWARD_DISTANCES = [100, 120, 100, 120, 100]

ScheduleMode = str  # "v2" | "v3"


class Scheduler:
    """Fleet bus charging scheduler (V2 default, V3 optional)."""

    def __init__(
        self,
        world: World,
        route: Route,
        stations: list[Station] | None = None,
        *,
        use_delta_eval: bool = True,
    ):
        self.world = world
        self.route = route
        self.stations = stations or []
        self._station_ids = (
            [s.id for s in self.stations]
            if self.stations
            else CHARGING_STATIONS
        )
        self._charge_duration = full_charge_minutes(world)
        self.use_delta_eval = use_delta_eval

    def _travel_time(self, distance_km: int) -> int:
        return int(
            distance_km / self.world.speed_kmph * 60
        )

    def _distance_between(self, start: str, end: str) -> int:
        if start == end:
            return 0
        route_order = self.route.stations
        start_idx = route_order.index(start)
        end_idx = route_order.index(end)
        distance = 0
        if start_idx < end_idx:
            for i in range(start_idx, end_idx):
                distance += self.route.distance_between(
                    route_order[i],
                    route_order[i + 1],
                )
        else:
            for i in range(start_idx, end_idx, -1):
                distance += self.route.distance_between(
                    route_order[i],
                    route_order[i - 1],
                )
        return distance

    def _destination_for(self, bus: Bus) -> str:
        if bus.direction.value == "forward":
            return "KOC"
        return "BLR"

    def _origin_for(self, bus: Bus) -> str:
        if bus.direction.value == "forward":
            return "BLR"
        return "KOC"

    def _simulate_plan_on_calendar(
        self,
        bus: Bus,
        plan: list[str],
        calendar,
    ) -> BusSchedule:
        """Simulate one bus on a shared fleet calendar (mutates calendar)."""
        current_time = bus.departure_time_minutes
        total_wait_time = 0
        charging_events: list[ChargingEvent] = []
        current_station = self._origin_for(bus)
        destination = self._destination_for(bus)

        for charge_station in plan:
            arrival_time = current_time + self._travel_time(
                self._distance_between(
                    current_station,
                    charge_station,
                )
            )
            arrival, charge_start, charge_end, wait_time = (
                calendar.reserve(
                    charge_station,
                    arrival_time,
                    self._charge_duration,
                )
            )
            total_wait_time += wait_time

            charging_events.append(
                ChargingEvent(
                    station=charge_station,
                    arrival_time=arrival,
                    charge_start_time=charge_start,
                    charge_end_time=charge_end,
                    wait_time=wait_time,
                    charge_duration_minutes=self._charge_duration,
                    outgoing_leg_km=0,
                )
            )
            current_time = charge_end
            current_station = charge_station

        final_arrival_time = current_time + self._travel_time(
            self._distance_between(
                current_station,
                destination,
            )
        )

        return BusSchedule(
            bus_id=bus.id,
            route_plan=plan,
            charging_events=charging_events,
            final_arrival_time=final_arrival_time,
            total_wait_time=total_wait_time,
        )

    def _all_valid_plans(self) -> list[list[str]]:
        return generate_valid_plans(
            CHARGING_STATIONS,
            FORWARD_DISTANCES,
            self.world.battery_range_km,
        )

    def _generate_plans(self) -> list[list[str]]:
        all_plans = self._all_valid_plans()
        min_stops = min(len(p) for p in all_plans)
        two_stop = [p for p in all_plans if len(p) == min_stops]
        return two_stop or all_plans

    def plan_counts(self) -> tuple[int, int]:
        """(all legal plans, plans used for scheduling)."""
        all_plans = self._all_valid_plans()
        used = self._generate_plans()
        return len(all_plans), len(used)

    def _result_shell(
        self,
        scenario: Scenario,
        plans: list[list[str]],
        schedules: list[BusSchedule],
        bus_plans: dict[str, list[str]],
        plan_evaluations: dict[str, list[dict]],
        *,
        scheduler_version: str,
        version_label: str,
        version_name: str,
        charging_mode: str,
        total_wait: int,
        optimization: dict | None,
        metrics: dict | None = None,
    ) -> dict:
        return {
            "schedules": schedules,
            "bus_plans": bus_plans,
            "plan_evaluations": plan_evaluations,
            "conflicts": [],
            "weights": scenario.weights,
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "battery_range_km": self.world.battery_range_km,
            "min_charge_stops": min(len(p) for p in plans) if plans else 0,
            "scheduler_version": scheduler_version,
            "version_label": version_label,
            "version_name": version_name,
            "charging_mode": charging_mode,
            "optimization": optimization,
            "total_fleet_wait_minutes": total_wait,
            "bus_count": len(scenario.buses),
            "metrics": metrics or {},
        }

    def _schedule_v2(
        self,
        scenario: Scenario,
        plans: list[list[str]],
        metrics: dict,
    ) -> dict:
        weights = scenario.weights
        buses = scenario.buses
        sequential = FleetSequentialScheduler(self)
        assignment, schedules, meta, plan_evaluations = (
            sequential.schedule(buses, plans, weights)
        )

        return self._result_shell(
            scenario,
            plans,
            schedules,
            {bid: list(plan) for bid, plan in assignment.items()},
            plan_evaluations,
            scheduler_version=V2_SCHEDULER_VERSION,
            version_label=V2_VERSION_LABEL,
            version_name=V2_VERSION_NAME,
            charging_mode=V2_CHARGING_MODE,
            total_wait=meta["total_wait"],
            optimization={
                "bus_order": meta["bus_order"],
                "fleet_rule_score": meta["rule_score"],
            },
            metrics=metrics,
        )

    def _schedule_v3(
        self,
        scenario: Scenario,
        plans: list[list[str]],
        metrics: dict,
    ) -> dict:
        weights = scenario.weights
        buses = scenario.buses

        optimizer = FleetOptimizer(
            self,
            use_delta_eval=self.use_delta_eval,
        )
        opt_result = optimizer.optimize(buses, plans, weights)
        metrics = {
            **metrics,
            "plans_evaluated": (
                opt_result.full_simulations
                + opt_result.delta_simulations
            ),
        }

        bus_order_name = opt_result.bus_order_name
        bus_order = dict(bus_orders(buses))[bus_order_name]

        plan_evaluations: dict[str, list[dict]] = {}
        for bus in buses:
            plan_evaluations[bus.id] = (
                optimizer.plan_evaluations_for_bus(
                    buses,
                    bus,
                    plans,
                    weights,
                    bus_order,
                    opt_result.assignment,
                )
            )

        return self._result_shell(
            scenario,
            plans,
            opt_result.schedules,
            {
                bid: list(plan)
                for bid, plan in opt_result.assignment.items()
            },
            plan_evaluations,
            scheduler_version=V4_SCHEDULER_VERSION,
            version_label=V4_VERSION_LABEL,
            version_name=V4_VERSION_NAME,
            charging_mode=V4_CHARGING_MODE,
            total_wait=opt_result.metrics.total_wait,
            optimization={
                "bus_order": bus_order_name,
                "iterations": opt_result.iterations,
                "fleet_rule_score": opt_result.metrics.rule_score,
                "max_bus_wait": opt_result.metrics.max_bus_wait,
                "makespan": opt_result.metrics.makespan,
                "full_simulations": opt_result.full_simulations,
                "delta_simulations": opt_result.delta_simulations,
                "evaluation_engine": V4_ENGINE_LABEL,
                "warm_start_used": opt_result.warm_start_used,
                "baseline_wait": opt_result.baseline_wait,
                "optimized_wait": opt_result.optimized_wait,
                "safety_fallback": opt_result.safety_fallback,
            },
            metrics=metrics,
        )

    def schedule_scenario(
        self,
        scenario: Scenario,
        plans: list[list[str]] | None = None,
        mode: ScheduleMode = "v2",
    ) -> dict:
        plans = plans or self._generate_plans()
        generated, used = self.plan_counts()
        metrics: dict = {
            "buses": len(scenario.buses),
            "plans_generated": generated,
            "plans_used": used,
            "mode": mode,
        }

        t0 = time.perf_counter()
        if mode == "v3":
            result = self._schedule_v3(scenario, plans, metrics)
        else:
            result = self._schedule_v2(scenario, plans, metrics)

        elapsed = round(time.perf_counter() - t0, 4)
        if mode == "v2":
            result["metrics"]["scheduler_runtime_seconds"] = elapsed
        else:
            result["metrics"]["optimizer_runtime_seconds"] = elapsed
        return result
