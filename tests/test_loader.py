import sys
import os

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

from scheduler.loader import (
    load_world,
    load_stations,
    load_route,
    load_scenario
)

world = load_world("data/config/world.json")
print(world)

stations = load_stations("data/config/stations.json")
print(stations)

route = load_route("data/config/routes.json")
print(route)

scenario = load_scenario(
    "data/scenarios/scenario_1.json"
)

print(scenario)

print(f"Bus count: {len(scenario.buses)}")
print(f"First bus: {scenario.buses[0]}")