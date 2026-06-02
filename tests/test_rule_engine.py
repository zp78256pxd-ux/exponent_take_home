import sys
import os

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

from scheduler.models import Weights
from scheduler.rule_engine import RuleEngine


context = {
    "wait_time": 10,
    "operator_delay": 20,
    "network_delay": 30
}


print("\nScenario 1")

scenario_1_weights = Weights(
    individual=1.0,
    operator=1.0,
    overall=1.0
)

engine = RuleEngine(
    scenario_1_weights
)

score = engine.evaluate(context)

print(f"Score: {score}")


print("\nScenario 4")

scenario_4_weights = Weights(
    individual=1.0,
    operator=2.0,
    overall=1.0
)

engine = RuleEngine(
    scenario_4_weights
)

score = engine.evaluate(context)

print(f"Score: {score}")