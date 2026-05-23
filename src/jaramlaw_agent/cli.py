"""jaramlaw CLI 진입점.

사용 예:
  python -m jaramlaw_agent doctor
  python -m jaramlaw_agent demo --scenario A
  python -m jaramlaw_agent demo --scenario B --output runs/scenario_b.json
  python -m jaramlaw_agent demo --scenario C
  python -m jaramlaw_agent validate-workflow

Constitution 5원칙 자동 강제. seeded mode 기본 (API 키 없이 동작).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from . import DISCLAIMER, __version__
from .audit import _serialize
from .config import Config
from .family_context import build_family_profile
from .law_retrieval import retrieve_matched_laws
from .orchestrator import PROJECT_ROOT, run_workflow
from .rights_card import render_card_markdown
from .workflow import validate_family_legal_workflow, WorkflowValidationError


SCENARIO_DIR = PROJECT_ROOT / "data" / "seed" / "scenarios"

SCENARIO_FILE_MAP = {
    "A": "A_pregnancy_workmom.yaml",
    "B": "B_academy_refund.yaml",
    "C": "C_daycare_accident.yaml",
}


def cmd_doctor(args: argparse.Namespace) -> int:
    """환경 자가진단 + 외부 통합 상태."""
    print("=== 자람법 doctor ===")
    print(f"version: {__version__}")
    issues = []

    # 시드 디렉토리
    laws_dir = PROJECT_ROOT / "data" / "seed" / "laws"
    supports_dir = PROJECT_ROOT / "data" / "seed" / "supports"
    scenarios_dir = PROJECT_ROOT / "data" / "seed" / "scenarios"

    n_laws = len(list(laws_dir.glob("*.yaml"))) if laws_dir.exists() else 0
    n_supports = len(list(supports_dir.glob("*.yaml"))) if supports_dir.exists() else 0
    n_scenarios = len(list(scenarios_dir.glob("*.yaml"))) if scenarios_dir.exists() else 0

    print(f"  laws seeded:     {n_laws}")
    print(f"  supports seeded: {n_supports}")
    print(f"  scenarios:       {n_scenarios}")

    if n_laws < 20:
        issues.append(f"법령 시드 부족 — 현재 {n_laws} (목표 20+)")
    if n_supports < 5:
        issues.append(f"지원 시드 부족 — 현재 {n_supports} (목표 5+)")
    if n_scenarios < 3:
        issues.append(f"시나리오 fixture 부족 — 현재 {n_scenarios} (목표 3)")

    # workflow YAML
    wf_path = PROJECT_ROOT / "workflows" / "family-legal-jaramlaw.workflow.yaml"
    if not wf_path.exists():
        issues.append(f"workflow YAML 누락: {wf_path}")
    else:
        try:
            validate_family_legal_workflow(wf_path)
            print("  workflow YAML:   ✓ validated")
        except WorkflowValidationError as exc:
            issues.append(f"workflow YAML 검증 실패: {exc}")

    # === 외부 통합 (T16-T19) 진단 ===
    print()
    print("=== 외부 통합 ===")
    cfg = Config.from_env()
    summary = cfg.summary()
    print(f"  OpenAI:     {summary['openai_api_key']} ({summary['openai_model']})")
    print(f"  법제처 API: {summary['law_api_key']} ({summary['law_api_base_url']})")
    print(f"  legalize-kr: {summary['legalize_kr_path']} (exists: {summary['legalize_kr_exists']})")
    if cfg.has_legalize_kr():
        from .legalize_kr_client import LegalizeKrClient
        lc = LegalizeKrClient(cfg)
        mapped = lc.list_mapped_laws()
        ok = sum(1 for _, _, x in mapped if x)
        print(f"  legalize-kr 매핑: {ok}/{len(mapped)} OK")
        if ok < len(mapped):
            for lid, p, x in mapped:
                if not x:
                    print(f"    ❌ {lid} -> {p}")
    if args.deep and cfg.has_law_api():
        from .law_api_client import LawApiClient
        print()
        print("  법제처 API 호출 테스트:")
        try:
            la = LawApiClient(cfg).diagnose()
            print(f"    status={la.get('status')} sample={la.get('sample_law','-')}")
        except Exception as exc:
            issues.append(f"법제처 API 호출 실패: {exc}")
    if args.deep and cfg.has_openai():
        from .openai_client import OpenAiClient
        print()
        print("  OpenAI 호출 테스트:")
        try:
            oc = OpenAiClient(cfg).diagnose()
            print(f"    status={oc.get('status')} tokens={oc.get('sample_tokens','-')}")
        except Exception as exc:
            issues.append(f"OpenAI 호출 실패: {exc}")

    print()
    if issues:
        print("⚠️ 발견 사항:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("✅ 모든 자가진단 PASS")
    return 0


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    fn = SCENARIO_FILE_MAP.get(scenario_id.upper())
    if not fn:
        raise SystemExit(f"unknown scenario: {scenario_id} (use A/B/C)")
    path = SCENARIO_DIR / fn
    if not path.exists():
        raise SystemExit(f"scenario fixture not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def cmd_demo(args: argparse.Namespace) -> int:
    """시나리오 데모 실행 → 보고서 + audit log."""
    scenario_id = args.scenario
    fixture = _load_scenario(scenario_id)

    raw_input = fixture.get("family_profile", {})
    raw_input["scenario"] = fixture.get("scenario", {})
    raw_input["reference_date"] = fixture.get("reference_date")
    raw_input["persona"] = fixture.get("persona")

    report = run_workflow(
        raw_input=raw_input,
        scenario_id=scenario_id,
    )

    # 결과 출력
    print(DISCLAIMER)
    print()
    print(f"=== 시나리오 {scenario_id}: {fixture.get('scenario_name', '')} ===")
    print(f"audit_log_id: {report.audit_log_id}")
    print(f"reference_date: {report.family_profile.reference_date}")
    print(f"life_stages: {report.life_stages}")
    print(f"family_flags: {report.family_profile.flags}")
    print()

    # safety 라우팅 우선
    if report.safety_routing and report.safety_routing.triggered:
        print("🚨 SAFETY ROUTING 발동")
        print(f"  카테고리: {report.safety_routing.category}")
        print(f"  연락처: {report.safety_routing.contact}")
        print(f"  사유: {report.safety_routing.reason}")
        print()

    print(f"📚 매칭 법령: {len(report.matched_laws)}건")
    for law in report.matched_laws[:8]:
        print(f"  - {law.law_name} {law.article} ({law.title}) — score={law.relevance_score}")
    if len(report.matched_laws) > 8:
        print(f"  ... 외 {len(report.matched_laws) - 8}건")
    print()

    print(f"💰 지원 매칭: {len(report.support_matches)}건")
    for s in report.support_matches:
        dline = f"D-{s.deadline_days_left}" if s.deadline_days_left is not None else "상시"
        print(f"  - {s.name}: {s.amount_description}  [{dline}, {s.application_channel}]")
    print()

    print(f"📋 권리 카드: {len(report.rights_cards)}장")
    for c in report.rights_cards:
        print(f"  - {c.title} ({c.legal_basis.law} {c.legal_basis.article})")
    print()

    if report.calendar:
        print(f"📅 캘린더 이벤트: {len(report.calendar.events)}건 (다음 5건)")
        for ev in report.calendar.events[:5]:
            print(f"  - {ev.scheduled_date}: {ev.title}")
        print()

    print(f"📝 초안 문서: {len(report.draft_documents)}건")
    for d in report.draft_documents:
        print(f"  - {d.title} ({d.kind})")
        if d.calculation_breakdown:
            print(f"    계산: {d.calculation_breakdown}")
    print()

    if report.verifier_results:
        v = report.verifier_results.summarize()
        print(f"✔ 검증: total={v['total']} verified={v['verified']} partial={v['partial']} unverifiable={v['unverifiable']} ratio={v['verified_ratio']}")
        print()

    if report.human_review and report.human_review.needed:
        print("🤝 전문가 상담 권장")
        print(f"  사유: {report.human_review.reason}")
        for exp in report.human_review.recommended_experts:
            print(f"  - {exp['kind']}: {exp['contact_info']} ({exp.get('cost_estimate', '')})")
        print()

    # output 파일 저장
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = _serialize(report)
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"💾 final_report → {out_path}")

    # 첫 권리카드 markdown 출력 (옵션)
    if args.print_first_card and report.rights_cards:
        print()
        print("=" * 60)
        print(render_card_markdown(report.rights_cards[0]))

    return 0


def cmd_validate_workflow(args: argparse.Namespace) -> int:
    wf_path = PROJECT_ROOT / "workflows" / "family-legal-jaramlaw.workflow.yaml"
    try:
        wf = validate_family_legal_workflow(wf_path)
    except WorkflowValidationError as exc:
        print(f"❌ workflow 검증 실패: {exc}", file=sys.stderr)
        return 1
    print(f"✅ workflow OK")
    print(f"  name: {wf.name}")
    print(f"  purpose: {wf.purpose}")
    print(f"  nodes ({len(wf.node_ids)}): {', '.join(wf.node_ids)}")
    return 0


# === 신규: 외부 통합 명령어 ===


def cmd_search_law(args: argparse.Namespace) -> int:
    """법령 검색 — 시드 + legalize-kr + (옵션) 법제처 API."""
    keyword = args.keyword
    cfg = Config.from_env()
    print(f"🔎 검색어: {keyword}")
    print()

    # 1) 시드 (법령 매칭)
    print("=== 시드 매칭 ===")
    dummy_profile = build_family_profile({
        "parents": [{"role": "guardian", "age": 30}],
        "children": [],
    })
    seed_results = retrieve_matched_laws(dummy_profile, keyword, top_k=5)
    for law in seed_results:
        print(f"  - {law.law_name} {law.article} ({law.title}) [score={law.relevance_score}]")
    if not seed_results:
        print("  (매칭 없음)")
    print()

    # 2) legalize-kr 본문 검색
    if cfg.has_legalize_kr():
        from .legalize_kr_client import LegalizeKrClient
        print("=== legalize-kr 본문 검색 ===")
        client = LegalizeKrClient(cfg)
        lk_results = client.search_full_text(keyword, max_results=3)
        for r in lk_results:
            print(f"  - {r.law_name} ({r.file_path}, 시행 {r.effective_date_iso})")
            if r.article_excerpt:
                snippet = r.article_excerpt.replace("\n", " ")[:200]
                print(f"    snippet: …{snippet}…")
        if not lk_results:
            print("  (매핑된 22개 법령에서 매칭 없음)")
    print()

    # 3) 법제처 API (--remote 옵션)
    if args.remote and cfg.has_law_api():
        from .law_api_client import LawApiClient
        api = LawApiClient(cfg)
        print("=== 법제처 Open API 검색 (법령명) ===")
        try:
            api_results = api.search_laws(keyword, display=5, search_mode=1)
            if not api_results:
                print("  (법령명 매칭 없음)")
            for r in api_results:
                print(f"  - {r.law_name} | 공포 {r.promulgation_date} | 시행 {r.effective_date} | {r.department} | MST={r.law_mst}")
        except Exception as exc:
            print(f"  ❌ API 호출 실패: {exc}")
        print()
        print("=== 법제처 Open API 검색 (본문) ===")
        try:
            api_results = api.search_laws(keyword, display=5, search_mode=2)
            if not api_results:
                print("  (본문 매칭 없음)")
            for r in api_results:
                print(f"  - {r.law_name} | 시행 {r.effective_date} | {r.department}")
        except Exception as exc:
            print(f"  ❌ API 호출 실패: {exc}")
    elif args.remote:
        print("=== 법제처 API ===")
        print("  ⚠️ LAW_API_KEY 미설정 — .env 확인")

    return 0


def cmd_fetch_article(args: argparse.Namespace) -> int:
    """특정 law_id (자람법 시드 ID) → 현행 본문 출력."""
    cfg = Config.from_env()
    law_id = args.law_id
    article_no = args.article

    if not cfg.has_legalize_kr():
        print("⚠️ legalize-kr 저장소 없음 — LEGALIZE_KR_PATH 또는 external/legalize-kr/ 확인")
        return 1

    from .legalize_kr_client import LegalizeKrClient
    client = LegalizeKrClient(cfg)

    if article_no:
        art = client.extract_article_section(law_id, article_no)
    else:
        art = client.get_article(law_id)

    if not art:
        print(f"❌ law_id={law_id} 매핑 없음. 매핑 목록:")
        for lid, p, ok in client.list_mapped_laws():
            mark = "✓" if ok else "✗"
            print(f"  {mark} {lid:38s} {p}")
        return 1

    print(f"# {art.title}")
    print(f"- 시행일자: {art.effective_date_iso}")
    print(f"- 출처: {art.source_url}")
    print(f"- 파일: {art.file_path}")
    print()
    text_to_show = art.article_excerpt or art.body_full
    # 너무 길면 잘라서 출력
    if len(text_to_show) > 4000 and not args.full:
        print(text_to_show[:4000])
        print()
        print(f"... (생략) — 전체 보기는 --full")
    else:
        print(text_to_show)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """자연어 질문 → 매칭 법령 컨텍스트 + LLM 답변."""
    cfg = Config.from_env()
    question = args.question
    print(f"❓ 질문: {question}")
    print()

    # 1) 시드 + retrieval로 컨텍스트 확보
    profile_raw = {
        "parents": [{"role": "guardian", "age": 30}],
        "children": [],
        "reference_date": None,
    }
    if args.persona:
        profile_raw["persona"] = args.persona

    profile = build_family_profile(profile_raw)
    matched_laws = retrieve_matched_laws(
        family_profile=profile,
        scenario_query=question,
        persona_hint=args.persona,
        top_k=6,
    )

    print(f"📚 컨텍스트 법령 {len(matched_laws)}건:")
    for law in matched_laws:
        print(f"  - {law.law_name} {law.article} ({law.title})")
    print()

    # 2) (옵션) legalize-kr 본문으로 컨텍스트 보강
    if args.with_legalize and cfg.has_legalize_kr():
        from .legalize_kr_client import LegalizeKrClient
        lc = LegalizeKrClient(cfg)
        for law in matched_laws[:3]:
            art = lc.extract_article_section(law.law_id, law.article)
            if art and art.effective_date_iso:
                # 시드 effective_date를 legalize-kr 최신 시행일로 보강
                law.effective_date = art.effective_date_iso
                if art.source_url:
                    law.source_url = art.source_url

    # 3) LLM 호출
    if not cfg.has_openai():
        print("⚠️ OPENAI_API_KEY 미설정 — LLM 호출 스킵. 위 컨텍스트 법령만 참고하세요.")
        print(DISCLAIMER)
        return 0

    from .openai_client import OpenAiClient
    client = OpenAiClient(cfg)
    print("🤖 LLM 호출 중 ...")
    answer = client.ask(
        user_question=question,
        matched_laws=matched_laws,
        family_context_summary=f"flags={profile.flags}, life_stages={profile.life_stages}",
    )
    print()
    print("=" * 60)
    print(answer.text)
    print("=" * 60)
    print()
    print(f"model: {answer.model} | tokens: {answer.total_tokens} (prompt={answer.prompt_tokens}, completion={answer.completion_tokens})")
    if answer.citations:
        print(f"citations: {answer.citations}")
    if answer.safety_flag:
        print("⚠️ 안전 라우팅 안내가 응답에 포함됨")
    if answer.error:
        print(f"❌ error: {answer.error}")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jaramlaw",
        description="자람법(JaramLaw) — 가족 라이프스테이지 법령·정책 AI 동반자",
    )
    parser.add_argument("--version", action="version", version=f"jaramlaw {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp_doctor = sub.add_parser("doctor", help="환경 자가진단 (외부 통합 포함)")
    sp_doctor.add_argument("--deep", action="store_true", help="법제처 API + OpenAI 호출 테스트 포함")
    sp_doctor.set_defaults(func=cmd_doctor)

    sp_demo = sub.add_parser("demo", help="시나리오 데모 실행")
    sp_demo.add_argument("--scenario", required=True, choices=["A", "B", "C"])
    sp_demo.add_argument("--output", default=None, help="final_report JSON 출력 경로")
    sp_demo.add_argument("--print-first-card", action="store_true", help="첫 권리카드 markdown 출력")
    sp_demo.set_defaults(func=cmd_demo)

    sp_val = sub.add_parser("validate-workflow", help="workflow YAML 검증")
    sp_val.set_defaults(func=cmd_validate_workflow)

    sp_search = sub.add_parser("search-law", help="법령 검색 — 시드 + legalize-kr + (옵션) 법제처 API")
    sp_search.add_argument("keyword", help="검색 키워드")
    sp_search.add_argument("--remote", action="store_true", help="법제처 Open API도 호출")
    sp_search.set_defaults(func=cmd_search_law)

    sp_fetch = sub.add_parser("fetch-article", help="law_id 본문 출력 (legalize-kr 현행본)")
    sp_fetch.add_argument("law_id", help="자람법 시드 law_id (예: labor-standards-74)")
    sp_fetch.add_argument("--article", default=None, help="특정 조문 (예: 제74조)")
    sp_fetch.add_argument("--full", action="store_true", help="긴 본문도 전체 출력")
    sp_fetch.set_defaults(func=cmd_fetch_article)

    sp_ask = sub.add_parser("ask", help="자연어 질문 → 매칭 법령 컨텍스트 + LLM 답변 (OpenAI)")
    sp_ask.add_argument("question", help="질문 텍스트")
    sp_ask.add_argument("--persona", default=None, choices=["P1", "P2", "P3"], help="페르소나 hint")
    sp_ask.add_argument("--with-legalize", action="store_true", default=True, help="legalize-kr 현행 시행일로 컨텍스트 보강 (기본 활성)")
    sp_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
