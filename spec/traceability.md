# 자람법 TRACEABILITY — 제안서 → SPEC → 구현 매핑

> 자람법_제안서_v2.md 각 섹션이 어떤 SPEC 항목, 모듈, 테스트로 구현되는지 추적.

## 제안서 → SPEC 매핑

| 제안서 § | 제안서 내용 | SPEC § | 구현 모듈 | 테스트 |
|---|---|---|---|---|
| §1 | 한 줄 소개 | spec §1 | (전체) | test_scenarios.py |
| §2.1 | 똑똑맘 채널 신호 | (마케팅 영역, MVP 외) | content_link.py (stub) | — |
| §2.2 P1-P5 | 부모 5가지 페인 | spec §3 (F1-F8) | 전체 모듈 | test_scenarios.py |
| §3 | 핵심 가치 제안 | spec §1 | — | — |
| §4 | 페르소나 3 | spec §2 | data/seed/scenarios/*.yaml | test_family_context.py |
| §5 F1 | 가족 프로필 매니저 | spec §3 F1 | family_context.py | test_family_context.py |
| §5 F2 | 지원 매칭 | spec §3 F2 | support_matching.py | test_support_matching.py |
| §5 F3 | 법령 캘린더 | spec §3 F3 | calendar_gen.py | test_calendar.py |
| §5 F4 | 분쟁 자가진단 + 신고 | spec §3 F4 | orchestrator.py + document_drafter.py | test_document_drafter.py |
| §5 F5 | 문서 분석 (멀티모달) | spec §3 F5 (stub) | — (MVP 후속) | — |
| §5 F6 | 권리 카드 | spec §3 F6 | rights_card.py | test_rights_card.py |
| §5 F7 | 법령 변화 푸시 | spec §3 F7 (stub) | freshness_monitor.py | — |
| §5 F8 | 똑똑맘 연계 | spec §3 F8 (stub) | content_link.py | — |
| §6 시나리오 A | 둘째 임신 + 첫째 4세 | spec §4 시나리오 A | examples/scenario_A.py | test_scenarios.py::test_scenario_a |
| §6 시나리오 B | 학원 환불 거부 | spec §4 시나리오 B | examples/scenario_B.py | test_scenarios.py::test_scenario_b |
| §6 시나리오 C | 어린이집 사고 | spec §4 시나리오 C | examples/scenario_C.py | test_scenarios.py::test_scenario_c |
| §6 시나리오 D | 남편 육아휴직 거부 | (시나리오 A에 권리카드로 포함) | rights_card.py 데이터 | test_rights_card.py |
| §6 시나리오 E | AI 기본법 시의성 | (현 시드 외 — 후속) | — | — |
| §7 법령 데이터 30개 카탈로그 | 데이터 출처 | spec §6 LawArticle | data/seed/laws/*.yaml | test_law_retrieval.py |
| §8 기술 아키텍처 14노드 | (그림 그대로) | plan §1 | workflows/family-legal-jaramlaw.workflow.yaml + orchestrator.py | test_workflow_validation.py |
| §8.1 AITHOR 자산 매핑 | 기존 자산 100% 재사용 | plan §7 (SKILLs 활용) | docs/ai-research-skills-integration.md | — |
| §9 AI 차별점 6 | Life-Stage Aware 외 | spec §3 (F1-F8에 통합) | family_context.py + orchestrator.py | test_scenarios.py |
| §11 안전성 5 | 변호사법/의료법/PII/자동발사/고지 | constitution §원칙1-5 | guard.py + verifier.py + workflow YAML safety 섹션 | test_constitution.py |
| §12 MVP 범위 | 시나리오 3개 deterministic | spec §4 + §8 AC1 | examples/scenario_*.py | test_scenarios.py |
| §15 기획서 매핑 | 붙임4 양식 매핑 | docs/contest-mapping.md | — | — |

## Constitution 원칙 → 강제 메커니즘

| 원칙 | 강제 위치 | 검증 테스트 |
|---|---|---|
| 1 (변호사법) | 출력 표준 고지 + verifier "구체 사건 자문" 키워드 차단 | test_constitution.py::test_principle_1_disclaimer |
| 2 (Citation) | verifier.py atomic claim 검사 | test_constitution.py::test_principle_2_citation |
| 3 (Safety routing) | guard.py SafetySignalDetector | test_constitution.py::test_principle_3_safety_routing |
| 4 (자동 발사 금지) | workflow.py `external_side_effect_tools_allowed: []` validate | test_constitution.py::test_principle_4_no_side_effects |
| 5 (PII) | guard.py PIIRedactor | test_constitution.py::test_principle_5_pii_masking |

## 법령 → 시드 → 권리카드 → 테스트 정합성

| 법령/조문 | 시드 YAML | RightsCard | 시나리오 |
|---|---|---|---|
| 근로기준법 74조 | labor-standards-74.yaml | maternity-leave-90d | A |
| 근로기준법 74조의2 | labor-standards-74-2.yaml | prenatal-checkup-leave | A |
| 남녀고용평등법 18조의2 | equal-employment-18-2.yaml | spouse-birth-leave | A |
| 남녀고용평등법 19조 | equal-employment-19.yaml | parental-leave-1y | A, D (포함) |
| 남녀고용평등법 22조의2 | equal-employment-22-2.yaml | family-care-leave | A |
| 남녀고용평등법 37조 | equal-employment-37.yaml | (벌칙 — 권리카드 footnote) | D |
| 영유아보육법 33조의3 | childcare-33-3.yaml | daycare-safety-report | C |
| 영유아보육법 15조의5 | childcare-15-5.yaml | daycare-cctv-access | C |
| 영유아보육법 34조 | childcare-34.yaml | (지원 매칭 보육료) | A |
| 학원법 시행령 18조 별표4 | academy-decree-18.yaml | (환불액 계산) | B |
| 학교폭력예방법 12-17조 | school-violence-12-17.yaml | school-violence-procedure | (시드만, MVP 후속 사용) |
| 아동복지법 3조 | child-welfare-3.yaml | (학대 정의) | C 안내 |
| 아동학대범죄처벌법 10조 | child-abuse-10.yaml | abuse-report-obligation | C 라우팅 |
| 정보통신망법 31조 | itnet-31.yaml | minor-consent-14 | (constitution §5) |
| 양육비이행확보법 | child-support-enforcement.yaml | child-support-enforcement | (P3 페르소나) |
| 한부모가족지원법 | single-parent.yaml | (지원 매칭) | (P3) |
| 아동수당법 4조 | child-allowance-4.yaml | (지원 매칭) | A |
| 모자보건법 | maternal-health.yaml | (캘린더) | A |
| 감염병예방법 24조 | infectious-disease-24.yaml | (예방접종 캘린더) | A |
| 저출산고령사회기본법 | low-birth-rate-act.yaml | (첫만남이용권 근거) | A |

22개 시드 → 14개 RightsCard + 환불 계산기 + 캘린더 + 5개 지원 매칭.

## AC 매핑

| AC | 검증 | 테스트 |
|---|---|---|
| AC1 deterministic A/B/C | seeded mode 동일 입력 → 동일 출력 | test_scenarios.py |
| AC2 고지 문구 | 모든 출력에 lawyer disclaimer | test_constitution.py |
| AC3 citation | atomic claim verifier | test_verifier.py |
| AC4 PII | 입력 마스킹 회귀 | test_guard.py |
| AC5 safety routing | 학대 키워드 → 1577-1391 | test_guard.py, test_constitution.py |
| AC6 환불액 정확성 | 학원법 시행령 별표4 일할 계산 ±1원 | test_document_drafter.py |
| AC7 pytest 15+ | 전수 PASS | (실행) |
| AC8 workflow validate | require_nodes + require_text | test_workflow_validation.py |
