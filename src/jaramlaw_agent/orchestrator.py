"""orchestrator — 14노드 workflow runner.

Multi-Agent Board 패턴: 5 에이전트 독립 검토 (board_opinions).
Constitution 5원칙 강제 + audit log 생성.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Optional

from . import DISCLAIMER
from .audit import write_audit_log
from .calendar_gen import generate_calendar
from .document_drafter import draft_documents_for_scenario
from .family_context import build_family_profile
from .guard import run_guard
from .human_review import determine_human_review
from .law_retrieval import retrieve_matched_laws
from .models import (
    CalendarOutput,
    DraftDocument,
    FamilyProfile,
    FinalReport,
    HumanReviewSection,
    LawArticle,
    RightsCard,
    SafetyRouting,
    SupportMatch,
    VerifierResults,
)
from .rights_card import generate_rights_cards
from .support_matching import match_supports
from .verifier import collect_atomic_claims, verify_claims


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "family-legal-jaramlaw.workflow.yaml"


def _board_opinions(
    profile: FamilyProfile,
    matched_laws: list[LawArticle],
    supports: list[SupportMatch],
    draft_docs: list[DraftDocument],
) -> dict[str, Any]:
    """5 에이전트 독립 검토 (deterministic 정리)."""
    # contrarian-verifier — citation_gap / overreach / missing_exception 휴리스틱
    findings = []
    for law in matched_laws:
        if not law.effective_date:
            findings.append({
                "severity": "warning", "category": "citation_gap",
                "statement": f"{law.law_name} {law.article}에 시행일 누락",
                "evidence": law.law_id,
            })
        if law.exceptions:
            findings.append({
                "severity": "info", "category": "missing_exception",
                "statement": f"{law.law_name} {law.article} 예외 존재: {law.exceptions}",
                "evidence": law.law_id,
            })

    if not findings:
        findings.append({
            "severity": "info", "category": "ok",
            "statement": "주요 인용 조문 모두 완전한 citation 보유.",
            "evidence": "all",
        })

    contrarian_verdict = "PASS"
    if any(f["severity"] == "critical" for f in findings):
        contrarian_verdict = "BLOCK"
    elif any(f["severity"] == "warning" for f in findings):
        contrarian_verdict = "NEEDS_WORK"

    return {
        "law_retrieval_agent": {
            "matched_count": len(matched_laws),
            "top_laws": [f"{l.law_name} {l.article}" for l in matched_laws[:5]],
        },
        "family_context_agent": {
            "life_stages": profile.life_stages,
            "flags": profile.flags,
        },
        "support_matching_agent": {
            "matched_count": len(supports),
            "imminent": [s.name for s in supports if s.deadline_days_left is not None and s.deadline_days_left <= 30],
        },
        "document_drafter_agent": {
            "drafts_count": len(draft_docs),
            "kinds": [d.kind for d in draft_docs],
        },
        "contrarian_verifier": {
            "findings": findings,
            "verdict": contrarian_verdict,
            "recommendations": [
                "사용자에게 'unverifiable' claim 별도 강조 권장",
                "vault citation 누락 발생 시 시드 보강 후속",
            ],
        },
    }


def run_workflow(
    raw_input: dict[str, Any],
    scenario_id: Optional[str] = None,
    seed_laws_dir: Optional[Path] = None,
    seed_supports_dir: Optional[Path] = None,
    workflow_path: Optional[Path] = None,
    write_audit: bool = True,
) -> FinalReport:
    """14노드 워크플로우 실행 → FinalReport.

    노드 순서:
      1. intake (raw_input 직접 수신)
      2. input_guard (guard.py)
      3. (safety triggered ? safety_routing 분기)
      4. family_context
      5. law_retrieval
      6. support_matching
      7. parallel_expert_board (5 에이전트)
      8. document_drafter
      9. verify_atomic_claims
      10. human_review_gate
      11. rights_card_gen
      12. calendar_gen
      13. freshness_monitor (skip — MVP)
      14. audit_log → final_report
    """
    workflow_path = workflow_path or DEFAULT_WORKFLOW_PATH

    # Node 1-2: intake + guard
    guard_result = run_guard(raw_input)
    redacted = guard_result.redacted_input
    safety = guard_result.safety_routing

    # Node 4: family_context (safety triggered여도 프로필은 계산 — 보고서 일관성)
    profile = build_family_profile(redacted)

    # safety triggered → 일반 워크플로우 우회, safety_routing 노드로 직행
    if safety.triggered:
        human = determine_human_review(
            verifier_results=None,
            safety_routing=safety,
            scenario_type=redacted.get("scenario", {}).get("type"),
        )

        report = FinalReport(
            family_profile=profile,
            life_stages=profile.life_stages,
            matched_laws=[],
            support_matches=[],
            rights_cards=[],
            calendar=None,
            draft_documents=[],
            verifier_results=None,
            safety_routing=safety,
            human_review=human,
            disclaimer=DISCLAIMER,
            scenario_id=scenario_id,
        )
        if write_audit:
            report.audit_log_id = write_audit_log(report)
        return report

    # Node 5: law_retrieval
    scenario_obj = redacted.get("scenario", {}) or {}
    scenario_query = scenario_obj.get("query", "")
    persona_hint = redacted.get("persona") or scenario_obj.get("persona")
    matched_laws = retrieve_matched_laws(
        family_profile=profile,
        scenario_query=scenario_query,
        persona_hint=persona_hint,
        top_k=15,
        seed_dir=seed_laws_dir,
    )

    # Node 6: support_matching
    supports = match_supports(profile, seed_dir=seed_supports_dir)

    # Node 8: document_drafter
    scenario_type = scenario_obj.get("type")
    scenario_data = scenario_obj.get("data", {}) or {}
    draft_docs = draft_documents_for_scenario(
        scenario_type=scenario_type or "general",
        profile=profile,
        scenario_data=scenario_data,
        laws=matched_laws,
    )

    # Node 11: rights_card_gen
    rights_cards = generate_rights_cards(matched_laws, profile)

    # Node 12: calendar_gen
    calendar_out = generate_calendar(profile)

    # Node 7: parallel_expert_board (board_opinions)
    board = _board_opinions(profile, matched_laws, supports, draft_docs)

    # Node 9: verify_atomic_claims
    claims = collect_atomic_claims(matched_laws, supports, rights_cards, draft_docs)
    verifier_results = verify_claims(claims)

    # Node 10: human_review_gate
    human = determine_human_review(
        verifier_results=verifier_results,
        safety_routing=safety,
        scenario_type=scenario_type,
    )

    # Node 14: audit_log + final_report
    report = FinalReport(
        family_profile=profile,
        life_stages=profile.life_stages,
        matched_laws=matched_laws,
        support_matches=supports,
        rights_cards=rights_cards,
        calendar=calendar_out,
        draft_documents=draft_docs,
        verifier_results=verifier_results,
        safety_routing=safety,
        human_review=human,
        disclaimer=DISCLAIMER,
        scenario_id=scenario_id,
    )

    # board_opinions를 별도 dict로 audit log에 포함
    report.__dict__["board_opinions"] = board

    if write_audit:
        report.audit_log_id = write_audit_log(report)
    return report
