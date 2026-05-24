"""Independent final-report validation gate.

The name mirrors cross-model verification, but the current implementation is a
deterministic independent reviewer. It is isolated from drafting and retrieval
roles through the model routing metadata.
"""

from __future__ import annotations

from typing import Any

from .models import FinalReport


def run_independent_validation(
    report: FinalReport,
    *,
    model_routing: dict[str, Any],
    budget_guard: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    guard_status = _nested(model_routing, "model_guard", "status")
    if guard_status == "BLOCK":
        findings.append({
            "severity": "block",
            "code": "model_guard_blocked",
            "message": "model routing guard reported a blocked assignment",
        })

    if budget_guard and budget_guard.get("allowed") is False:
        findings.append({
            "severity": "block",
            "code": "budget_exceeded",
            "message": budget_guard.get("reason") or "budget guard denied the workflow",
        })

    if report.safety_routing and report.safety_routing.triggered:
        if not report.human_review or not report.human_review.needed:
            findings.append({
                "severity": "block",
                "code": "safety_without_human_review",
                "message": "safety routing triggered without human review",
            })
        return _result(findings, validator_role="independent_validator")

    if not report.verifier_results:
        findings.append({
            "severity": "warn",
            "code": "missing_verifier_results",
            "message": "final report has no verifier results",
        })
    else:
        verifier = report.verifier_results
        if verifier.unverifiable_count > 0:
            findings.append({
                "severity": "block",
                "code": "unverifiable_claims",
                "message": f"{verifier.unverifiable_count} claims remain unverifiable",
            })
        if verifier.partial_count > 0:
            findings.append({
                "severity": "warn",
                "code": "partial_claims",
                "message": f"{verifier.partial_count} claims have partial citations",
            })
        if verifier.verified_ratio < 0.8:
            findings.append({
                "severity": "warn",
                "code": "low_verified_ratio",
                "message": f"verified ratio is {verifier.verified_ratio}",
            })

    if not report.matched_laws:
        findings.append({
            "severity": "warn",
            "code": "no_law_matches",
            "message": "no law matches were attached to the final report",
        })

    incomplete_laws = [
        law.law_id
        for law in report.matched_laws
        if not (law.law_name and law.article and law.effective_date and law.source_url)
    ]
    if incomplete_laws:
        findings.append({
            "severity": "warn",
            "code": "incomplete_law_citations",
            "message": "some law records are missing citation fields",
            "law_ids": incomplete_laws[:8],
        })

    if report.draft_documents and not any(doc.legal_basis for doc in report.draft_documents):
        findings.append({
            "severity": "warn",
            "code": "drafts_without_legal_basis",
            "message": "draft documents exist without legal basis references",
        })

    return _result(findings, validator_role="independent_validator")


def _result(findings: list[dict[str, Any]], *, validator_role: str) -> dict[str, Any]:
    if any(item.get("severity") == "block" for item in findings):
        status = "BLOCK"
    elif findings:
        status = "WARN"
    else:
        status = "PASS"
    return {
        "validation_version": "jaramlaw-independent-validation/v1",
        "validator_role": validator_role,
        "status": status,
        "findings": findings,
    }


def _nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
