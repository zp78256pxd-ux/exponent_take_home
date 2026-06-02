"""Decision-oriented schedule explanations (output only; no scheduler changes)."""

from __future__ import annotations

from collections import defaultdict

from scheduler.models import BusSchedule, Weights
from scheduler.rule_engine import RULE_DEFINITIONS, RuleEngine
from scheduler.utils import minutes_to_time
from scheduler.version import V2_VERSION_LABEL, V2_VERSION_NAME, V3_VERSION_LABEL


def _plan_label(plan: list[str]) -> str:
    if not plan:
        return "direct"
    return " → ".join(plan)


def _station_wait_totals(
    schedules: list[BusSchedule],
) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for schedule in schedules:
        for event in schedule.charging_events:
            totals[event.station] += event.wait_time
    return dict(totals)


def _station_activity_counts(
    schedules: list[BusSchedule],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for schedule in schedules:
        for event in schedule.charging_events:
            counts[event.station] += 1
    return dict(counts)


def explain_rules(weights: Weights) -> str:
    """Full rule table — intended for diagnostics only."""
    lines = [
        "## Rules Used",
        "",
        "Weighted scoring (higher total score is better):",
        "",
        "| Rule | Weight | Input | Goal |",
        "|------|--------|-------|------|",
    ]

    for rule in RULE_DEFINITIONS:
        weight = getattr(weights, rule.name, 0)
        lines.append(
            f"| **{rule.name}** | {weight} "
            f"| −{rule.context_key} | {rule.description} |"
        )

    lines.extend(
        [
            "",
            "**Combined score** = "
            f"({weights.individual} × individual) + "
            f"({weights.operator} × operator) + "
            f"({weights.overall} × overall)",
        ]
    )
    return "\n".join(lines)


def _format_breakdown(
    engine: RuleEngine,
    context: dict,
) -> str:
    breakdown = engine.evaluate_breakdown(context)
    parts = []
    for item in breakdown["components"]:
        parts.append(
            f"{item['rule']}={item['weighted_score']:.1f} "
            f"(−{item['input_value']} × {item['weight']})"
        )
    parts.append(f"**total={breakdown['total']:.1f}**")
    return ", ".join(parts)


def _rank_evaluations(evaluations: list[dict]) -> list[dict]:
    return sorted(
        evaluations,
        key=lambda item: (
            item.get("fleet_total_wait", item["context"]["wait_time"]),
            item.get("wait_time", item["context"]["wait_time"]),
            -item["score"],
        ),
    )


def _selection_reason(
    winner: dict,
    runner_up: dict | None,
) -> str:
    if runner_up is None:
        return (
            "Best option among feasible plans for this bus "
            "given the fleet calendar and range limits."
        )

    w_fleet = winner.get("fleet_total_wait")
    r_fleet = runner_up.get("fleet_total_wait")
    alt_plan = _plan_label(runner_up["plan"])

    if (
        w_fleet is not None
        and r_fleet is not None
        and r_fleet > w_fleet
    ):
        return (
            f"Reduced fleet wait by {r_fleet - w_fleet} min "
            f"compared to {alt_plan}."
        )

    w_wait = winner["context"]["wait_time"]
    r_wait = runner_up["context"]["wait_time"]
    if r_wait > w_wait:
        return (
            f"Reduced this bus's charger wait by {r_wait - w_wait} min "
            f"compared to {alt_plan}."
        )

    if winner["score"] > runner_up["score"]:
        return (
            f"Better match for scenario weights than {alt_plan} "
            f"at similar wait."
        )

    return f"Preferred over {alt_plan} on fleet-wide tie-breakers."


def _selection_impact(
    winner: dict,
    busiest_station: str | None,
) -> str:
    plan = winner.get("plan") or []
    bus_wait = winner["context"]["wait_time"]

    if bus_wait == 0:
        return "Arrives when the charger is free — no queue at this stop."

    if plan and busiest_station and plan[0] != busiest_station:
        return (
            f"First stop is {plan[0]}, spreading load away from "
            f"the busiest station ({busiest_station})."
        )

    if plan and busiest_station and plan[0] == busiest_station:
        return (
            f"Uses station {busiest_station} early; wait absorbed "
            f"to protect later legs."
        )

    return "Keeps this bus within range while limiting fleet-wide delay."


def explain_plan_selection(
    bus_id: str,
    evaluations: list[dict],
    weights: Weights,
    show_debug: bool = False,
    busiest_station: str | None = None,
) -> str:
    if not evaluations:
        return f"No charging plans evaluated for **{bus_id}**."

    ranked = _rank_evaluations(evaluations)
    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None

    if not show_debug:
        lines = [
            f"### {bus_id}",
            "",
            f"**Selected:** {_plan_label(winner['plan'])}",
            "",
            f"**Reason:** {_selection_reason(winner, runner_up)}",
            "",
            f"**Impact:** {_selection_impact(winner, busiest_station)}",
        ]
        return "\n".join(lines)

    engine = RuleEngine(weights)
    lines = [
        f"### {bus_id} (diagnostics)",
        "",
        f"**Selected:** `{_plan_label(winner['plan'])}` · "
        f"score **{winner['score']:.1f}**",
        "",
        f"Winner breakdown: {_format_breakdown(engine, winner['context'])}",
        "",
        "**Candidates (fleet context fixed):**",
    ]

    for item in ranked[:2]:
        context = item["context"]
        marker = " ✓" if item is winner else ""
        fleet_w = item.get("fleet_total_wait", "—")
        lines.append(
            f"- `{_plan_label(item['plan'])}` — "
            f"score **{item['score']:.1f}**{marker}  \n"
            f"  fleet wait **{fleet_w} min** · "
            f"bus wait {context['wait_time']} min  \n"
            f"  {_format_breakdown(engine, context)}"
        )

    if len(ranked) > 2:
        lines.append(f"- *{len(ranked) - 2} more plan(s) omitted*")

    return "\n".join(lines)


def explain_conflict(
    conflict: dict,
    weights: Weights,
    show_debug: bool = False,
) -> str:
    bus_id = conflict["bus_id"]
    station = conflict["station"]
    wait = conflict["wait_time"]

    if not show_debug:
        return (
            f"**{bus_id}** waited **{wait} min** at Station **{station}**."
        )

    engine = RuleEngine(weights)
    context = conflict["priority_context"]
    return (
        f"- **{bus_id}** ({conflict['operator']}) at **{station}**: "
        f"waited **{wait} min** "
        f"(arrived {minutes_to_time(conflict['arrival_time'])}, "
        f"charged {minutes_to_time(conflict['charge_start_time'])}).  \n"
        f"  Priority {_format_breakdown(engine, context)}"
    )


def _decision_summary_paragraph(result: dict) -> str:
    version = result.get("scheduler_version", "2")
    weights = result["weights"]

    if version == "3":
        behavior = (
            "A global pass assigned charging plans across the whole fleet "
            "to lower total wait before timetables were fixed."
        )
    else:
        behavior = (
            "Buses were scheduled in departure order on one shared charger "
            "calendar; each bus picked the plan that best fit the fleet "
            "already committed."
        )

    fairness = ""
    if weights.operator > weights.individual:
        fairness = " Operator fairness was weighted more heavily in ties."
    elif weights.overall > weights.individual:
        fairness = " Trip-time balance was weighted more heavily in ties."

    return behavior + fairness


def _key_insights(result: dict) -> list[str]:
    schedules: list[BusSchedule] = result.get("schedules") or []
    insights: list[str] = []

    station_waits = _station_wait_totals(schedules)
    if station_waits:
        busiest = max(station_waits, key=station_waits.get)
        insights.append(
            f"Most loaded station: **{busiest}** "
            f"({station_waits[busiest]} min total wait)"
        )
    else:
        insights.append("Most loaded station: none (no charger waits)")

    if schedules:
        top_bus = max(schedules, key=lambda s: s.total_wait_time)
        if top_bus.total_wait_time > 0:
            insights.append(
                f"Largest wait contributor: **{top_bus.bus_id}** "
                f"({top_bus.total_wait_time} min)"
            )
        else:
            insights.append(
                "Largest wait contributor: none (all buses charged on arrival)"
            )

    if result.get("scheduler_version") == "3":
        insights.append(
            "Optimization: global search applied — compare with "
            "standard scheduler to see wait vs compute tradeoff."
        )
    else:
        insights.append(
            "Optimization: standard incremental scheduler (fast, stable)."
        )

    return insights


def _explain_summary(result: dict) -> str:
    opt = result.get("optimization") or {}
    conflicts = result.get("conflicts") or []
    bus_order = opt.get("bus_order", "forward_then_reverse")

    version_line = result.get("version_label", V2_VERSION_LABEL)
    if result.get("scheduler_version") == "2":
        version_line = f"{V2_VERSION_LABEL} — {V2_VERSION_NAME}"
    elif result.get("scheduler_version") == "3":
        version_line = f"{V3_VERSION_LABEL} — Global Fleet Optimization"

    lines = [
        "## Result Summary",
        "",
        f"**Version:** {version_line}",
        f"**Scenario:** {result.get('scenario_name', result.get('scenario_id', '—'))}",
        f"**Bus count:** {result.get('bus_count', len(result.get('schedules', [])))}",
        f"**Fleet wait:** {result.get('total_fleet_wait_minutes', 0)} min",
        f"**Conflicts:** {len(conflicts)}",
        f"**Bus order:** {bus_order}",
        f"**Mode:** `{result.get('charging_mode', '—')}`",
        "",
        _decision_summary_paragraph(result),
        "",
        "**Key insights:**",
    ]
    lines.extend(f"- {line}" for line in _key_insights(result))
    return "\n".join(lines)


def _explain_decision_highlights(result: dict) -> str:
    weights = result["weights"]
    schedules: list[BusSchedule] = result.get("schedules") or []
    station_waits = _station_wait_totals(schedules)
    busiest = (
        max(station_waits, key=station_waits.get)
        if station_waits
        else None
    )

    parts = ["## Decision Highlights", ""]
    for bus_id, evaluations in result.get("plan_evaluations", {}).items():
        parts.append(
            explain_plan_selection(
                bus_id,
                evaluations,
                weights,
                show_debug=False,
                busiest_station=busiest,
            )
        )
        parts.append("")

    return "\n".join(parts).rstrip()


def _explain_capacity_insights(result: dict) -> str:
    schedules: list[BusSchedule] = result.get("schedules") or []
    station_waits = _station_wait_totals(schedules)
    activity = _station_activity_counts(schedules)

    lines = [
        "## Capacity Insights (Experimental)",
        "",
        "*(Approximate heuristic only — no simulation or prediction.)*",
        "",
    ]

    if not schedules:
        lines.append("No charging activity to analyze.")
        return "\n".join(lines)

    if station_waits:
        utilized = max(station_waits, key=station_waits.get)
        lines.append(
            f"**Most utilized station:** {utilized} "
            f"({station_waits[utilized]} min aggregate wait, "
            f"{activity.get(utilized, 0)} charge visits)"
        )
        bottleneck = utilized
        lines.append(
            f"**Estimated bottleneck:** Station **{bottleneck}** "
            f"(single charger, highest observed queue time)"
        )
        est = max(0, station_waits[bottleneck] // 2)
        lines.append(
            f"**If one charger were added at {bottleneck}:** "
            f"roughly up to **{est} min** less fleet wait "
            f"(heuristic, not measured)"
        )
    else:
        lines.append(
            "**Most utilized station:** No queues observed in this run."
        )
        lines.append(
            "**Estimated bottleneck:** None under current assignment."
        )
        lines.append(
            "**Extra capacity:** Marginal gain likely small for this scenario."
        )

    return "\n".join(lines)


def _explain_conflicts_section(
    result: dict,
    weights: Weights,
    show_debug: bool,
) -> str:
    conflicts = result.get("conflicts") or []
    lines = ["## Conflict Summary", ""]

    if not conflicts:
        lines.append("No charger conflicts recorded for this schedule.")
        return "\n".join(lines)

    for conflict in conflicts:
        lines.append(explain_conflict(conflict, weights, show_debug))
    return "\n".join(lines)


def _explain_diagnostics(result: dict) -> str:
    weights = result["weights"]
    opt = result.get("optimization") or {}
    parts = [
        "## Diagnostics",
        "",
        explain_rules(weights),
        "",
    ]

    if opt:
        parts.extend(
            [
                "### Run metadata",
                "",
                f"- Bus order: `{opt.get('bus_order', '—')}`",
                f"- Iterations: {opt.get('iterations', '—')}",
                f"- Evaluation engine: {opt.get('evaluation_engine', '—')}",
                f"- Full simulations: {opt.get('full_simulations', '—')}",
                f"- Delta simulations: {opt.get('delta_simulations', '—')}",
                "",
            ]
        )

    metrics = result.get("metrics") or {}
    if metrics:
        parts.append("### Metrics snapshot")
        parts.append("")
        for key, value in metrics.items():
            parts.append(f"- {key}: {value}")
        parts.append("")

    schedules: list[BusSchedule] = result.get("schedules") or []
    station_waits = _station_wait_totals(schedules)
    busiest = (
        max(station_waits, key=station_waits.get)
        if station_waits
        else None
    )

    parts.append("### Per-bus plan diagnostics")
    parts.append("")
    for bus_id, evaluations in result.get("plan_evaluations", {}).items():
        parts.append(
            explain_plan_selection(
                bus_id,
                evaluations,
                weights,
                show_debug=True,
                busiest_station=busiest,
            )
        )
        parts.append("")

    conflicts = result.get("conflicts") or []
    if conflicts:
        parts.extend(["### Conflict diagnostics", ""])
        for conflict in conflicts:
            parts.append(
                explain_conflict(conflict, weights, show_debug=True)
            )

    return "\n".join(parts).rstrip()


def explain_scenario_result(result: dict) -> list[str]:
    """Multi-level explanation: summary and highlights by default; diagnostics optional."""
    show_debug = result.get("show_debug") is True
    weights = result["weights"]

    sections = [
        _explain_summary(result),
        "",
        _explain_decision_highlights(result),
        "",
        _explain_capacity_insights(result),
        "",
        _explain_conflicts_section(result, weights, show_debug=False),
    ]

    if show_debug:
        sections.extend(["", _explain_diagnostics(result)])

    return sections
