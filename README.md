# 자람법 (JaramLaw)

> **부모가 양육에 집중하고, 법령·지원·권리·의무는 자람법이 알아서 챙겨준다.**
>
> 가족 라이프스테이지 법령·정책 AI 동반자. AITHOR-Agent-Framework 기반 도메인팩 `family-legal`.

---

## 한 줄 소개

자람법은 부모가 입력한 아이의 생년월일·지역·가족 구성·라이프이벤트를 기준으로,
지금 이 순간 우리 가족에게 적용되는 **법령·정부지원·권리·의무**를 선제적으로 알려주고,
실제 받은 문서(어린이집 알림장·학원 환불 안내·학교폭력 통지문 등)를 분석해 **대응 가이드를 자동 생성**하는
가족 라이프스테이지 법령 AI 동반자다.

---

## 기본 UI 모습

부모가 바로 상담 흐름을 이해할 수 있도록, 따뜻한 색감의 상담 입력·이력·검토 결과·전문가 확인 패널을 한 화면에 배치했다.
UI는 `jaramlaw-agent-ui/`에서 실행되며, Python 워크플로우와 운영 계층 상태를 함께 표시한다.

![JaramLaw Agent 기본 UI](docs/assets/jaramlaw-ui-basic.png)

---

## 빠른 시작

```bash
# 1. venv 셋업
cd /home/cafe66/workspace/jaramlaw-agent
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml pytest

# 2. .env 설정 (선택 — 외부 통합 사용 시)
cp .env.example .env
# .env 편집: OPENAI_API_KEY, LAW_API_KEY 입력 (gitignored)

# 3. legalize-kr 클론 (선택 — 현행 법령 본문 사용 시)
mkdir -p external && git clone https://github.com/legalize-kr/legalize-kr external/legalize-kr

# 4. 자가진단 (외부 통합 포함)
PYTHONPATH=src python3 -m jaramlaw_agent doctor --deep

# 5. 시나리오 데모 (3개 — seeded mode, API 키 없이 동작)
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario A --output runs/A.json
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario B --output runs/B.json --print-first-card
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario C --output runs/C.json

# 6. 신규 통합 명령어 (T16-T21)
PYTHONPATH=src python3 -m jaramlaw_agent search-law "출산휴가"           # 시드 + legalize-kr
PYTHONPATH=src python3 -m jaramlaw_agent search-law "근로기준법" --remote # +법제처 Open API
PYTHONPATH=src python3 -m jaramlaw_agent fetch-article labor-standards-74 --article 제74조
PYTHONPATH=src python3 -m jaramlaw_agent ask "둘째 임신했는데 출산휴가 어떻게 신청하나요?" --persona P1

# 7. 테스트 (63 PASS 보장)
PYTHONPATH=src python3 -m pytest tests/ -v
```

## 외부 통합 (선택)

| 통합 | 환경변수 | 용도 |
|---|---|---|
| **legalize-kr** | `LEGALIZE_KR_PATH` | 한국 현행 법령 본문 (3060 디렉토리, Git 저장소) |
| **법제처 Open API** | `LAW_API_KEY` (OC 파라미터) | 실시간 법령 검색 (https://open.law.go.kr) |
| **OpenAI** | `OPENAI_API_KEY` | 자연어 질문 → 매칭 법령 컨텍스트 + LLM 답변 |
| **OpenRouter** | `OPENROUTER_API_KEY` | (옵션) 대체 LLM 제공자 |

모든 외부 통합은 **graceful degrade** — 키 없으면 자동 비활성, 시드 데이터로만 동작.

### 보안 주의
- `.env` 파일은 **.gitignore 처리**됨. 절대 commit 금지.
- API 키는 메모리에만 보유, 로그에 마스킹 처리 (`config.redact_secret`).
- `key.md` 같은 외부 평문 파일은 jaramlaw-agent **외부**에 보관 권장.

---

## 프로젝트 구조

```text
jaramlaw-agent/
├── spec/                    # SDD 산출물 — constitution, spec, plan, tasks, traceability
├── workflows/               # workflow YAML (family-legal-jaramlaw)
├── agents/                  # 9개 에이전트 contract
├── handoff/                 # delegation-board
├── data/seed/
│   ├── laws/                # 22개 법령 시드 yaml
│   ├── supports/            # 11개 정부지원 시드 yaml
│   └── scenarios/           # 3개 시나리오 fixture (A/B/C)
├── src/jaramlaw_agent/      # 14노드 워크플로우 Python 구현
│   ├── models.py
│   ├── family_context.py    # F1 라이프스테이지 분류
│   ├── law_retrieval.py     # F4 hybrid retrieval (BM25 + tag + RRF)
│   ├── support_matching.py  # F2 자격 매칭 + D-day
│   ├── document_drafter.py  # F4 신청서·신고서 초안 (학원 환불액 계산 포함)
│   ├── rights_card.py       # F6 권리 카드
│   ├── calendar_gen.py      # F3 영유아 건강검진 + 예방접종 + 학사 iCal
│   ├── guard.py             # AgentShield: PII 마스킹 + safety routing
│   ├── verifier.py          # Atomic Claim citation 검증
│   ├── human_review.py      # 고위험 → 전문가 라우팅
│   ├── orchestrator.py      # 14노드 실행 + Multi-Agent Board
│   ├── workflow.py          # YAML 파서 + validator
│   ├── audit.py             # 구조화 audit log
│   └── cli.py               # 진입점
├── tests/                   # 65 unit + e2e PASS
├── examples/                # scenario A/B/C 실행 예제
├── audit_logs/              # JSON audit log
├── runs/                    # JSON final_report
└── docs/                    # 아키텍처 + SKILLs 통합 가이드
```

---

## Operational Agent Layer

JaramLaw now includes the formal operations layer expected from a complete
AI-agent system:

- `agents/team.yaml` central team topology
- `workflows/jaramlaw-model-routing.workflow.yaml` role routing, isolation, and budget metadata
- `workflows/jaramlaw-brain.workflow.yaml` metadata-only memory workflow
- `src/jaramlaw_agent/model_routing.py`, `budget_guard.py`, `memory_rag.py`, `observability.py`, `cross_model_verifier.py`
- UI Ops APIs for workflow status, audit logs, traces, local publish, and batch consult

See [`docs/operational-agent-architecture.md`](docs/operational-agent-architecture.md).

---

## 8개 킬러 기능

1. **F1 가족 프로필 매니저** — 생년월일 → 라이프스테이지 자동 분류 + 특수상황 태그
2. **F2 지원 매칭 엔진** — 받을 자격 있는 정부지원 자동 매칭 + 신청기한 D-day
3. **F3 우리아이 법령 캘린더** — 영유아 건강검진 + 예방접종 + 학사 + 부모급여 전환 시점 iCal
4. **F4 분쟁 자가진단 + 신고 워크플로우** — 학원 환불 / 어린이집 사고 / 육아휴직 거부 등 시나리오 → 신고경로 + 신고서 초안
5. **F5 문서 업로드 분석** — (MVP stub, 후속 OCR 통합)
6. **F6 권리 카드** — 1장짜리 "법령 명함" markdown + JSON
7. **F7 법령 변화 영향 푸시** — (MVP stub)
8. **F8 똑똑맘 콘텐츠 연계** — (MVP stub)

상세: [`spec/spec.md`](spec/spec.md)

---

## 14노드 아키텍처

```
intake → input_guard → family_context → law_retrieval → support_matching →
parallel_expert_board (5 에이전트) → document_drafter → verify_atomic_claims →
human_review_gate → rights_card_gen + calendar_gen + freshness_monitor → audit_log

(safety triggered ? → safety_routing 직행)
```

상세: [`spec/plan.md`](spec/plan.md), [`docs/architecture.md`](docs/architecture.md)

---

## Constitution 5원칙 (반드시 강제)

1. **변호사법 회피** — 법률 자문이 아닌 양육 정보 보조 도구
2. **Citation Required** — 모든 법령 claim은 (law, article, effective_date, source_url) 인용 필수
3. **Safety-First Routing** — 학대/응급/자해/가정폭력 신호 → 즉시 전문기관
4. **자동 신고 발사 금지** — 신고서 "초안"만, 외부 시스템 직접 호출 X
5. **PII 마스킹** — 아이 이름·주민번호·정확 주소 자동 마스킹

상세: [`spec/constitution.md`](spec/constitution.md)

---

## 시나리오 데모 (3개)

### 시나리오 A — 둘째 임신 + 첫째 4세, 워킹맘 (서울 마포)

```bash
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario A
```

기대 출력: 지원 매칭 4건, 권리카드 4+장, 캘린더 8+건, safety 미발동.

### 시나리오 B — 초1 딸 학원 환불 거부 (화성)

```bash
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario B --print-first-card
```

기대 출력: 환불 요청서 초안 1건, 환불액 ≈641,667원 (학원법 시행령 별표4 일할 계산).

### 시나리오 C — 어린이집 24개월 아들 사고

```bash
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario C
```

기대 출력: 권리카드 + 사고 경위서·CCTV 열람 신청서 초안, **safety 라우팅 발동 (1577-1391)**.

---

## AITHOR-Agent-Framework 매핑

| AITHOR 자산 | 자람법 활용 |
|---|---|
| Kernel + Domain Pack 패턴 | `family-legal` 도메인팩 |
| AgentShield | `guard.py` PIIRedactor + SafetySignalDetector |
| AgentCompiler 패턴 | `workflow.py` YAML 파서 + validator |
| AgentLoop | `freshness_monitor.py` (MVP stub) |
| Multi-Agent Board | `orchestrator._board_opinions()` 5 에이전트 |
| Citation-required RAG | `verifier.py` Atomic Claim |
| Human Review Gate | `human_review.py` |

---

## AI-research-SKILLs 활용

본 프로젝트는 [`AI-research-SKILLs`](../AI-research-SKILLs/) 67+ 카테고리 중 10개 직접 활용.
상세: [`docs/ai-research-skills-integration.md`](docs/ai-research-skills-integration.md)

| 스킬 | 활용 영역 |
|---|---|
| `14-agents` | Multi-Agent Board (5 에이전트 독립 검토) |
| `15-rag` | Hybrid BM25 + Tag + RRF |
| `07-safety-alignment` | Constitution 5원칙 + Safety routing |
| `11-evaluation` | Atomic claim verifier + e2e 시나리오 회귀 |
| `17-observability` | audit log 구조화 |
| `24-spec-driven-planner` | SDD 문서 (spec/plan/tasks/traceability) |
| `25-backend-architect` | 14노드 워크플로우 |
| `28-agent-memory` | FamilyProfile 컨텍스트 |
| `62-mcp-agent-protocols` | LAW.OS law_mcp_server 인터페이스 |
| `68-claude-native-agent-systems` | 에이전트 contract 패턴 |

---

## 출처 / 라이선스

- 제안서: [`자람법_제안서_v2.md`](../자람법_제안서_v2.md) (2026-05-22, cafe99)
- 기반: [`AITHOR-Agent-Framework`](../AITHOR-Agent-Framework/) (policy-finance-agent.workflow.yaml mirror)
- 라이선스: MIT
- 데이터 출처: law.go.kr (국가법령정보센터), open.law.go.kr 공동활용 API
- **고지**: 본 서비스는 양육 정보 보조 도구이며, 구체 사안에 대한 법률 자문이 아닙니다.

---

## 테스트 결과

```
65 passed, 4 skipped in 0.97s
```

전체 테스트:
- `test_models.py` (3)
- `test_family_context.py` (6)
- `test_law_retrieval.py` (5)
- `test_support_matching.py` (4)
- `test_document_drafter.py` (5)
- `test_guard.py` (8)
- `test_verifier.py` (4)
- `test_rights_card.py` (3)
- `test_calendar.py` (3)
- `test_workflow_validation.py` (3)
- `test_constitution.py` (6) — 5원칙 회귀 차단
- `test_scenarios.py` (4) — A/B/C e2e + deterministic 재현성
- `test_operational_governance.py` (4) — model routing, budget, memory, independent validation
- `test_mcp_server.py` (2) — MCP-style tool registry
