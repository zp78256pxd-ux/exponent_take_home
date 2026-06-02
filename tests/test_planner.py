# test_planner.py


import sys
import os

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

from scheduler.planner import generate_valid_plans

stations = ["A", "B", "C", "D"]

distances = [
    100,  # Bengaluru -> A
    120,  # A -> B
    100,  # B -> C
    120,  # C -> D
    100   # D -> Kochi
]

plans = generate_valid_plans(
    stations,
    distances,
    battery_range=240
)

for plan in plans:
    print(plan)

print(f"\nTotal Plans: {len(plans)}")