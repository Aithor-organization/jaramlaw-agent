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
from .adversarial_critic import critique_answer
from .agent_topology import summarize_team_topology
from .agentshield_bridge import (
    inspect_input_payload,
    inspect_output_text,
    status as agentshield_status,
)
from .audit import write_audit_log
from .budget_guard import BudgetGuard, actual_usage_cost
from .calendar_gen import generate_calendar
from .cross_model_verifier import run_independent_validation
from .document_drafter import draft_documents_for_scenario
from .family_context import build_family_profile
from .guard import augment_safety_with_llm, run_guard
from .human_review import determine_human_review
from .law_live import LiveLawEnricher
from . import learning
from .law_retrieval import retrieve_matched_laws
from .memory_rag import JaramLawMemoryRAG
from .openai_client import OpenAiClient
from .model_routing import plan_model_routing, select_model
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
    parse_effective_date,
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
    enable_safety_llm: bool = True,
    enable_learning: bool = True,
    enable_critic: bool = True,
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

    # Node 2-bis: AgentShield 입력 가드.
    #
    # 로컬 guard는 인젝션 패턴 6개와 PII 3종(주민번호·휴대폰·주소)만 본다. 실측해보니
    # "이전의 모든 지시를 무시하고"(띄어쓰기 변형), "i g n o r e ..."(난독화), 중국어
    # 인젝션이 전부 통과했고, 이메일·카드·여권·계좌는 마스킹조차 되지 않았다.
    #
    # 여기서 두 가지를 **실제로** 한다: 마스킹된 payload를 아래로 흘려보내고(원본 replay 금지),
    # 인젝션이면 상담을 멈춘다(주석만 달고 통과시키지 않는다).
    # 단, 학대/응급 등 안전 신호가 이미 잡힌 입력은 인젝션 의심이어도 차단하지 않는다 —
    # 신고하려는 부모를 단어 하나로 막지 않기 위함(safety_triggered 전달).
    shield_input = inspect_input_payload(redacted, safety_triggered=safety.triggered)
    redacted = shield_input.sanitized_payload
    shield_report: dict[str, Any] = {
        "status": agentshield_status(),
        "input": shield_input.to_dict(),
    }
    tracer.trace(
        "agentshield_input",
        available=shield_input.available,
        allowed=shield_input.allowed,
        pii_types=shield_input.pii_types,
        reasons=shield_input.reasons,
    )

    if not shield_input.allowed:
        # 인젝션 차단 — 프로필도 법령도 계산하지 않는다. 공격 payload를 파이프라인
        # 아래로 흘려보내지 않는 것이 요점이다.
        blocked_profile = build_family_profile(redacted)
        blocked_report = FinalReport(
            family_profile=blocked_profile,
            life_stages=blocked_profile.life_stages,
            safety_routing=safety,
            human_review=determine_human_review(
                verifier_results=None,
                safety_routing=safety,
                scenario_type=redacted.get("scenario", {}).get("type"),
            ),
            disclaimer=DISCLAIMER,
            scenario_id=scenario_id,
            law_source={"mode": "blocked", "live_count": 0, "errors": []},
            ai_answer={
                "mode": "blocked_injection",
                "text": (
                    "입력에서 시스템 지시를 조작하려는 패턴이 감지되어 상담을 진행하지 않았습니다. "
                    "질문만 다시 보내주세요."
                ),
                "used_laws": 0,
            },
            agentshield=shield_report,
        )
        tracer.trace("agentshield_block", reasons=shield_input.reasons)
        blocked_report.trace_summary = tracer.summary()
        if write_audit:
            blocked_report.audit_log_id = write_audit_log(blocked_report)
            tracer.trace("audit_log", audit_log_id=blocked_report.audit_log_id)
            tracer.export()
        return blocked_report

    # 이번 실행에서 LLM을 실제로 쓸 수 있는지 먼저 확인하고, 그 사실대로 라우팅을 기록한다.
    # 답변 상한을 2,000토큰으로 올리면서 실측한 최장 지연이 9.7초(luna)였다.
    # 여유를 두되 UI subprocess 예산(45초)은 넘지 않는다.
    llm = OpenAiClient(timeout=30.0)
    llm_ready = enable_ai_answer and llm.enabled()

    # 키워드가 놓친 안전 신호를 저비용 분류 모델(nano)로 보강한다.
    # 키워드가 이미 잡았으면 호출조차 하지 않고, 모델이 실패하면 키워드 결과가 그대로 산다.
    safety_augmented_by_model = False
    if enable_safety_llm and llm.enabled() and not safety.triggered:
        boosted = augment_safety_with_llm(
            redacted,
            safety,
            classifier=lambda instruction, text: llm.classify(
                instruction, text, model=select_model("safety_classify")
            ),
        )
        if boosted.triggered:
            safety = boosted
            safety_augmented_by_model = True

    tracer.trace(
        "input_guard",
        safety_triggered=safety.triggered,
        safety_category=safety.category,
        safety_source="model" if safety_augmented_by_model else "keyword",
        injection_detected=guard_result.injection_detected,
        notes_count=len(guard_result.notes),
    )

    model_routing = plan_model_routing(redacted, safety, llm_enabled=llm_ready)
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
            agentshield=shield_report,
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
    # learning.plan이 scenario_type을 쓰는데 이 변수는 Node 8(document_drafter)에서야
    # 할당됐다 — 모든 상담이 UnboundLocalError로 죽었다. 첫 사용 지점 앞으로 올린다.
    scenario_type = scenario_obj.get("type")
    persona_hint = redacted.get("persona") or scenario_obj.get("persona")
    # 과거 같은 주제의 상담에서 배운 것을 이번 실행의 **파라미터로** 가져온다.
    # (텍스트로 LLM에 흘리는 게 아니라 검색 점수와 토큰 상한을 직접 바꾼다.)
    learning_plan = learning.plan(scenario_query, scenario_type, enabled=enable_learning)
    tracer.trace(
        "learning_plan",
        topic_tags=learning_plan.topic_tags,
        boosted_laws=len(learning_plan.law_boosts),
        applied_patterns=len(learning_plan.applied_pattern_ids),
        changed_behavior=learning_plan.to_dict()["changed_behavior"],
    )

    matched_laws = retrieve_matched_laws(
        family_profile=profile,
        scenario_query=scenario_query,
        persona_hint=persona_hint,
        top_k=15,
        seed_dir=seed_laws_dir,
        learned_boosts=learning_plan.law_boosts,
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

    # Node 8: document_drafter  (scenario_type은 Node 5에서 이미 잡았다)
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
    # 비평가는 "AI에게 근거로 준 법령"과 정확히 같은 목록을 봐야 한다.
    # 그래야 "이 목록에 없는 인용 = 환각"이라는 판정이 성립한다.
    citable_for_critic: list[LawArticle] = []
    if enable_ai_answer and scenario_query and not safety.triggered:
        ref_date = parse_effective_date(profile.reference_date) or date.today()
        # 아직 시행되지 않은 조문은 현행처럼 인용될 수 없다 (예: 시행일 2026-10-29).
        pending = [law for law in matched_laws if not law.is_effective_on(ref_date)]
        in_force = [law for law in matched_laws if law.is_effective_on(ref_date)]
        citable = [
            law for law in in_force
            if law.law_name and law.article and law.effective_date and law.source_url
        ]
        citable_for_critic = citable
        ai_answer["citable_laws"] = len(citable)
        ai_answer["withheld_laws"] = len(in_force) - len(citable)
        ai_answer["not_yet_effective_laws"] = len(pending)
        if pending:
            ai_answer["not_yet_effective"] = [
                {"law": law.law_name, "article": law.article, "effective_date": law.effective_date}
                for law in pending
            ]

        # 국면에 맞는 모델을 고른다. 평시에는 빠르고 싼 모델, 안전 신호가 걸렸거나
        # 심층 사안이면 추론 모델로 올린다 (model_routing.select_model).
        criticality = model_routing.get("criticality", "standard")
        answer_model = select_model("answer", criticality)
        ai_answer["model_selected"] = answer_model
        ai_answer["criticality"] = criticality

        if llm.enabled() and citable:
            answer = llm.ask(
                user_question=scenario_query,
                matched_laws=citable,
                family_context_summary=f"life_stages={profile.life_stages}, flags={profile.flags}",
                model=answer_model,
                # 과거 이 주제에서 답변이 상한에 걸려 잘린 적이 있으면 미리 늘려서 시작한다.
                max_tokens=learning_plan.max_answer_tokens,
            )
            if answer.error:
                ai_answer["error"] = answer.error
                ai_answer["finish_reason"] = answer.finish_reason
            else:
                # Node 9-ter: AgentShield 출력 가드.
                #
                # 여기까지 LLM 답변은 아무 검사 없이 부모 화면으로 나갔다. 모델이 프롬프트에
                # 섞여든 API 키를 되뱉거나("api_key='sk-...'"), 상담자가 적은 이메일을
                # 그대로 복창하거나, "100% 보장" 같은 절대 단정을 하면 그대로 노출됐다.
                # 법률 안내에서 그 단정 한 줄은 그 자체로 사고다.
                #
                # 마스킹된 텍스트를 **실제로** 화면에 내보낸다. 원문은 남기지 않는다.
                shield_output = inspect_output_text(answer.text)
                shield_report["output"] = shield_output.to_dict()
                tracer.trace(
                    "agentshield_output",
                    available=shield_output.available,
                    allowed=shield_output.allowed,
                    redacted=bool(shield_output.pii_types),
                    unsupported_claims=len(shield_output.unsupported_claims),
                )

                # 토큰은 답변을 내보내든 막든 이미 썼다. 비용은 결과와 무관하게 기록한다.
                budget_guard["actual_usage"] = actual_usage_cost(
                    model=answer.model,
                    prompt_tokens=answer.prompt_tokens,
                    completion_tokens=answer.completion_tokens,
                    cached_tokens=answer.cached_tokens,
                )

                if not shield_output.allowed:
                    # 마스킹으로 해소되지 않는 위반(고신뢰 유출 탐지 등) — 답변을 내보내지 않고
                    # 규칙 모드로 강등한다. 반쯤 지워진 답변을 내보내는 것보다 낫다.
                    ai_answer.update({
                        "mode": "blocked_output",
                        "error": "output_guard_blocked",
                        "text": (
                            "생성된 답변이 출력 안전 검사를 통과하지 못해 표시하지 않았습니다. "
                            "아래 법령 근거와 권리카드를 참고해 주세요."
                        ),
                        "guard_reasons": shield_output.reasons,
                        "model": answer.model,
                        "prompt_tokens": answer.prompt_tokens,
                        "completion_tokens": answer.completion_tokens,
                        "total_tokens": answer.total_tokens,
                        "cached_tokens": answer.cached_tokens,
                        "used_laws": 0,
                    })
                    tracer.trace("agentshield_output_block", reasons=shield_output.reasons)
                else:
                    ai_answer.update({
                        "mode": "llm",
                        # 원문(answer.text)이 아니라 마스킹된 텍스트를 싣는다.
                        "text": shield_output.sanitized_text,
                        "model": answer.model,
                        "citations": answer.citations,
                        "prompt_tokens": answer.prompt_tokens,
                        "completion_tokens": answer.completion_tokens,
                        "total_tokens": answer.total_tokens,
                        # 입력 토큰 중 OpenAI가 자동 재사용한 몫. 비용 계산에 반드시 반영해야 한다.
                        "cached_tokens": answer.cached_tokens,
                        "cache_hit_ratio": round(answer.cached_tokens / answer.prompt_tokens, 3) if answer.prompt_tokens else 0.0,
                        "finish_reason": answer.finish_reason,
                        "truncated": answer.truncated,
                        "used_laws": len(citable),
                    })
                    if shield_output.unsupported_claims:
                        # "100% 보장" 같은 절대 단정은 법률 안내에서 나가면 안 되는 표현이다.
                        # 메타데이터에만 담으면 UI가 그 필드를 읽지 않아 본문이 그대로 노출된다
                        # (Codex F5). UI가 반드시 렌더하는 text 자체에 경고를 덧붙여, 별도
                        # UI 수정 없이도 부모가 단정을 액면으로 받지 않도록 한다.
                        ai_answer["unsupported_claims"] = shield_output.unsupported_claims
                        warn = ", ".join(shield_output.unsupported_claims)
                        ai_answer["text"] = (
                            f"{shield_output.sanitized_text.rstrip()}\n\n"
                            f"⚠️ 아래 표현은 단정적이라 그대로 신뢰하지 마세요: {warn}. "
                            f"법적 효과는 개별 사안과 요건에 따라 달라지며, 확정된 보장이 아닙니다."
                        )
        elif not llm.enabled():
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
        agentshield=shield_report,
    )

    # Node 9-ter: 독립 적대적 비평가.
    #
    # 부모가 읽을 답변을 **다른 회사의 모델**(기본 x-ai/grok-4.5, 폴백 anthropic/claude-sonnet-5)이
    # 물어뜯는다. 답변을 쓴 모델에게 자기 답변을 검토시키면 같은 착각을 두 번 한다.
    #
    # 여기가 이 시스템에서 답변 텍스트를 검증하는 **유일한** 지점이다. atomic claim 검증은
    # 결정론 산출물만 보고, 그 사이로 "[민법 제836조의2]에 따라 100% 승소합니다" 같은 문장이
    # 전 게이트를 통과해 나가고 있었다.
    critic = critique_answer(
        question=scenario_query,
        answer=str(ai_answer.get("text") or ""),
        laws=citable_for_critic,
        enabled=enable_critic,
    ).to_dict()
    report.adversarial_critic = critic
    tracer.trace(
        "adversarial_critic",
        verdict=critic.get("verdict"),
        model=critic.get("model"),
        findings=len(critic.get("findings", [])),
        fallback_used=critic.get("fallback_used"),
    )

    # 🔴 판정을 실제로 강제한다.
    #
    # 이전 구현은 BLOCK을 리포트에 적어만 뒀다 — 소비하는 코드가 없어서 BLOCK과 PASS가
    # 운영상 동일했다. 기록은 게이트가 아니다. 차단하려면 실제로 차단해야 한다.
    if critic.get("verdict") == "BLOCK":
        withheld = ai_answer.get("text") or ""
        ai_answer.update({
            "mode": "withheld_by_critic",
            "text": (
                "독립 검증 모델이 이 답변에서 근거 없는 단정 또는 존재하지 않는 법령 인용을 발견해 "
                "표시를 보류했습니다. 아래 법령 목록과 문서 초안은 그대로 확인하실 수 있으며, "
                "정확한 판단이 필요하면 전문가 상담을 권장합니다.\n\n"
                + "\n".join(
                    f"- ({f.get('code')}) {f.get('reason')}"
                    for f in critic.get("findings", [])[:4]
                )
            ),
            "withheld_text": withheld,          # 감사·디버깅용으로만 보존. UI는 text만 읽는다.
            "withheld_reason": critic.get("summary"),
        })
        report.ai_answer = ai_answer
        # 사람이 봐야 한다. 비평가가 막은 답변을 조용히 넘기지 않는다.
        if report.human_review:
            report.human_review.needed = True
            prior = report.human_review.reason
            report.human_review.reason = (
                f"{prior} / 독립 비평가 BLOCK — 답변 보류" if prior
                else "독립 비평가 BLOCK — 답변 보류"
            )
        tracer.trace("critic_block_enforced", findings=len(critic.get("findings", [])))

    # Final governance gates run after all writer/reviewer outputs are attached.
    report.independent_validation = run_independent_validation(
        report,
        model_routing=model_routing,
        budget_guard=budget_guard,
        critic_verdict=critic,
    )
    tracer.trace(
        "independent_validation",
        status=report.independent_validation.get("status"),
        findings=len(report.independent_validation.get("findings", [])),
    )
    capture = memory.capture_outcome(report) if write_audit else {"captured": False, "reason": "audit_disabled"}
    report.memory_context = {**memory_context, "capture": capture}
    tracer.trace("memory_capture", captured=capture.get("captured"))

    # 학습 폐루프: 이번 상담을 성공/실패로 판정해 저장하고,
    # 이번에 적용했던 패턴들이 실제로 통했는지로 그 패턴들의 confidence를 갱신한다.
    # (적용 결과가 confidence를 바꾸는 것 — SEAS가 끝내 구현하지 못한 부분이다.)
    learning_result = learning.observe(
        report.to_dict(), learning_plan,
        scenario_type=scenario_type or "general",
        enabled=enable_learning,
    )
    report.learning = {**learning_plan.to_dict(), "capture": learning_result}
    tracer.trace(
        "learning_observe",
        captured=learning_result.get("captured"),
        status=learning_result.get("status"),
        outcome_feedback=learning_result.get("outcome_feedback", {}).get("updated", 0),
    )

    report.trace_summary = tracer.summary()

    if write_audit:
        report.audit_log_id = write_audit_log(report)
        tracer.trace("audit_log", audit_log_id=report.audit_log_id)
        tracer.export()
    return report
