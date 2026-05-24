"""Local budget guard for agent routing plans.

The guard estimates cost from model-route tiers even when the current runtime is
deterministic. This gives UI and audit logs the same operational contract that a
future paid model backend would need.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any


TIER_ESTIMATES_USD = {
    "shallow": 0.001,
    "standard": 0.004,
    "deep": 0.009,
    "critical": 0.018,
}


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    estimated_cost_usd: float
    per_run_limit_usd: float
    monthly_limit_usd: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["estimated_cost_usd"] = round(self.estimated_cost_usd, 6)
        return data


class BudgetGuard:
    def __init__(self, *, per_run_limit_usd: float = 0.25, monthly_limit_usd: float = 25.0) -> None:
        self.per_run_limit_usd = per_run_limit_usd
        self.monthly_limit_usd = monthly_limit_usd

    @classmethod
    def from_env(cls) -> "BudgetGuard":
        return cls(
            per_run_limit_usd=_env_float("JARAMLAW_PER_RUN_BUDGET_USD", 0.25),
            monthly_limit_usd=_env_float("JARAMLAW_MONTHLY_BUDGET_USD", 25.0),
        )

    def authorize(self, routing_plan: dict[str, Any]) -> BudgetDecision:
        estimated = estimate_plan_cost(routing_plan)
        allowed = estimated <= self.per_run_limit_usd
        return BudgetDecision(
            allowed=allowed,
            estimated_cost_usd=estimated,
            per_run_limit_usd=self.per_run_limit_usd,
            monthly_limit_usd=self.monthly_limit_usd,
            reason="within per-run budget" if allowed else "estimated model cost exceeds per-run budget",
        )


def estimate_plan_cost(routing_plan: dict[str, Any]) -> float:
    assignments = routing_plan.get("assignments", [])
    if not isinstance(assignments, list):
        return 0.0
    total = 0.0
    for item in assignments:
        if not isinstance(item, dict):
            continue
        total += TIER_ESTIMATES_USD.get(str(item.get("tier") or "shallow"), TIER_ESTIMATES_USD["shallow"])
    return round(total, 6)


def _env_float(name: str, fallback: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return fallback
    try:
        return float(raw)
    except ValueError:
        return fallback
