"""Local budget guard for agent routing plans.

The guard estimates cost from model-route tiers even when the current runtime is
deterministic. This gives UI and audit logs the same operational contract that a
future paid model backend would need.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Optional


TIER_ESTIMATES_USD = {
    "shallow": 0.001,
    "standard": 0.004,
    "deep": 0.009,
    "critical": 0.018,
}


# 1,000토큰당 USD. **기본값은 비어 있다 — 이게 의도한 동작이다.**
#
# gpt-5.6-luna/sol/terra의 실제 단가를 우리는 모른다. 모르는 값을 그럴듯한 상수로 채우면
# 감사 로그에 "비용 $0.004"라고 찍히고, 그 숫자는 검증된 적이 없는데도 사실처럼 읽힌다.
# 그래서 단가를 아는 사람이 넣기 전까지는 USD를 만들어내지 않고 토큰만 보고한다.
#
#   JARAMLAW_MODEL_PRICES='{"gpt-5.6-luna": {"in": 0.001, "out": 0.004}}'
def _load_prices() -> dict[str, dict[str, float]]:
    raw = os.environ.get("JARAMLAW_MODEL_PRICES")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


MODEL_PRICES_USD_PER_1K: dict[str, dict[str, float]] = _load_prices()


def actual_usage_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> dict[str, Any]:
    """실제로 쓴 토큰을 기록한다. 단가를 알 때만 USD를 계산한다.

    cached_tokens는 OpenAI가 자동 재사용한 입력분이다. 같은 법령 컨텍스트가 반복되면
    입력 토큰의 대부분이 여기로 잡힌다 (실측: 반복 질의에서 3,887/3,890 = 100%).
    과금은 통상 캐시분에 할인이 붙으므로, 캐시를 빼지 않으면 비용을 과대 계상한다.
    """
    billable_input = max(0, prompt_tokens - cached_tokens)
    usage: dict[str, Any] = {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "billable_input_tokens": billable_input,
        "completion_tokens": completion_tokens,
        "cache_hit_ratio": round(cached_tokens / prompt_tokens, 3) if prompt_tokens else 0.0,
    }

    price = MODEL_PRICES_USD_PER_1K.get(model)
    if not price:
        usage["pricing_known"] = False
        usage["cost_usd"] = None
        usage["note"] = f"{model} 단가 미설정 — JARAMLAW_MODEL_PRICES로 주입하면 USD를 계산한다"
        return usage

    cost = (billable_input / 1000.0) * float(price.get("in", 0.0)) + (
        completion_tokens / 1000.0
    ) * float(price.get("out", 0.0))
    usage["pricing_known"] = True
    usage["cost_usd"] = round(cost, 6)
    return usage


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
