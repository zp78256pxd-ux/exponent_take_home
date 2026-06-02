"""
Version 3 — global fleet assignment optimization (heuristic search).

Version 4 — warm-start from V2 baseline, then coordinate descent and
pairwise swaps; delta evaluation for suffix replay; never worse than V2 wait.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from scheduler.context_builder import build_bus_context, build_fleet_context
from scheduler.models import Bus, BusSchedule, Weights
from scheduler.rule_engine import RuleEngine


@dataclass(frozen=True)
class FleetMetrics:
    total_wait: int
    max_bus_wait: int
    makespan: int
    operator_waits: dict[str, int]
    rule_score: float


@dataclass
class FleetOptimizationResult:
    assignment: dict[str, list[str]]
    schedules: list[BusSchedule]
    metrics: FleetMetrics
    bus_order_name: str
    iterations: int
    full_simulations: int = 0
    delta_simulations: int = 0
    use_delta_eval: bool = True
    warm_start_used: bool = False
    baseline_wait: int = 0
    optimized_wait: int = 0
    safety_fallback: bool = False


def plan_key(plan: list[str]) -> tuple[str, ...]:
    return tuple(plan)


def bus_orders(buses: list[Bus]) -> list[tuple[str, list[Bus]]]:
    forward = sorted(
        [b for b in buses if b.direction.value == "forward"],
        key=lambda b: b.departure_time_minutes,
    )
    reverse = sorted(
        [b for b in buses if b.direction.value == "reverse"],
        key=lambda b: b.departure_time_minutes,
    )
    by_dep = sorted(buses, key=lambda b: b.departure_time_minutes)
    return [
        ("forward_then_reverse", forward + reverse),
        ("reverse_then_forward", reverse + forward),
        ("by_departure", by_dep),
    ]


def objective_key(
    metrics: FleetMetrics,
    weights: Weights | None = None,
) -> tuple:
    """Lower is better. Total wait first; operator-heavy scenarios break ties earlier."""
    operator_max = (
        max(metrics.operator_waits.values())
        if metrics.operator_waits
        else 0
    )
    if weights is not None and weights.operator > weights.individual:
        return (
            metrics.total_wait,
            operator_max,
            metrics.max_bus_wait,
            -metrics.rule_score,
            metrics.makespan,
        )
    return (
        metrics.total_wait,
        metrics.max_bus_wait,
        -metrics.rule_score,
        metrics.makespan,
    )


class FleetOptimizer:
    def __init__(
        self,
        scheduler: object,
        use_delta_eval: bool = True,
    ):
        self._scheduler = scheduler
        self.use_delta_eval = use_delta_eval
        self._full_simulations = 0
        self._delta_simulations = 0

    def _order_index(
        self,
        bus_order: list[Bus],
    ) -> dict[str, int]:
        return {bus.id: i for i, bus in enumerate(bus_order)}

    def _build_prefix(
        self,
        bus_order: list[Bus],
        assignment: dict[str, list[str]],
        through_index: int,
    ) -> tuple[list[BusSchedule], object]:
        from scheduler.fleet_calendar import FleetCalendar

        calendar = FleetCalendar(self._scheduler._station_ids)
        schedules: list[BusSchedule] = []
        for bus in bus_order[:through_index]:
            schedule = self._scheduler._simulate_plan_on_calendar(
                bus,
                assignment[bus.id],
                calendar,
            )
            schedules.append(schedule)
        return schedules, calendar

    def _metrics_from_schedules(
        self,
        schedules: list[BusSchedule],
        buses: list[Bus],
        weights: Weights,
    ) -> FleetMetrics:
        context = build_fleet_context(schedules, buses)
        operator_waits: dict[str, int] = defaultdict(int)
        bus_by_id = {b.id: b for b in buses}
        for schedule in schedules:
            operator_waits[
                bus_by_id[schedule.bus_id].operator
            ] += schedule.total_wait_time
        return FleetMetrics(
            total_wait=context["wait_time"],
            max_bus_wait=max(
                (s.total_wait_time for s in schedules),
                default=0,
            ),
            makespan=context["network_delay"],
            operator_waits=dict(operator_waits),
            rule_score=RuleEngine(weights).evaluate(context),
        )

    def simulate_fleet_suffix(
        self,
        buses: list[Bus],
        assignment: dict[str, list[str]],
        bus_order: list[Bus],
        weights: Weights,
        from_index: int,
        prefix_schedules: list[BusSchedule],
        prefix_calendar,
    ) -> tuple[list[BusSchedule], FleetMetrics]:
        from scheduler.fleet_calendar import FleetCalendar

        self._delta_simulations += 1
        calendar = prefix_calendar.copy()
        schedules = list(prefix_schedules)
        for bus in bus_order[from_index:]:
            schedule = self._scheduler._simulate_plan_on_calendar(
                bus,
                assignment[bus.id],
                calendar,
            )
            schedules.append(schedule)
        return schedules, self._metrics_from_schedules(
            schedules,
            buses,
            weights,
        )

    def simulate_fleet_at(
        self,
        buses: list[Bus],
        assignment: dict[str, list[str]],
        bus_order: list[Bus],
        weights: Weights,
        from_index: int = 0,
    ) -> tuple[list[BusSchedule], FleetMetrics]:
        if from_index <= 0 or not self.use_delta_eval:
            return self.simulate_fleet(
                buses,
                assignment,
                bus_order,
                weights,
            )
        prefix_schedules, prefix_calendar = self._build_prefix(
            bus_order,
            assignment,
            from_index,
        )
        return self.simulate_fleet_suffix(
            buses,
            assignment,
            bus_order,
            weights,
            from_index,
            prefix_schedules,
            prefix_calendar,
        )

    def simulate_fleet(
        self,
        buses: list[Bus],
        assignment: dict[str, list[str]],
        bus_order: list[Bus],
        weights: Weights,
    ) -> tuple[list[BusSchedule], FleetMetrics]:
        self._full_simulations += 1
        from scheduler.fleet_calendar import FleetCalendar

        calendar = FleetCalendar(self._scheduler._station_ids)
        schedules: list[BusSchedule] = []

        for bus in bus_order:
            plan = assignment[bus.id]
            schedule = self._scheduler._simulate_plan_on_calendar(
                bus,
                plan,
                calendar,
            )
            schedules.append(schedule)

        metrics = self._metrics_from_schedules(
            schedules,
            buses,
            weights,
        )
        return schedules, metrics

    def greedy_assignment(
        self,
        buses: list[Bus],
        plans: list[list[str]],
        weights: Weights,
        bus_order: list[Bus],
    ) -> dict[str, list[str]]:
        default = plans[0]
        assignment = {bus.id: list(default) for bus in buses}
        _, best_metrics = self.simulate_fleet(
            buses,
            assignment,
            bus_order,
            weights,
        )
        best_key = objective_key(best_metrics, weights)

        order_index = self._order_index(bus_order)
        for bus in bus_order:
            chosen = assignment[bus.id]
            from_idx = order_index[bus.id]
            for plan in plans:
                if plan_key(plan) == plan_key(chosen):
                    continue
                trial = {
                    bid: list(assignment[bid])
                    for bid in assignment
                }
                trial[bus.id] = list(plan)
                _, metrics = self.simulate_fleet_at(
                    buses,
                    trial,
                    bus_order,
                    weights,
                    from_idx,
                )
                key = objective_key(metrics, weights)
                if key < best_key:
                    best_key = key
                    chosen = list(plan)
            assignment[bus.id] = chosen

        return assignment

    def coordinate_descent(
        self,
        buses: list[Bus],
        plans: list[list[str]],
        weights: Weights,
        bus_order: list[Bus],
        assignment: dict[str, list[str]],
    ) -> tuple[dict[str, list[str]], list[BusSchedule], FleetMetrics, int]:
        assignment = {
            bid: list(assignment[bid]) for bid in assignment
        }
        schedules, metrics = self.simulate_fleet(
            buses,
            assignment,
            bus_order,
            weights,
        )
        best_key = objective_key(metrics, weights)
        iterations = 0
        order_index = self._order_index(bus_order)

        improved = True
        while improved:
            improved = False
            for bus in buses:
                current = assignment[bus.id]
                from_idx = order_index[bus.id]
                for plan in plans:
                    if plan_key(plan) == plan_key(current):
                        continue
                    trial = {
                        bid: list(assignment[bid])
                        for bid in assignment
                    }
                    trial[bus.id] = list(plan)
                    trial_schedules, trial_metrics = (
                        self.simulate_fleet_at(
                            buses,
                            trial,
                            bus_order,
                            weights,
                            from_idx,
                        )
                    )
                    trial_key = objective_key(
                        trial_metrics,
                        weights,
                    )
                    iterations += 1
                    if trial_key < best_key:
                        assignment = trial
                        schedules = trial_schedules
                        metrics = trial_metrics
                        best_key = trial_key
                        improved = True
                        current = list(plan)

        return assignment, schedules, metrics, iterations

    def pairwise_swap_search(
        self,
        buses: list[Bus],
        plans: list[list[str]],
        weights: Weights,
        bus_order: list[Bus],
        assignment: dict[str, list[str]],
        schedules: list[BusSchedule],
        metrics: FleetMetrics,
    ) -> tuple[
        dict[str, list[str]],
        list[BusSchedule],
        FleetMetrics,
        int,
    ]:
        assignment = {
            bid: list(assignment[bid]) for bid in assignment
        }
        best_key = objective_key(metrics, weights)
        swaps = 0
        order_index = self._order_index(bus_order)

        improved = True
        while improved:
            improved = False
            for i, bus_a in enumerate(buses):
                for bus_b in buses[i + 1 :]:
                    trial = {
                        bid: list(assignment[bid])
                        for bid in assignment
                    }
                    trial[bus_a.id], trial[bus_b.id] = (
                        list(assignment[bus_b.id]),
                        list(assignment[bus_a.id]),
                    )
                    if plan_key(trial[bus_a.id]) == plan_key(
                        assignment[bus_a.id]
                    ) and plan_key(trial[bus_b.id]) == plan_key(
                        assignment[bus_b.id]
                    ):
                        continue
                    from_idx = min(
                        order_index[bus_a.id],
                        order_index[bus_b.id],
                    )
                    trial_schedules, trial_metrics = (
                        self.simulate_fleet_at(
                            buses,
                            trial,
                            bus_order,
                            weights,
                            from_idx,
                        )
                    )
                    trial_key = objective_key(
                        trial_metrics,
                        weights,
                    )
                    swaps += 1
                    if trial_key < best_key:
                        assignment = trial
                        schedules = trial_schedules
                        metrics = trial_metrics
                        best_key = trial_key
                        improved = True

        return assignment, schedules, metrics, swaps

    def _v2_baseline(
        self,
        buses: list[Bus],
        plans: list[list[str]],
        weights: Weights,
    ) -> tuple[dict[str, list[str]], list[BusSchedule], int]:
        from scheduler.fleet_sequential import FleetSequentialScheduler

        assignment, schedules, meta, _ = FleetSequentialScheduler(
            self._scheduler
        ).schedule(buses, plans, weights)
        return assignment, schedules, meta["total_wait"]

    def optimize(
        self,
        buses: list[Bus],
        plans: list[list[str]],
        weights: Weights,
    ) -> FleetOptimizationResult:
        baseline_assignment, baseline_schedules, baseline_wait = (
            self._v2_baseline(buses, plans, weights)
        )
        warm_start = {
            bid: list(plan) for bid, plan in baseline_assignment.items()
        }

        best_assignment: dict[str, list[str]] | None = None
        best_schedules: list[BusSchedule] | None = None
        best_metrics: FleetMetrics | None = None
        best_order_name = ""
        best_key: tuple | None = None
        total_iterations = 0
        self._full_simulations = 0
        self._delta_simulations = 0

        for order_name, bus_order in bus_orders(buses):
            assignment = {
                bid: list(warm_start[bid]) for bid in warm_start
            }
            assignment, schedules, metrics, iters = (
                self.coordinate_descent(
                    buses,
                    plans,
                    weights,
                    bus_order,
                    assignment,
                )
            )
            total_iterations += iters

            assignment, schedules, metrics, swap_iters = (
                self.pairwise_swap_search(
                    buses,
                    plans,
                    weights,
                    bus_order,
                    assignment,
                    schedules,
                    metrics,
                )
            )
            total_iterations += swap_iters

            key = objective_key(metrics, weights)
            if best_key is None or key < best_key:
                best_key = key
                best_assignment = assignment
                best_schedules = schedules
                best_metrics = metrics
                best_order_name = order_name

        assert best_assignment is not None
        assert best_schedules is not None
        assert best_metrics is not None

        optimized_wait = best_metrics.total_wait
        safety_fallback = optimized_wait > baseline_wait

        if safety_fallback:
            baseline_metrics = self._metrics_from_schedules(
                baseline_schedules,
                buses,
                weights,
            )
            return FleetOptimizationResult(
                assignment=baseline_assignment,
                schedules=baseline_schedules,
                metrics=baseline_metrics,
                bus_order_name="forward_then_reverse",
                iterations=total_iterations,
                full_simulations=self._full_simulations,
                delta_simulations=self._delta_simulations,
                use_delta_eval=self.use_delta_eval,
                warm_start_used=True,
                baseline_wait=baseline_wait,
                optimized_wait=optimized_wait,
                safety_fallback=True,
            )

        return FleetOptimizationResult(
            assignment=best_assignment,
            schedules=best_schedules,
            metrics=best_metrics,
            bus_order_name=best_order_name,
            iterations=total_iterations,
            full_simulations=self._full_simulations,
            delta_simulations=self._delta_simulations,
            use_delta_eval=self.use_delta_eval,
            warm_start_used=True,
            baseline_wait=baseline_wait,
            optimized_wait=optimized_wait,
            safety_fallback=False,
        )

    def plan_evaluations_for_bus(
        self,
        buses: list[Bus],
        bus: Bus,
        plans: list[list[str]],
        weights: Weights,
        bus_order: list[Bus],
        base_assignment: dict[str, list[str]],
    ) -> list[dict]:
        engine = RuleEngine(weights)
        evaluations: list[dict] = []
        from_idx = self._order_index(bus_order)[bus.id]

        for plan in plans:
            trial = {
                bid: list(base_assignment[bid])
                for bid in base_assignment
            }
            trial[bus.id] = list(plan)
            schedules, metrics = self.simulate_fleet_at(
                buses,
                trial,
                bus_order,
                weights,
                from_idx,
            )
            schedule = next(
                s for s in schedules if s.bus_id == bus.id
            )
            bus_ctx = build_bus_context(
                schedule,
                metrics.operator_waits.get(bus.operator, 0),
                bus.departure_time_minutes,
            )
            evaluations.append(
                {
                    "plan": list(plan),
                    "score": engine.evaluate(bus_ctx),
                    "context": bus_ctx,
                    "schedule": schedule,
                    "wait_time": schedule.total_wait_time,
                    "fleet_total_wait": metrics.total_wait,
                }
            )

        return evaluations
