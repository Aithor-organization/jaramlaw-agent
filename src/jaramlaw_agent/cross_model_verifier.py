"""최종 리포트 독립 검증 게이트.

두 층으로 되어 있다:

  1. **결정론 검사** (아래 함수들) — 예산 초과, 안전 신호인데 사람 검토 없음,
     인용 필드 누락 같은 구조적 결함. 모델 없이 코드가 판단한다.
  2. **적대적 비평가** (`adversarial_critic`) — 다른 회사의 모델이 부모가 읽을
     답변 자체를 물어뜯는다. 결정론 검사가 절대 못 잡는 것(환각 인용, 승소 단정)을 잡는다.

이 파일의 이름은 원래 cross-model이었지만 실제로는 다른 모델을 부르지 않는
if-체인이었다. 이제는 진짜로 부른다.
"""

from __future__ import annotations

from typing import Any, Optional

from .models import FinalReport


def run_independent_validation(
    report: FinalReport,
    *,
    model_routing: dict[str, Any],
    budget_guard: dict[str, Any],
    critic_verdict: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    # 적대적 비평가의 판정을 **결정론 검사와 같은 등급으로** 취급한다.
    # 이전 구현은 비평 결과를 리포트 옆에 적어만 뒀다 — BLOCK이 PASS와 아무 차이가 없었다.
    if critic_verdict:
        verdict = str(critic_verdict.get("verdict") or "")
        if verdict == "BLOCK":
            findings.append({
                "severity": "block",
                "code": "adversarial_critic_block",
                "message": critic_verdict.get("summary") or "독립 비평가가 답변을 차단했다",
                "critic_model": critic_verdict.get("model"),
                "critic_findings": critic_verdict.get("findings", [])[:6],
            })
        elif verdict == "WARN":
            findings.append({
                "severity": "warn",
                "code": "adversarial_critic_warn",
                "message": critic_verdict.get("summary") or "독립 비평가가 결함을 지적했다",
                "critic_model": critic_verdict.get("model"),
                "critic_findings": critic_verdict.get("findings", [])[:6],
            })
        elif verdict == "UNAVAILABLE":
            # 검증을 못 했다는 사실을 숨기지 않는다. 검증된 것처럼 보이면 그게 더 위험하다.
            findings.append({
                "severity": "warn",
                "code": "adversarial_critic_unavailable",
                "message": f"독립 비평가를 호출하지 못했다 ({critic_verdict.get('error')}) — 답변은 교차 검증되지 않았다",
            })

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
