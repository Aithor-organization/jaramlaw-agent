"""orchestrator — 14노드 workflow runner.

Multi-Agent Board 패턴: 5 에이전트 독립 검토 (board_opinions).
Constitution 5원칙 강제 + audit log 생성.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Optional

from . import DISCLAIMER
from .agent_topology import summarize_team_topology
from .audit import write_audit_log
from .budget_guard import BudgetGuard
from .calendar_gen import generate_calendar
from .cross_model_verifier import run_independent_validation
from .document_drafter import draft_documents_for_scenario
from .family_context import build_family_profile
from .guard import run_guard
from .human_review import determine_human_review
from .law_live import LiveLawEnricher
from .law_retrieval import retrieve_matched_laws
from .memory_rag import JaramLawMemoryRAG
from .openai_client import OpenAiClient
from .model_routing import plan_model_routing
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
from .observability import WorkflowTracer
from .rights_card import generate_rights_cards
from .support_matching import match_supports
from .verifier import collect_atomic_claims, verify_claims_with_retry


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
    enable_live_law: bool = True,
    live_law_budget_s: float = 12.0,
    enable_ai_answer: bool = True,
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
    tracer = WorkflowTracer()
    memory = JaramLawMemoryRAG()
    tracer.trace(
        "workflow_start",
        scenario_id=scenario_id,
        workflow_path=str(workflow_path),
        write_audit=write_audit,
    )

    # Node 1-2: intake + guard
    guard_result = run_guard(raw_input)
    redacted = guard_result.redacted_input
    safety = guard_result.safety_routing
    tracer.trace(
        "input_guard",
        safety_triggered=safety.triggered,
        safety_category=safety.category,
        injection_detected=guard_result.injection_detected,
        notes_count=len(guard_result.notes),
    )

    model_routing = plan_model_routing(redacted, safety)
    model_routing["team_topology"] = summarize_team_topology()
    budget_guard = BudgetGuard.from_env().authorize(model_routing).to_dict()
    memory_context = memory.recall(redacted)
    tracer.trace(
        "model_routing",
        criticality=model_routing.get("criticality"),
        assignments=len(model_routing.get("assignments", [])),
        guard_status=model_routing.get("model_guard", {}).get("status"),
    )
    tracer.trace(
        "budget_guard",
        allowed=budget_guard.get("allowed"),
        estimated_cost_usd=budget_guard.get("estimated_cost_usd"),
    )
    tracer.trace(
        "memory_recall",
        matches=len(memory_context.get("matches", [])),
        record_count=memory_context.get("record_count"),
    )

    # Node 4: family_context (safety triggered여도 프로필은 계산 — 보고서 일관성)
    profile = build_family_profile(redacted)
    tracer.trace(
        "family_context",
        parents=len(profile.parents),
        children=len(profile.children),
        flags=profile.flags,
        life_stages=profile.life_stages,
    )

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
            model_routing=model_routing,
            budget_guard=budget_guard,
            memory_context=memory_context,
            # 안전 차단은 '조회 실패'가 아니라 '조회를 하지 않기로 한 결정'이다.
            # 이걸 구분하지 않으면 화면에 조회 실패 경고가 뜬다.
            law_source={"mode": "blocked", "live_count": 0, "errors": []},
            ai_answer={"mode": "blocked", "text": "", "used_laws": 0},
        )
        report.independent_validation = run_independent_validation(
            report,
            model_routing=model_routing,
            budget_guard=budget_guard,
        )
        tracer.trace(
            "independent_validation",
            status=report.independent_validation.get("status"),
            findings=len(report.independent_validation.get("findings", [])),
        )
        capture = memory.capture_outcome(report) if write_audit else {"captured": False, "reason": "audit_disabled"}
        report.memory_context = {**memory_context, "capture": capture}
        tracer.trace("memory_capture", captured=capture.get("captured"))
        report.trace_summary = tracer.summary()
        if write_audit:
            report.audit_log_id = write_audit_log(report)
            tracer.trace("audit_log", audit_log_id=report.audit_log_id)
            tracer.export()
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
    tracer.trace("law_retrieval", matched_laws=len(matched_laws))

    # Node 5-bis: 법제처 실시간 보강 (조문 원문 / 시행일 / 출처주소).
    # 여기서 얻은 값이 아래 문서초안·권리카드·인용검증에 그대로 흘러간다.
    # 네트워크가 죽어도 상담은 끝까지 가야 하므로 예외를 밖으로 내보내지 않는다.
    law_source: dict[str, Any] = {"mode": "seed", "live_count": 0, "errors": []}
    if enable_live_law and matched_laws:
        try:
            status = LiveLawEnricher(total_budget_s=live_law_budget_s).enrich(matched_laws)
            law_source = asdict(status)
        except Exception as exc:  # noqa: BLE001 — 무대에서 죽는 것보다 시드로 계속하는 게 낫다
            law_source["errors"] = [f"{type(exc).__name__}: {exc}"]
    tracer.trace(
        "law_live_enrich",
        mode=law_source.get("mode"),
        live_count=law_source.get("live_count", 0),
    )

    # Node 6: support_matching
    supports = match_supports(profile, seed_dir=seed_supports_dir)
    tracer.trace("support_matching", support_matches=len(supports))

    # Node 8: document_drafter
    scenario_type = scenario_obj.get("type")
    scenario_data = scenario_obj.get("data", {}) or {}
    draft_docs = draft_documents_for_scenario(
        scenario_type=scenario_type or "general",
        profile=profile,
        scenario_data=scenario_data,
        laws=matched_laws,
    )
    tracer.trace("document_drafter", draft_documents=len(draft_docs), scenario_type=scenario_type)

    # Node 11: rights_card_gen
    rights_cards = generate_rights_cards(matched_laws, profile)
    tracer.trace("rights_card_gen", rights_cards=len(rights_cards))

    # Node 12: calendar_gen
    calendar_out = generate_calendar(profile)
    tracer.trace("calendar_gen", calendar_events=len(calendar_out.events if calendar_out else []))

    # Node 7: parallel_expert_board (board_opinions)
    board = _board_opinions(profile, matched_laws, supports, draft_docs)
    tracer.trace("parallel_expert_board", board_agents=len(board))

    # Node 9: verify_atomic_claims
    claims = collect_atomic_claims(matched_laws, supports, rights_cards, draft_docs)
    verifier_results = verify_claims_with_retry(claims)
    tracer.trace(
        "verify_atomic_claims",
        claims=len(claims),
        verified=verifier_results.verified_count,
        partial=verifier_results.partial_count,
        unverifiable=verifier_results.unverifiable_count,
        attempts=verifier_results.retry_summary.get("attempts_used"),
    )

    # Node 9-bis: 안내 답변 생성 (생성형 AI).
    # 근거로 넘기는 법령은 '인용 4요소(법령명/조문/시행일/출처주소)를 모두 갖춘 것'뿐이다.
    # 보류된 인용은 애초에 AI 눈에 보이지 않으므로 화면에도 나갈 수 없다.
    ai_answer: dict[str, Any] = {"mode": "rule", "text": "", "used_laws": 0}
    if enable_ai_answer and scenario_query and not safety.triggered:
        citable = [
            law for law in matched_laws
            if law.law_name and law.article and law.effective_date and law.source_url
        ]
        ai_answer["citable_laws"] = len(citable)
        ai_answer["withheld_laws"] = len(matched_laws) - len(citable)
        client = OpenAiClient(timeout=25.0)
        if client.enabled() and citable:
            answer = client.ask(
                user_question=scenario_query,
                matched_laws=citable,
                family_context_summary=f"life_stages={profile.life_stages}, flags={profile.flags}",
            )
            if answer.error:
                ai_answer["error"] = answer.error
            else:
                ai_answer.update({
                    "mode": "llm",
                    "text": answer.text,
                    "model": answer.model,
                    "citations": answer.citations,
                    "total_tokens": answer.total_tokens,
                    "used_laws": len(citable),
                })
        elif not client.enabled():
            ai_answer["error"] = "OPENAI_API_KEY 미설정"
    tracer.trace("ai_answer", mode=ai_answer.get("mode"), used_laws=ai_answer.get("used_laws", 0))

    # Node 10: human_review_gate
    human = determine_human_review(
        verifier_results=verifier_results,
        safety_routing=safety,
        scenario_type=scenario_type,
    )
    tracer.trace("human_review_gate", needed=human.needed)

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
        board_opinions=board,
        model_routing=model_routing,
        budget_guard=budget_guard,
        memory_context=memory_context,
        law_source=law_source,
        ai_answer=ai_answer,
    )

    # Final governance gates run after all writer/reviewer outputs are attached.
    report.independent_validation = run_independent_validation(
        report,
        model_routing=model_routing,
        budget_guard=budget_guard,
    )
    tracer.trace(
        "independent_validation",
        status=report.independent_validation.get("status"),
        findings=len(report.independent_validation.get("findings", [])),
    )
    capture = memory.capture_outcome(report) if write_audit else {"captured": False, "reason": "audit_disabled"}
    report.memory_context = {**memory_context, "capture": capture}
    tracer.trace("memory_capture", captured=capture.get("captured"))
    report.trace_summary = tracer.summary()

    if write_audit:
        report.audit_log_id = write_audit_log(report)
        tracer.trace("audit_log", audit_log_id=report.audit_log_id)
        tracer.export()
    return report
