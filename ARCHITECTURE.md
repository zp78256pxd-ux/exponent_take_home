# Architecture & Trade-offs (Submission Notes)

This project is intentionally engineered like a **product-ready system**, not a one-off “solve this instance optimally at any cost”.

Yes, this problem is small enough that an “optimal” approach (MIP / CP-SAT) could work *today*. We chose **not** to lead with that because:

- **Debuggability & explainability** matter more than theoretical optimality in an interview + real ops.
- Optimization solvers add **new failure modes** (infeasible models, tuning, constraints bugs) that are hard to reason about quickly.
- The goal here is a design that **scales in requirements**, not just in math.

So the architecture favors:
- clear hard constraints (planner),
- clean shared resource modelling (calendar),
- tunable business goals (rule engine),
- and an optional optimizer layer that never regresses the baseline (Version 4).

---

## Data model trade-offs (`data/config/*.json`, `data/scenarios/*.json`)

### `data/config/routes.json`
- **Decision**: Represent the route as explicit **directed edges** (`from`, `to`, `distance_km`), not a single “bidirectional” flag.
- **Trade-off**:
  - ✅ Supports asymmetric distances/times and one-way segments later.
  - ✅ Keeps route behaviour explicit and testable.
  - ❌ Slightly more verbose config.

### `data/config/world.json`
- **Decision**: Keep battery range, charging time, and speed as **global parameters**.
- **Trade-off**:
  - ✅ Simple: all buses behave the same (matches assignment).
  - ✅ No duplication in each bus object.
  - ❌ If you later introduce bus types (different ranges/speeds), you’d move these fields onto the bus model.

### `data/config/stations.json`
- **Decision**: Store stations as `{id, chargers}` (single-int capacity).
- **Trade-off**:
  - ✅ Matches “one charger per station” problem cleanly.
  - ✅ Easy extension to multi-charger stations later.
  - ❌ Doesn’t model per-charger details (power, status, maintenance).

### `data/config/operators.json`
- **Decision**: Keep operators lightweight (id/name).
- **Trade-off**:
  - ✅ Avoid premature complexity.
  - ✅ Still supports operator-based weighting/fairness rules.
  - ❌ If later you need priority tiers or contracts, you’d extend this config.

### `data/scenarios/scenario_*.json`
- **Decision**: Scenario owns **weights** (individual/operator/overall).
- **Trade-off**:
  - ✅ Each scenario is a different “business objective profile”.
  - ✅ Same world + route can be evaluated under different priorities.
  - ❌ You must keep weights and context fields aligned (rule extensions require context fields).

---

## Scheduler versioning trade-offs (what each version optimizes for)

| Version | Module(s) | Decision style | Why it exists | UI |
|---------|-----------|----------------|---------------|----|
| **V2 (default)** | `scheduler/fleet_sequential.py` | Incremental (commit bus-by-bus) | Fast, predictable, easy to debug | “Run Standard Scheduler” |
| **V4 (optional)** | `scheduler/fleet_optimizer.py` | Warm-start + local search | Lower fleet wait without risking regression | “Run Fleet Optimization” |

Notes:
- V3 is a historical stepping-stone (global search without warm-start safety).
- V4 includes delta evaluation (suffix replay) as a performance optimization.

**Future (docs only): Multi-seed** — run the same local search from a few deterministic starting assignments (V2 + structured seeds) and keep the best. No randomness; avoids full \(3^N\).

---

## File-by-file trade-offs (why each file exists)

### `scheduler/models.py`
- **Decision**: Use dataclasses for domain objects (Bus, Station, Route, Schedule).
- **Trade-off**:
  - ✅ Stronger invariants than raw dicts; easier refactors.
  - ✅ Cleaner function signatures.
  - ❌ Slightly more boilerplate than dict-based scripting.

### `scheduler/loader.py`
- **Decision**: Centralize JSON → model parsing.
- **Trade-off**:
  - ✅ Keeps IO out of business logic.
  - ✅ Makes scheduler pure / testable (inputs are typed objects).
  - ❌ More files, but much cleaner boundaries.

### `scheduler/utils.py`
- **Decision**: Keep time conversion in one place, including overnight formatting.
- **Trade-off**:
  - ✅ Prevents subtle UI/time bugs everywhere else.
  - ✅ Small edge-case handling (`+1d`) improves realism.

### `scheduler/planner.py`
- **Decision**: Enumerate legal plans (small station count) instead of heavy optimization.
- **Trade-off**:
  - ✅ Hard constraints are enforced cleanly and deterministically.
  - ✅ Easy to explain: “these plans are legal; scheduler chooses among them”.
  - ❌ If stations grow large, you’d move to graph search / pruning.

### `scheduler/fleet_calendar.py`
- **Decision**: Model charger capacity as “pump free after time T” per station.
- **Trade-off**:
  - ✅ Very debuggable and deterministic.
  - ✅ Makes charger contention explicit.
  - ❌ Not a full discrete-event simulator; it’s a planning calendar (by design).

### `scheduler/charging.py`
- **Decision**: Keep charge duration policy in one function (`full_charge_minutes`).
- **Trade-off**:
  - ✅ Enforces the assignment rule (25 min full charge) consistently.
  - ✅ Clear hook for future “top-up” policies without touching scheduler logic.

### `scheduler/context_builder.py`
- **Decision**: Build rule evaluation contexts in one place (bus + fleet).
- **Trade-off**:
  - ✅ Removes duplication and prevents drift between V2/V4.
  - ✅ Makes adding new rule inputs explicit (one place to update).

### `scheduler/rule_engine.py`
- **Decision**: Open for extension: rules live in `RULE_DEFINITIONS`; engine loops dynamically.
- **Trade-off**:
  - ✅ Adding a rule is “add Rule + add weight field + add to list”.
  - ✅ Explainability preserved via `evaluate_breakdown`.
  - ❌ Context inputs must be supplied by context_builder (intended).

### `scheduler/fleet_sequential.py` (V2)
- **Decision**: Baseline scheduler is incremental and deterministic.
- **Trade-off**:
  - ✅ Production-friendly default.
  - ✅ Easy to reason about why a bus chose a plan (local decision).
  - ❌ Not globally optimal: early decisions can constrain later buses.

### `scheduler/fleet_optimizer.py` (V4)
- **Decision**: Warm-start from V2 and then refine with local search + delta evaluation.
- **Trade-off**:
  - ✅ Improves fleet wait on hard scenarios.
  - ✅ **Safety floor**: never worse than V2 wait.
  - ✅ Delta evaluation reduces recomputation cost.
  - ❌ Still heuristic (not guaranteed global optimum), but high quality with explainable steps.

### `scheduler/scheduler.py`
- **Decision**: Single entrypoint with mode switch (`v2` vs optimizer path).
- **Trade-off**:
  - ✅ Keeps UI and callers simple.
  - ✅ Central place to attach metadata/metrics.
  - ❌ Needs discipline to keep logic thin (delegates to V2/V4 modules).

### `scheduler/timeline_builder.py`
- **Decision**: UI formatting separated from scheduling decisions.
- **Trade-off**:
  - ✅ Prevents “presentation logic” from contaminating the scheduler.
  - ✅ Easier to change tables without touching scheduling.

### `scheduler/explainer.py`
- **Decision**: Decision-oriented narrative by default; diagnostics behind a toggle.
- **Trade-off**:
  - ✅ Fast to understand in <30s.
  - ✅ Deep dive available without overwhelming the viewer.

### `app.py`
- **Decision**: Streamlit is a pragmatic demo UI.
- **Trade-off**:
  - ✅ Great for interview demos: inputs → run → timelines.
  - ✅ Makes V2 vs V4 trade-off tangible (wait vs compute).
  - ❌ Not “production UI”, but perfect for take-home.

### `tests/`
- **Decision**: Keep lightweight script-style tests.
- **Trade-off**:
  - ✅ Zero framework dependency required to execute them.
  - ❌ Not as strict as a real pytest suite; sufficient for submission sanity checks.