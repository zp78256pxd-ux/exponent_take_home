import sys
import os

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

from scheduler.models import Weights
from scheduler.rule_engine import (
    IndividualRule,
    OperatorRule,
    OverallRule,
    RuleEngine,
)

context = {
    "wait_time": 10,
    "operator_delay": 20,
    "network_delay": 30,
}

print(IndividualRule().score(context))
print(OperatorRule().score(context))
print(OverallRule().score(context))

engine = RuleEngine(
    Weights(individual=1.0, operator=1.0, overall=1.0)
)
print(engine.evaluate(context))
print(engine.evaluate_breakdown(context))
