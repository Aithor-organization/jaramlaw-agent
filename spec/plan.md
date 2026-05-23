# 자람법 PLAN — 구현 계획

> SPEC를 실행 가능한 14노드 workflow + Python 모듈 + 시드 데이터 + 테스트로 분해.

## 1. 아키텍처 14노드

```text
[1] intake (입력 수집)
   ↓
[2] input_guard (AgentShield: PII 마스킹, prompt injection, safety 신호 감지)
   ↓ (학대/응급 신호 시 [13]로 즉시 라우팅)
[3] family_context (라이프스테이지 분류 + 특수상황 태그)
   ↓
[4] law_retrieval (BM25 + 시드 hybrid matching, LawApiClient stub)
   ↓
[5] support_matching (자격 매칭 + D-day 계산)
   ↓
[6] parallel_expert_board (5 에이전트 독립 검토 — board_opinions)
   ↓
[7] document_drafter (신청서/신고서/환불요청서 초안)
   ↓
[8] verify_atomic_claims (Citation-required 검증 — Constitution 원칙 2)
   ↓ (unverifiable 발견 시 [9]로 격리)
[9] human_review_gate (고위험·저신뢰 → 전문가 상담 안내 라우팅)
   ↓
[10] rights_card_gen (권리 카드 markdown/JSON 생성)
[11] calendar_gen (영유아 일정 iCal 생성)
   ↓
[12] freshness_monitor (법령 변경 감지 stub)
   ↓
[13] safety_routing (긴급 라우팅 — 학대/응급/자해/가정폭력)
   ↓
[14] audit_log (구조화 로그 + final_report JSON)
```

## 2. 모듈 구조

```
src/jaramlaw_agent/
├── __init__.py
├── __main__.py
├── models.py              # FamilyProfile, Child, LawArticle, Support, RightsCard
├── family_context.py      # life stage + 특수상황 태그 (F1)
├── law_retrieval.py       # 시드 yaml 로드 + BM25 매칭 (F4 핵심)
├── support_matching.py    # 자격 매칭 + D-day (F2)
├── document_drafter.py    # 신청서/신고서 템플릿 (F4)
├── rights_card.py         # 권리카드 생성 (F6)
├── calendar_gen.py        # iCal 생성 (F3)
├── guard.py               # AgentShield PIIRedactor + SafetySignalDetector
├── verifier.py            # Atomic claim citation check
├── human_review.py        # 고위험 라우팅
├── orchestrator.py        # 14노드 실행 + Multi-Agent Board
├── workflow.py            # YAML 파서 + validator
├── audit.py               # audit log 생성
├── content_link.py        # 똑똑맘 stub
├── freshness_monitor.py   # 법령 변경 감지 stub
└── cli.py                 # 진입점 (demo / doctor / match)
```

## 3. 시드 데이터 범위

### 법령 시드 (20-30개 조문 — `data/seed/laws/`)
| 카테고리 | 조문 (수) |
|---|---|
| 임신·출산 권리 | 근로기준법 74조/74조의2, 남녀고용평등법 18조의2 (3) |
| 육아휴직 | 남녀고용평등법 19조/22조의2/37조 (3) |
| 부모급여·수당 | 아동수당법 4조, 한부모가족지원법 (2) |
| 영유아 보육 | 영유아보육법 33조의3/15조의5/34조 (3) |
| 건강·예방접종 | 감염병예방법 24조, 모자보건법 (2) |
| 학원 분쟁 | 학원법 시행령 18조 별표4 (1) |
| 학교폭력 | 학교폭력예방법 12-17조 (3개 grouped) |
| 아동 권리 | 아동복지법 3조, 아동학대범죄처벌법 10조 (2) |
| 미성년 SNS | 정보통신망법 31조 (1) |
| 양육비 | 양육비이행확보법 (1) |
| 기타 | 저출산고령사회기본법 (1) |
| **총** | **22+ 조문** |

### 정부지원 시드 (`data/seed/supports/`)
- 부모급여 (만 0세 100만원/월, 만 1세 50만원/월)
- 아동수당 (만 8세 미만 월 10만원)
- 첫만남이용권 (200만원)
- 다자녀 혜택
- 한부모 아동양육비
- 임산부 친환경 농산물
- 보육료 (누리과정)
- 양육수당 (가정양육 시)
- 서울시 둘째 출산축하금
- 배우자 출산휴가 급여

### 시나리오 fixture (`data/seed/scenarios/`)
- A_pregnancy_workmom.yaml
- B_academy_refund.yaml
- C_daycare_accident.yaml

## 4. workflow YAML

`workflows/family-legal-jaramlaw.workflow.yaml` — policy-finance-agent.workflow.yaml 패턴 mirror.
필수 토큰: `AgentShield.RuntimeGuard`, `pii_redaction_required: true`, `external_side_effect_tools_allowed: []`, `citation_required: true`.

## 5. 의존성

- Python ≥ 3.10
- pyyaml (시드 데이터 로드 + workflow YAML 파싱)
- pytest (dev)
- 외부 API 의존성 없음 (seeded mode 기본)

## 6. 테스트 전략

| 테스트 | 검증 항목 | AC |
|---|---|---|
| test_models.py | 데이터클래스 직렬화 | — |
| test_family_context.py | 생년월일 → 라이프스테이지 | F1 |
| test_law_retrieval.py | 시드 로드 + 키워드 매칭 | F4 |
| test_support_matching.py | 자격 매칭 + D-day | F2 |
| test_document_drafter.py | 환불액 계산 + 템플릿 | F4 |
| test_guard.py | PII 마스킹 + safety 신호 | 원칙 3, 5 |
| test_verifier.py | citation 강제 | 원칙 2 |
| test_rights_card.py | 권리카드 출력 | F6 |
| test_calendar.py | iCal 생성 | F3 |
| test_workflow_validation.py | YAML validator | AC8 |
| test_constitution.py | 5원칙 회귀 차단 | 원칙 1-5 |
| test_scenarios.py | A/B/C deterministic | AC1, AC2, AC3 |

## 7. AI-research-SKILLs 활용

| 스킬 | 활용 영역 |
|---|---|
| `14-agents` | Multi-Agent Board 패턴 (5 에이전트 병렬) |
| `15-rag` | Hybrid BM25 + Vector + RRF + Reranker (law retrieval) |
| `07-safety-alignment` | Constitution 원칙 + Safety signal routing |
| `11-evaluation` | Atomic claim verifier + e2e 시나리오 회귀 |
| `17-observability` | audit log 구조화 |
| `24-spec-driven-planner` | 본 SDD 문서 패턴 |
| `25-backend-architect` | 14노드 workflow 아키텍처 |
| `28-agent-memory` | FamilyProfile + 컨텍스트 영속화 |
| `62-mcp-agent-protocols` | LAW.OS law_mcp_server 연동 인터페이스 |
| `68-claude-native-agent-systems` | 에이전트 contract 패턴 |

## 8. 일정 (MVP D-7)

| 일정 | 작업 (Task ID) |
|---|---|
| D-7 (5/24, 오늘) | T01-T05: 스캐폴드 + SDD + workflow + agent contracts + 시드 |
| D-6 | T06-T08: 시나리오 fixture + 코어 모듈 + matching/card/calendar |
| D-5 | T09-T10: document drafter + safety layer |
| D-4 | T11-T12: orchestrator + CLI demo |
| D-3 | T13: tests |
| D-2 | T14: docs |
| D-1 | T15: 통합 검증 |
| D-day | 제출 |

본 turn에서는 D-7 ~ D-3 작업을 모두 수행 (autonomous mode).
