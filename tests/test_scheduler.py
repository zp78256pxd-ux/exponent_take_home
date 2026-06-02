import sys
import os

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

from scheduler.loader import (
    load_world,
    load_route,
    load_scenario,
    load_stations,
)
from scheduler.scheduler import Scheduler

world = load_world("data/config/world.json")
route = load_route("data/config/routes.json")
stations = load_stations("data/config/stations.json")
scenario = load_scenario("data/scenarios/scenario_1.json")

scheduler = Scheduler(world, route, stations)
result = scheduler.schedule_scenario(scenario)

print(f"Schedules: {len(result['schedules'])}")
print(f"Conflicts: {len(result['conflicts'])}")
for schedule in result["schedules"][:3]:
    print(schedule)
