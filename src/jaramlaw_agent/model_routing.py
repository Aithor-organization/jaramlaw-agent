"""Deterministic model routing and role isolation metadata.

JaramLaw currently runs without external LLM calls. This module still makes the
agent routing contract explicit: each workflow role receives a tier, a model
family label, and an isolation group that can be enforced before a future model
backend is attached.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from .models import SafetyRouting


HIGH_RISK_SCENARIOS = {
    "daycare_accident",
    "school_violence",
    "cyber_bullying",
    "child_support_unpaid",
    "divorce_custody",
}

STANDARD_SCENARIOS = {
    "academy_refund",
    "parental_leave",
}


@dataclass(frozen=True)
class RoleAssignment:
    role: str
    tier: str
    model_family: str
    isolation_group: str
    reason: str
    max_input_chars: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_criticality(
    redacted_input: dict[str, Any],
    safety_routing: Optional[SafetyRouting] = None,
) -> str:
    """Classify the workflow depth without looking at domain-specific outcome."""
    scenario = redacted_input.get("scenario") if isinstance(redacted_input, dict) else {}
    scenario = scenario if isinstance(scenario, dict) else {}
    scenario_type = str(scenario.get("type") or "general")
    query = str(scenario.get("query") or "")

    if safety_routing and safety_routing.triggered:
        return "critical"
    if scenario_type in HIGH_RISK_SCENARIOS:
        return "critical"
    if len(query) > 1800:
        return "deep"
    if scenario_type in STANDARD_SCENARIOS:
        return "standard"
    return "shallow"


def build_role_assignments(criticality: str) -> list[RoleAssignment]:
    """Return a stable routing plan with writer/verifier isolation."""
    base = [
        RoleAssignment(
            role="router",
            tier="shallow",
            model_family="deterministic-router",
            isolation_group="route",
            reason="input classification and workflow selection",
            max_input_chars=3000,
        ),
        RoleAssignment(
            role="law_retrieval_agent",
            tier="standard",
            model_family="deterministic-retrieval",
            isolation_group="retrieval",
            reason="retrieve seed legal anchors",
            max_input_chars=6000,
        ),
        RoleAssignment(
            role="document_drafter_agent",
            tier="standard",
            model_family="deterministic-drafter",
            isolation_group="writer",
            reason="produce structured draft documents",
            max_input_chars=8000,
        ),
        RoleAssignment(
            role="contrarian_verifier",
            tier="deep",
            model_family="deterministic-verifier",
            isolation_group="verifier",
            reason="challenge overreach, missing exceptions, and citation gaps",
            max_input_chars=8000,
        ),
        RoleAssignment(
            role="atomic_claim_verifier",
            tier="deep",
            model_family="deterministic-verifier",
            isolation_group="verifier",
            reason="verify citation completeness for every atomic claim",
            max_input_chars=8000,
        ),
        RoleAssignment(
            role="independent_validator",
            tier="critical",
            model_family="deterministic-independent-review",
            isolation_group="independent-validation",
            reason="validate final report after writer/verifier loop",
            max_input_chars=12000,
        ),
    ]

    if criticality == "shallow":
        return base[:4]
    if criticality == "standard":
        return base[:5]
    return base


def validate_model_assignments(assignments: list[RoleAssignment]) -> dict[str, Any]:
    """Enforce role isolation before the workflow proceeds."""
    by_role = {item.role: item for item in assignments}
    findings: list[dict[str, str]] = []

    writer = by_role.get("document_drafter_agent")
    verifier = by_role.get("atomic_claim_verifier") or by_role.get("contrarian_verifier")
    independent = by_role.get("independent_validator")

    if writer and verifier and writer.isolation_group == verifier.isolation_group:
        findings.append({
            "severity": "block",
            "code": "writer_verifier_not_isolated",
            "message": "writer and verifier share an isolation group",
        })

    if independent and verifier and independent.isolation_group == verifier.isolation_group:
        findings.append({
            "severity": "block",
            "code": "validator_not_independent",
            "message": "independent validator must not share verifier isolation",
        })

    return {
        "status": "BLOCK" if any(item["severity"] == "block" for item in findings) else "PASS",
        "findings": findings,
    }


def plan_model_routing(
    redacted_input: dict[str, Any],
    safety_routing: Optional[SafetyRouting] = None,
) -> dict[str, Any]:
    criticality = classify_criticality(redacted_input, safety_routing)
    assignments = build_role_assignments(criticality)
    guard = validate_model_assignments(assignments)
    return {
        "routing_version": "jaramlaw-model-routing/v1",
        "criticality": criticality,
        "execution_mode": "deterministic-local",
        "external_model_calls": False,
        "assignments": [item.to_dict() for item in assignments],
        "model_guard": guard,
    }
