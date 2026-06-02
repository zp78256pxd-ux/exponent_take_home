import json
from pathlib import Path

import pandas as pd
import streamlit as st
from scheduler.explainer import explain_scenario_result
from scheduler.loader import (
    load_route,
    load_scenario,
    load_stations,
    load_world,
)
from scheduler.models import Direction
from scheduler.scheduler import Scheduler
from scheduler.timeline_builder import (
    build_bus_timetable,
    build_station_view,
    build_summary_table,
)
from scheduler.version import (
    V2_VERSION_LABEL,
    V2_VERSION_NAME,
    V4_VERSION_LABEL,
    V4_VERSION_NAME,
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SCENARIO_DIR = DATA / "scenarios"

PAGE_STYLE = """
<style>
    .block-container { padding-top: 1.25rem; padding-bottom: 2rem; }
    .hero {
        padding: 1rem 1.25rem;
        border-radius: 12px;
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0d9488 100%);
        color: #f8fafc;
        margin-bottom: 1.25rem;
    }
    .hero h1 { color: #f8fafc !important; font-size: 1.75rem !important; margin: 0; }
    .hero p { color: #cbd5e1; margin: 0.35rem 0 0 0; font-size: 0.95rem; }
    .run-card {
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem 1.1rem;
        background: #f8fafc;
        min-height: 7.5rem;
    }
    .run-card-opt {
        border-color: #99f6e4;
        background: linear-gradient(180deg, #f0fdfa 0%, #f8fafc 100%);
    }
    .pill {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.35rem;
    }
    .pill-v2 { background: #dbeafe; color: #1e40af; }
    .pill-v4 { background: #ccfbf1; color: #0f766e; }
    div[data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.65rem 0.85rem;
    }
    .section-label {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #64748b;
        margin-bottom: 0.5rem;
    }
</style>
"""


def _format_runtime(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 0.1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"


@st.cache_resource
def load_config():
    world = load_world(str(DATA / "config" / "world.json"))
    route = load_route(str(DATA / "config" / "routes.json"))
    stations = load_stations(str(DATA / "config" / "stations.json"))
    return world, route, stations


def list_scenarios() -> list[Path]:
    return sorted(SCENARIO_DIR.glob("scenario_*.json"))


def load_scenario_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def direction_endpoints(bus) -> tuple[str, str]:
    if bus.direction == Direction.FORWARD:
        return "BLR", "KOC"
    return "KOC", "BLR"


def run_scheduler(mode: str) -> None:
    world, route, stations = load_config()
    scenario_path = st.session_state["selected_scenario_path"]
    scenario = load_scenario(str(scenario_path))
    scheduler = Scheduler(world, route, stations)

    if mode == "v2":
        with st.spinner(f"Running {V2_VERSION_LABEL}…"):
            result = scheduler.schedule_scenario(scenario, mode="v2")
        st.session_state["standard_result"] = result
        st.session_state["result"] = result
        st.session_state.pop("comparison", None)
        st.session_state["schedule_mode"] = "v2"
    else:
        standard = st.session_state.get("standard_result")
        if (
            not standard
            or standard.get("scenario_id") != scenario.id
        ):
            with st.spinner(f"Running {V2_VERSION_LABEL} (baseline)…"):
                standard = scheduler.schedule_scenario(
                    scenario,
                    mode="v2",
                )
            st.session_state["standard_result"] = standard
        with st.spinner(f"Running {V4_VERSION_LABEL}…"):
            optimized = scheduler.schedule_scenario(
                scenario,
                mode="v3",
            )
        st.session_state["result"] = optimized
        st.session_state["comparison"] = {
            "standard": standard,
            "optimized": optimized,
        }
        st.session_state["schedule_mode"] = "v3"

    st.session_state["scenario"] = scenario
    st.session_state["result_scenario_id"] = scenario.id


def render_metrics_panel(result: dict, comparison: dict | None) -> None:
    metrics = result.get("metrics") or {}
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Buses", metrics.get("buses", "—"))
    m2.metric("Legal plans", metrics.get("plans_generated", "—"))
    m3.metric(
        "Run time",
        _format_runtime(
            metrics.get("scheduler_runtime_seconds")
            or metrics.get("optimizer_runtime_seconds")
        ),
    )
    pe = metrics.get("plans_evaluated")
    m4.metric("Plan evals", pe if pe is not None else "—")

    if comparison and st.session_state.get("schedule_mode") == "v3":
        std = comparison["standard"]
        opt = comparison["optimized"]
        sm = std.get("metrics") or {}
        om = opt.get("metrics") or {}
        wait_std = std.get("total_fleet_wait_minutes", 0)
        wait_opt = opt.get("total_fleet_wait_minutes", 0)
        saved = wait_std - wait_opt
        c1, c2, c3 = st.columns(3)
        c1.metric("Standard wait", f"{wait_std} min")
        c2.metric("Optimized wait", f"{wait_opt} min")
        c3.metric(
            "Wait saved",
            f"{saved} min",
            delta=f"{saved} min" if saved > 0 else None,
            delta_color="normal" if saved >= 0 else "inverse",
        )

        std_t = sm.get("scheduler_runtime_seconds")
        opt_t = om.get("optimizer_runtime_seconds")
        ratio = (
            f"{(opt_t / std_t):.0f}× more compute"
            if std_t and opt_t and std_t > 0
            else "—"
        )
        st.caption(
            f"Compute: standard **{_format_runtime(std_t)}** · "
            f"optimization **{_format_runtime(opt_t)}** · {ratio}"
        )

        opt_meta = opt.get("optimization") or {}
        if opt_meta.get("baseline_wait") is not None:
            st.caption(
                f"Warm-start baseline **{opt_meta.get('baseline_wait')} min** → "
                f"after search **{opt_meta.get('optimized_wait')} min** · "
                f"fallback: **{opt_meta.get('safety_fallback', False)}**"
            )


def main():
    st.set_page_config(
        page_title="Bus Charging Scheduler",
        page_icon="🚌",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(PAGE_STYLE, unsafe_allow_html=True)

    world, route, stations = load_config()
    scenario_paths = list_scenarios()
    if not scenario_paths:
        st.error("No scenarios found in data/scenarios/")
        return

    with st.sidebar:
        st.markdown("### Setup")
        labels = [p.stem.replace("_", " ").title() for p in scenario_paths]
        path_by_label = dict(zip(labels, scenario_paths))
        selected_label = st.selectbox("Scenario", labels)
        selected_path = path_by_label[selected_label]
        scenario = load_scenario(str(selected_path))
        scenario_raw = load_scenario_json(selected_path)
        st.session_state["selected_scenario_path"] = selected_path

        if st.session_state.get("result_scenario_id") != scenario.id:
            st.session_state.pop("result", None)
            st.session_state.pop("scenario", None)
            st.session_state.pop("standard_result", None)
            st.session_state.pop("comparison", None)
        st.session_state["selected_scenario_id"] = scenario.id

        st.divider()
        st.markdown("**World**")
        st.metric("Range", f"{world.battery_range_km} km")
        st.metric("Charge", f"{world.charging_time_minutes} min")
        st.metric("Speed", f"{world.speed_kmph} km/h")

        st.divider()
        st.markdown("**Scenario weights**")
        w1, w2, w3 = st.columns(3)
        w1.metric("Bus", scenario.weights.individual)
        w2.metric("Op", scenario.weights.operator)
        w3.metric("Net", scenario.weights.overall)

        st.divider()
        with st.expander("Raw scenario JSON"):
            st.json(scenario_raw)

        # Benchmark intentionally removed from UI for submission.

    st.markdown(
        f"""
        <div class="hero">
            <h1>Bus Charging Scheduler</h1>
            <p>Bengaluru ↔ Kochi · shared charger calendar · 25 min full charge</p>
            <p style="margin-top:0.5rem">
                <span class="pill pill-v2">{V2_VERSION_LABEL}</span>
                <span class="pill pill-v4">{V4_VERSION_LABEL}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<p class="section-label">Scenario · {scenario.name}</p>',
        unsafe_allow_html=True,
    )
    if scenario_raw.get("description"):
        st.caption(scenario_raw["description"])

    st.markdown('<p class="section-label">Run scheduler</p>', unsafe_allow_html=True)
    run_col1, run_col2 = st.columns(2, gap="medium")
    with run_col1:
        st.markdown(
            f'<div class="run-card"><strong>Standard</strong><br>'
            f"<small>{V2_VERSION_LABEL} · {V2_VERSION_NAME}</small><br>"
            f"<small>Fast · deterministic · recommended default</small></div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "Run Standard Scheduler",
            type="primary",
            use_container_width=True,
            key="run_v2",
        ):
            run_scheduler("v2")
            st.rerun()
    with run_col2:
        st.markdown(
            f'<div class="run-card run-card-opt"><strong>Fleet optimization</strong><br>'
            f"<small>{V4_VERSION_LABEL} · {V4_VERSION_NAME}</small><br>"
            f"<small>Warm-start from V2 · may reduce total wait</small></div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "Run Fleet Optimization",
            use_container_width=True,
            key="run_v4",
        ):
            run_scheduler("v3")
            st.rerun()

    if "result" not in st.session_state:
        st.info(
            "Pick a scenario in the sidebar, then run **Standard** or "
            "**Fleet optimization** to build timetables."
        )
        return

    result = st.session_state["result"]
    scenario = st.session_state["scenario"]

    if result.get("scenario_id") != scenario.id:
        st.warning("Results are stale for this scenario — run a scheduler again.")
        return

    schedules = result["schedules"]
    comparison = st.session_state.get("comparison")

    st.divider()
    st.markdown(
        f'<p class="section-label">Results · {result.get("scenario_name", scenario.name)}</p>',
        unsafe_allow_html=True,
    )

    ver = result.get("version_label", "—")
    st.caption(f"{ver} · {result.get('version_name', '')} · `{result.get('charging_mode', '')}`")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Fleet wait", f"{result.get('total_fleet_wait_minutes', 0)} min")
    k2.metric("Buses scheduled", result.get("bus_count", len(schedules)))
    k3.metric("Conflicts", len(result.get("conflicts", [])))
    avg_stops = (
        sum(len(s.route_plan) for s in schedules) / len(schedules)
        if schedules
        else 0
    )
    k4.metric("Avg charge stops", f"{avg_stops:.1f}")

    opt = result.get("optimization") or {}
    if opt.get("iterations") is not None:
        st.caption(
            f"Search · order `{opt.get('bus_order', '—')}` · "
            f"{opt.get('iterations', 0)} steps · {opt.get('evaluation_engine', '—')}"
        )

    st.markdown('<p class="section-label">Run metrics</p>', unsafe_allow_html=True)
    render_metrics_panel(result, comparison)

    tab_summary, tab_bus, tab_station, tab_explain = st.tabs(
        [
            "Fleet summary",
            "Per bus",
            "Per station",
            "Explainer",
        ]
    )

    summary_df = pd.DataFrame(build_summary_table(schedules))

    with tab_summary:
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
        )

    departure_times = {
        bus.id: bus.departure_time_minutes for bus in scenario.buses
    }
    endpoints = {
        bus.id: direction_endpoints(bus) for bus in scenario.buses
    }
    timetables = build_bus_timetable(
        schedules,
        departure_times,
        endpoints,
    )

    with tab_bus:
        bus_ids = [s.bus_id for s in schedules]
        left, right = st.columns([1, 3])
        with left:
            selected_bus = st.selectbox("Bus", bus_ids, key="bus_select")
            plan = next(
                s.route_plan for s in schedules if s.bus_id == selected_bus
            )
            st.markdown(f"**Plan:** `{' → '.join(plan) or 'direct'}`")
            wait = next(
                s.total_wait_time
                for s in schedules
                if s.bus_id == selected_bus
            )
            st.metric("Bus wait", f"{wait} min")
        with right:
            rows = timetables[selected_bus]
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Event": row.event,
                            "Station": row.station,
                            "Start": row.start_time,
                            "End": row.end_time,
                            "Duration (min)": row.duration_minutes,
                            "Wait (min)": row.wait_minutes or 0,
                        }
                        for row in rows
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

    with tab_station:
        station_view = build_station_view(schedules)
        station_ids = sorted(station_view.keys()) or ["A", "B", "C", "D"]
        st_cols = st.columns(len(station_ids))
        for col, sid in zip(st_cols, station_ids):
            rows = station_view.get(sid, [])
            total_wait = sum(r.wait_minutes for r in rows)
            col.metric(f"Station {sid}", f"{len(rows)} visits")
            col.caption(f"{total_wait} min wait")

        selected_station = st.selectbox(
            "Detail station",
            station_ids,
            key="station_select",
        )
        rows = station_view.get(selected_station, [])
        if rows:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Bus": r.bus_id,
                            "Arrival": r.arrival_time,
                            "Charge start": r.charge_start_time,
                            "Charge end": r.charge_end_time,
                            "Wait (min)": r.wait_minutes,
                        }
                        for r in rows
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success(f"No charging at station {selected_station}.")

    with tab_explain:
        show_debug = st.checkbox(
            "Show diagnostics (scores & candidate plans)",
            value=False,
            key="explainer_show_debug",
        )
        explain_input = {**result, "show_debug": show_debug}
        for section in explain_scenario_result(explain_input):
            st.markdown(section)


if __name__ == "__main__":
    main()
