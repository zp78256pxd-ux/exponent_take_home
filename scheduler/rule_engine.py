from abc import ABC, abstractmethod

from scheduler.models import Weights


class Rule(ABC):
    name: str
    description: str
    context_key: str

    @abstractmethod
    def score(self, context: dict) -> float:
        pass


class IndividualRule(Rule):
    name = "individual"
    description = "Minimize per-bus waiting time at chargers"
    context_key = "wait_time"

    def score(self, context: dict) -> float:
        return -context.get(self.context_key, 0)


class OperatorRule(Rule):
    name = "operator"
    description = "Minimize cumulative delay for the bus operator"
    context_key = "operator_delay"

    def score(self, context: dict) -> float:
        return -context.get(self.context_key, 0)


class OverallRule(Rule):
    name = "overall"
    description = "Minimize network-wide trip completion time"
    context_key = "network_delay"

    def score(self, context: dict) -> float:
        return -context.get(self.context_key, 0)


RULE_DEFINITIONS = [
    IndividualRule(),
    OperatorRule(),
    OverallRule(),
]


class RuleEngine:
    def __init__(self, weights: Weights):
        self.weights = weights
        self._rules = RULE_DEFINITIONS

    def evaluate(self, context: dict) -> float:
        return self.evaluate_breakdown(context)["total"]

    def evaluate_breakdown(self, context: dict) -> dict:
        components = []
        total = 0.0

        for rule in self._rules:
            weight = getattr(self.weights, rule.name, 0)
            raw = rule.score(context)
            weighted = weight * raw
            total += weighted
            components.append(
                {
                    "rule": rule.name,
                    "description": rule.description,
                    "weight": weight,
                    "raw_score": raw,
                    "weighted_score": weighted,
                    "input_value": context.get(rule.context_key, 0),
                }
            )

        return {"components": components, "total": total}
