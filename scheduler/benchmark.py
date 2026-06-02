"""Fleet-wide timing benchmarks for the Metrics UI."""

from __future__ import annotations

import time
from pathlib import Path

from scheduler.loader import load_scenario
from scheduler.scheduler import Scheduler


def run_fleet_benchmark(
    scheduler: Scheduler,
    scenario_paths: list[Path],
) -> dict:
    """Average V2 and V3 runtime across all bundled scenarios."""
    v2_times: list[float] = []
    v3_times: list[float] = []
    bus_counts: list[int] = []

    for path in scenario_paths:
        scenario = load_scenario(str(path))
        bus_counts.append(len(scenario.buses))

        t0 = time.perf_counter()
        scheduler.schedule_scenario(scenario, mode="v2")
        v2_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        scheduler.schedule_scenario(scenario, mode="v3")
        v3_times.append(time.perf_counter() - t0)

    n = len(scenario_paths) or 1
    return {
        "scenario_count": len(scenario_paths),
        "total_buses": sum(bus_counts),
        "avg_buses_per_scenario": round(sum(bus_counts) / n, 1),
        "avg_scheduler_runtime_seconds": round(
            sum(v2_times) / n,
            4,
        ),
        "avg_optimizer_runtime_seconds": round(
            sum(v3_times) / n,
            4,
        ),
    }
