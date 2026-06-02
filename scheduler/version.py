"""Scheduler version labels (V2 default, V3 optional, V4 internal)."""

# Version 2 — default
V2_SCHEDULER_VERSION = "2"
V2_VERSION_LABEL = "Version 2"
V2_VERSION_NAME = "Fleet Scheduler"
V2_CHARGING_MODE = "v2_fleet_sequential"

# Version 3 — optional global optimization
V3_SCHEDULER_VERSION = "3"
V3_VERSION_LABEL = "Version 3"
V3_VERSION_NAME = "Global Fleet Optimization"
V3_CHARGING_MODE = "v3_global_fleet"

# Version 4 — warm-start from V2 + global search + delta evaluation
V4_SCHEDULER_VERSION = "4"
V4_VERSION_LABEL = "Version 4"
V4_VERSION_NAME = "Warm-start + Delta Evaluation"
V4_ENGINE_LABEL = "Warm-start + Delta evaluation"
V4_CHARGING_MODE = "v4_warm_start_delta"
