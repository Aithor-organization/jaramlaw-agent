# 자람법 (JaramLaw)

> **부모는 양육에 집중하고, 법령·지원·권리·의무는 자람법이 알아서 챙긴다.**
>
> 가족 라이프스테이지 법령·정책 AI 동반자.

---

## 1. 이 프로젝트가 존재하는 이유

한국의 부모가 마주하는 법·제도는 **아이가 자라는 속도만큼 계속 바뀐다.** 임신하면 출산휴가와 부모급여가, 아이가 어린이집에 가면 보육료와 아동학대 신고 절차가, 초등학교에 들어가면 학원 환불 규정과 학교폭력 대응이 각각 다른 법령·다른 기관·다른 기한으로 흩어져 있다. 부모는 대부분 **자신에게 어떤 권리가 있는지조차 모른 채** 기한을 넘기고, 받을 수 있는 지원을 놓치고, 분쟁이 생겨도 어디에 무엇을 요구할 수 있는지 알지 못한다.

자람법의 진짜 목적은 "법을 검색해 주는 것"이 아니다. **부모가 묻기 전에, 지금 이 가족에게 적용되는 법·지원·권리·의무를 먼저 알려주는 것**이다. 입력은 아이의 생년월일·지역·가족 구성·최근 사건 하나면 충분하다. 그 최소한의 사실에서 라이프스테이지를 계산하고, 해당하는 법령과 정부지원을 매칭하고, 놓치면 안 되는 기한을 달력에 얹고, 실제로 받은 문서(학원 환불 거부, 어린이집 사고 통지)에 대한 대응 초안까지 만들어 낸다.

그리고 이 도구가 다루는 것은 **아동의 개인정보와 법률적 조언**이라는, 틀리면 사람이 다치는 영역이다. 그래서 자람법은 "그럴듯한 답"을 빠르게 내는 대신, **틀린 답을 내보내지 않는 것**을 시스템의 1순위로 둔다. 이 README의 절반이 보안·검증·안정성에 할애된 것은 그 우선순위의 반영이다.

### 무엇이 아닌가 (경계)

- **법률 자문이 아니다.** 자람법은 양육 정보 보조 도구다. 구체 사건의 승소 가능성·소송 전략을 답하지 않는다 (변호사법 회피 — Constitution 원칙 1).
- **자동 신고 시스템이 아니다.** 신고서·신청서는 항상 "초안"으로만 만든다. 외부 기관에 무언가를 대신 제출하지 않는다 (원칙 4).
- **범용 챗봇이 아니다.** 제공된 법령 컨텍스트 밖의 법은 인용하지 않는다. 모르면 "확실하지 않음, 법제처·전문가 확인 권장"이라고 답한다 (원칙 2).

---

## 2. 시스템이 작동하는 원리

자람법은 하나의 요청을 **14개의 노드**로 이루어진 워크플로우로 처리한다. 각 노드는 앞 노드의 출력을 받아 다음으로 넘기며, 전 과정이 감사 로그로 남는다.

```
intake → input_guard → family_context → law_retrieval → support_matching →
parallel_expert_board(5) → document_drafter → verify_atomic_claims →
ai_answer(생성) → output_guard → adversarial_critic → human_review_gate →
rights_card + calendar → audit_log

(안전 신호 감지 시 → 일반 흐름 우회, safety_routing 직행)
```

핵심 설계 사상은 하나다: **결정론이 할 수 있는 일은 LLM에게 맡기지 않는다.** 라이프스테이지 계산, 지원 자격 판정, 환불액 산정, PII 마스킹, 인용 검증 — 이 모두는 규칙과 계산으로 처리한다. LLM은 오직 마지막에 "부모가 읽을 자연어 안내"를 쓰는 데만 쓰고, 그 답변조차 인용 가능한 법령 컨텍스트 안에 가둔다. 이렇게 하면 답이 틀릴 수 있는 표면적이 최소화된다.

### 노드별 역할

| 노드 | 하는 일 | 구현 |
|---|---|---|
| **intake** | 부모 입력 수신 (생년월일·지역·가족·사건) | `orchestrator.py` |
| **input_guard** | PII 마스킹 + 인젝션 차단 + 안전신호 감지 | `guard.py` + `agentshield_bridge.py` |
| **family_context** | 생년월일 → 라이프스테이지(임신/영아/유아/초등…) + 특수상황 태그 | `family_context.py` |
| **law_retrieval** | 하이브리드 검색(BM25 + 태그 + RRF)으로 적용 법령 선별 | `law_retrieval.py` + `law_live.py`(법제처 실시간 보강) |
| **support_matching** | 받을 자격 있는 정부지원 매칭 + 신청기한 D-day | `support_matching.py` |
| **parallel_expert_board** | 5개 에이전트가 독립 관점으로 교차 검토 | `orchestrator._board_opinions()` |
| **document_drafter** | 신청서·신고서 초안 생성 (환불액 일할 계산 포함) | `document_drafter.py` |
| **verify_atomic_claims** | 모든 법령 주장을 (법령명·조문·시행일·출처) 4요소로 검증 | `verifier.py` |
| **ai_answer** | 인용 가능한 법령만 컨텍스트로 자연어 안내 생성 | `openai_client.py` |
| **output_guard** | LLM 답변의 PII·시크릿 마스킹 + 근거 없는 단정 탐지 | `agentshield_bridge.py` |
| **adversarial_critic** | **다른 회사 모델**로 답변을 적대 검증 → 치명 결함 시 차단 | `adversarial_critic.py` |
| **human_review_gate** | 고위험 사안을 전문가 검토로 라우팅 | `human_review.py` |
| **rights_card + calendar** | 1장짜리 권리 카드 + 건강검진·예방접종·학사 iCal | `rights_card.py`, `calendar_gen.py` |
| **audit_log** | 전 과정을 구조화 로그로 영속화 | `audit.py`, `observability.py` |

### 8개 킬러 기능

1. **F1 가족 프로필 매니저** — 생년월일 → 라이프스테이지 자동 분류 + 특수상황 태그
2. **F2 지원 매칭 엔진** — 받을 자격 있는 정부지원 자동 매칭 + 신청기한 D-day
3. **F3 우리아이 법령 캘린더** — 영유아 건강검진 + 예방접종 + 학사 + 부모급여 전환 시점 iCal
4. **F4 분쟁 자가진단 + 신고 워크플로우** — 학원 환불 / 어린이집 사고 / 육아휴직 거부 → 신고경로 + 신고서 초안
5. **F5 문서 업로드 분석** — *(MVP stub, 후속 OCR 통합 예정)*
6. **F6 권리 카드** — 1장짜리 "법령 명함" markdown + JSON
7. **F7 법령 변화 영향 푸시** — *(MVP stub)*
8. **F8 똑똑맘 콘텐츠 연계** — *(MVP stub)*

---

## 3. Constitution — 절대 강제 5원칙

자람법의 모든 노드는 다음 5원칙 위에서만 동작한다. 이 원칙들은 테스트(`test_constitution.py`)로 회귀 차단된다.

1. **변호사법 회피** — 법률 자문이 아닌 양육 정보 보조 도구
2. **Citation Required** — 모든 법령 주장은 (법령명, 조문, 시행일, 출처 URL) 4요소 인용 필수
3. **Safety-First Routing** — 학대/응급/자해/가정폭력 신호 → 일반 답변 대신 즉시 긴급 연락처
4. **자동 신고 발사 금지** — 신고서는 "초안"만, 외부 시스템 직접 호출 금지
5. **PII 마스킹** — 아이 이름·주민번호·정확 주소 자동 마스킹

상세: [`spec/constitution.md`](spec/constitution.md)

---

## 4. 보안 · 안정 (틀린 답을 내보내지 않기)

아동 PII와 법률 조언을 다루는 시스템에서 보안은 부가 기능이 아니라 **본체**다. 자람법은 입력·출력 양쪽에 가드를 두고, 실패하면 조용히 넘어가지 않고 멈추는 fail-closed 원칙을 따른다.

### 4-1. AgentShield 런타임 가드 (`agentshield_bridge.py`)

입력과 출력을 실제로 검사하는 런타임 계층. (형제 저장소 `AgentShield`의 `RuntimeGuard`를 3-tier로 로드 — 설치본 → 형제 저장소 → `AGENTSHIELD_PATH`. 미설치 시 보호가 약해지되 상담은 계속되는 graceful degrade, 그 사실을 리포트에 실측 기록.)

- **입력 가드** — 프롬프트 인젝션(난독화·다국어 포함)을 탐지해 **차단**하고, 이메일·카드·여권·계좌·IP 등 확장 PII를 마스킹한 payload를 downstream에 실제로 흘려보낸다(원본 replay 금지). 인젝션이 감지되면 파이프라인 진입 자체를 막는다 — 주석만 달고 통과시키지 않는다.
- **출력 가드** — LLM 답변에 섞여 나올 수 있는 API 키·토큰·PII를 마스킹하고, "100% 보장"·"절대 안전" 같은 근거 없는 절대 단정을 탐지해 부모 화면에 경고를 덧붙인다.
- **안전 우선** — 학대·응급 등 안전 신호가 잡힌 입력은 인젝션 의심이 있어도 차단하지 않는다. 신고하려는 부모를 단어 하나로 막는 것이 가장 큰 사고이기 때문이다. 3인칭 신고 서술("어린이집이 지침을 무시하고 방치했습니다")은 실제 공격과 구별해 오탐 차단을 방지한다.

### 4-2. 교차 모델 적대 검증 (`adversarial_critic.py`)

결정론 게이트는 산출물의 **형식**만 본다. "[민법 제836조의2]에 따라 100% 승소한다" 같은 문장은 인용 4요소를 갖추고 있어 모든 형식 게이트를 통과한다. 이 구멍을 막기 위해, 부모가 실제로 읽을 답변 텍스트를 **답변을 생성한 모델과 다른 회사의 모델**(기본 `x-ai/grok-4.5`, 폴백 `anthropic/claude-sonnet-5`)로 적대 검증한다.

- 검증 대상 6종: 환각 인용, 권한 초과, 무단 법률자문, 예외 누락, 시행 전/폐지 법령, 근거 없는 단정
- 치명 3종(환각 인용·권한 초과·무단 자문)은 모델의 자기 신고를 무시하고 **강제 BLOCK** — 답변을 보류하고 원문은 보존한 채 전문가 검토로 승격
- 제3자로 나가는 것: 마스킹된 질문 + 답변 + 법령 컨텍스트. **나가지 않는 것: 가족 프로필·생년월일·지역.** `JARAMLAW_ENABLE_CRITIC=0`으로 차단 가능

> 참고: `cross_model_verifier.py`는 이름과 달리 2차 모델을 호출하지 않는 **결정론 리뷰어**다. 진짜 교차 모델 검증은 위 `adversarial_critic.py`가 담당한다.

### 4-3. 그 외 보안 조치

- **법제처 API https 강제** — OC 키가 쿼리스트링에 실려 나가므로 base URL을 https로 승격(http 입력 시에도). 평문 전송 차단.
- **PII 로그 마스킹** — API 키는 메모리에만 보유, 로그·감사 로그에 `config.redact_secret`로 마스킹.
- **`.env` 절대 커밋 금지** — `.gitignore` 처리. `.env.*` 전체 커버.
- **UI 인증 게이트** — 상담 이력·감사 로그를 다루는 모든 라우트에 `requireOperatorAuth`. 외부 바인딩 시 `JARAMLAW_API_TOKEN` 없으면 부팅 거부(fail-closed).
- **레이트리밋** — 공개 상담 엔드포인트에 슬라이딩 윈도우 제한(프로세스당 Python 프로세스 spawn 비용 DoS 차단).

### 4-4. 안정성 (외부 장애에서 살아남기)

- **재시도 + 회로 차단** (`agentshield_bridge.resilient_call`) — 외부 호출(OpenAI·법제처)의 일시적 실패를 지수 백오프로 재시도하고, 연속 실패가 쌓이면 회로를 열어 죽은 API를 매번 기다리지 않는다. 재시도해도 소용없는 영구 오류(4xx)는 재시도·회로 계산에서 제외한다.
- **graceful degrade** — 모든 외부 통합(법제처·OpenAI·OpenRouter·legalize-kr)은 키·네트워크가 없으면 자동 비활성, 시드 데이터로 상담을 끝까지 완주한다. "무대에서 죽는 것보다 시드로 계속하는 게 낫다"가 원칙.
- **안전 차단 vs 조회 실패 구분** — 안전 신호로 상담을 멈춘 것과 네트워크 실패는 다른 상태로 기록해, 화면에 잘못된 오류 경고가 뜨지 않게 한다.

---

## 5. 스스로 진화하는 학습 패턴

자람법은 상담을 거칠수록 **다음 상담이 나아지는** 폐루프 학습을 갖는다. 저장소(`brain.py`)와 배선(`learning.py`)이 짝을 이룬다.

### 5-1. 핵심 사상 — 텍스트 힌트가 아니라 실제 파라미터

대부분의 "학습하는 에이전트"는 과거 기록을 텍스트로 만들어 LLM 프롬프트에 붙인다. 조사해 보면 그런 학습은 **대부분 발동하지 않는다** — LLM의 선의에 기대기 때문이다. 자람법은 다르게 한다. `learning.plan()`은 과거 패턴을 읽어 **이번 실행의 실제 숫자를 바꾼다.**

- **검색 가산점** (`law_boosts`) — 과거 같은 주제에서 실제로 인용된 법령을 이번 검색에서 위로 끌어올린다. 가산점은 `2.0 × confidence`로, 시나리오 태그 매칭(4.0)보다 작게 잡는다 — 학습이 검색을 거들어야지 대체하면 새 법령을 영원히 못 찾기 때문.
- **답변 토큰 상한** (`max_answer_tokens`) — 과거 이 주제에서 답변이 상한에 걸려 잘렸던 이력이 있으면, 이번엔 미리 상한을 올린다(+1000, 최대 4000).

### 5-2. 결정론적 성패 판정

`classify_outcome()`은 **LLM에게 자기 성적을 매기게 하지 않는다.** 이번 세션에서 실측한 신호만 쓴다: 답변이 잘렸는가, 근거 법령을 줬는데 인용을 안 했는가, 안전 라우팅이 걸렸는가. 특히 `verified_ratio`(인용 4요소의 '존재'만 세는 지표)는 **의도적으로 배제**한다 — 항상 1.0이 나와 위조 법령도 통과시키는, "신호가 아니라 도장"이기 때문이다.

### 5-3. 적용 결과 되먹임 (닫힌 고리)

`brain.record_application_outcome()`이 이 학습 시스템의 심장이다. 단순히 "이런 패턴이 있었다"를 집계하는 게 아니라, **적용했던 패턴이 실제로 통했는지**를 되먹인다 — 통하면 confidence +0.03(상한 0.98), 실패하면 −0.10(하한 0.10). 도움이 안 되는 패턴은 스스로 신뢰도가 떨어져 밀려나고, 반복해서 통하는 패턴만 살아남는다.

### 5-4. 학습이 PII를 새지 않도록

학습 키는 `brain.LEARNABLE_TAGS`의 **닫힌 어휘**로만 만든다. 질의 원문(한글)이 학습 저장소에 흘러들면 아이 이름·상황이 남을 수 있으므로, `assert_clean()` PII 게이트가 화이트리스트 키 + 한글/날짜/주민번호/전화/이메일 정규식으로 차단한다. 저장 내용(`content`)은 영문·기계 판독용 사유만 담고 질의 원문은 절대 넣지 않는다.

### 5-5. 영속화

- 저장 위치: `.jaramlaw-brain/` (환경변수 `JARAMLAW_BRAIN_DIR`로 오버라이드)
- 파일: `pending_patterns.jsonl`(대기) → `patterns.jsonl`(승격) + `apply.log`(적용 이력)
- 임베딩·외부 의존성 0. JSONL append + 원자적 재작성.
- 학습·비평가는 `orchestrator.run_workflow` 안에서 기본 활성(`enable_learning`/`enable_critic`), CLI 별도 서브커맨드 아님.

---

## 6. 유지 · 보수 · 운영

배포 전에 "이 변경이 시스템을 나쁘게 만들지 않는가"를 기계적으로 검증하는 운영 게이트를 갖춘다. (형제 저장소 `AgentLoop`을 유지보수 게이트로 사용.)

- **`ops/agentloop/jaramlaw.policy.json`** — 커밋되는 "진실의 원본". SLO·임계값·컴포넌트 그래프·회귀 baseline을 한 파일에 둔다.
- **`scripts/agentloop_observations.py`** — 감사 로그·트레이스·캐시 등 **실제로 측정된 런타임 산출물에서만** 관측값을 방출한다. 측정 못 한 필드는 `_coverage.unmeasured`에 정직하게 기록한다.
- **`scripts/run_agentloop_gate.py`** — 게이트 러너. policy와 관측값의 컴포넌트 id 집합이 정확히 일치하는지 단언(`assert_ids_align` — 오타 하나로 게이트가 가짜 초록이 되는 것을 하드 에러로 방어)한 뒤, AgentLoop CLI로 검증·분석한다. `--fail-on-block` 시 치명 결과에 exit 2.
- **CI 배선** — `.github/workflows/agentloop-gate.yml`. 계약은 `tests/test_agentloop_gate.py`가 고정.

운영 설계의 핵심 원칙은 학습과 동일하다: **측정하지 않은 값은 쓰지 않는다. 침묵은 합격이 아니다.** 현재 게이트는 report-only이며, 런 20건+ 축적 + 토큰 텔레메트리 해소 + 실단가 주입 후 blocking으로 전환할 계획이다.

현재 운영 준비도의 정직한 상태(무엇이 아직 측정 안 되는가, P0/P1 백로그)는 [`docs/operational-readiness.md`](docs/operational-readiness.md)에 상세히 기록되어 있다.

---

## 7. 최적화

- **비용 인지 모델 라우팅** (`model_routing.py`) — 국면에 맞는 모델을 고른다. 평시 분류·안내는 빠르고 싼 모델, 안전 신호·심층 사안은 추론 모델로 올린다. 예산 가드(`budget_guard.py`)가 per-run 비용 상한을 강제한다.
- **프롬프트 캐시 활용** — 같은 법령 컨텍스트가 반복되면 OpenAI가 자동 재사용하는 입력 토큰(`cached_tokens`)을 실측해 실비용 계산에 반영한다.
- **답변 토큰 상한 튜닝** — 800토큰에서 학교폭력·CCTV처럼 절차가 긴 질문의 본문이 통째로 잘리던 문제를 실측으로 확인해 2000으로 상향(+학습이 주제별로 4000까지 동적 상향).
- **하이브리드 검색** — BM25 + 태그 매칭 + RRF 융합으로, 키워드와 의미를 함께 반영.
- **파라미터 폴백** — 모델별로 거부하는 파라미터(gpt-5.x의 `temperature`/`max_tokens`)를 400 응답이 지목한 대로 떼고 재시도해 모델 목록 하드코딩을 피한다.

---

## 8. 빠른 시작

```bash
# 1. venv 셋업
cd ~/workspace/jaramlaw-agent
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml pytest

# 2. AgentShield 설치 (보안 가드 — 형제 저장소)
pip install -e ../AgentShield      # 또는 AGENTSHIELD_PATH 환경변수

# 3. .env 설정 (선택 — 외부 통합 사용 시)
cp .env.example .env
# .env 편집: OPENAI_API_KEY, LAW_API_KEY, OPENROUTER_API_KEY (gitignored)

# 4. legalize-kr 클론 (선택 — 현행 법령 본문)
mkdir -p external && git clone https://github.com/legalize-kr/legalize-kr external/legalize-kr

# 5. 자가진단
PYTHONPATH=src python3 -m jaramlaw_agent doctor --deep

# 6. 시나리오 데모 (API 키 없이 seeded mode 동작)
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario A --output runs/A.json
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario B --print-first-card
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario C

# 7. 통합 명령어
PYTHONPATH=src python3 -m jaramlaw_agent search-law "출산휴가"
PYTHONPATH=src python3 -m jaramlaw_agent search-law "근로기준법" --remote   # +법제처 Open API
PYTHONPATH=src python3 -m jaramlaw_agent fetch-article labor-standards-74 --article 제74조
PYTHONPATH=src python3 -m jaramlaw_agent ask "둘째 임신했는데 출산휴가 어떻게 신청하나요?" --persona P1

# 8. 테스트
PYTHONPATH=src python3 -m pytest tests/ -q
```

### UI 실행

```bash
cd jaramlaw-agent-ui
npm install
npm run dev        # 기본 127.0.0.1 loopback (외부 노출 시 JARAMLAW_API_TOKEN 필수)
```

부모용 상담 입력·이력·검토 결과·전문가 확인 패널을 한 화면에 배치했고, Python 워크플로우와 운영 계층 상태를 함께 표시한다.

![JaramLaw Agent 기본 UI](docs/assets/jaramlaw-ui-basic.png)

---

## 9. 외부 통합 (전부 선택 — graceful degrade)

| 통합 | 환경변수 | 용도 |
|---|---|---|
| **AgentShield** | `AGENTSHIELD_PATH` (또는 `pip install -e`) | 입력/출력 런타임 가드 (미설치 시 보호 degrade) |
| **legalize-kr** | `LEGALIZE_KR_PATH` | 한국 현행 법령 본문 (Git 저장소) |
| **법제처 Open API** | `LAW_API_KEY` (OC 파라미터) | 실시간 법령 검색 (https, open.law.go.kr) |
| **OpenAI** | `OPENAI_API_KEY` | 자연어 질문 → 매칭 법령 컨텍스트 + 답변 |
| **OpenRouter** | `OPENROUTER_API_KEY` | 교차 모델 적대 비평가 (다른 회사 모델) |

키가 없으면 해당 통합만 자동 비활성되고, 나머지는 시드 데이터로 동작한다.

---

## 10. 프로젝트 구조

```text
jaramlaw-agent/
├── spec/                        # SDD 산출물 — constitution, spec, plan, tasks
├── workflows/                   # workflow YAML (family-legal + model-routing + brain)
├── agents/                      # 에이전트 contract + team.yaml
├── data/seed/                   # 법령 / 정부지원 / 시나리오(A/B/C) 시드
├── src/jaramlaw_agent/          # 14노드 워크플로우 Python 구현
│   ├── orchestrator.py          # 14노드 실행 + Multi-Agent Board
│   ├── family_context.py        # 라이프스테이지 분류
│   ├── law_retrieval.py         # 하이브리드 검색 (BM25 + tag + RRF)
│   ├── law_live.py              # 법제처 실시간 조문 보강
│   ├── support_matching.py      # 지원 자격 매칭 + D-day
│   ├── document_drafter.py      # 신청서·신고서 초안 (환불액 계산)
│   ├── rights_card.py           # 권리 카드
│   ├── calendar_gen.py          # 건강검진·예방접종·학사 iCal
│   ├── guard.py                 # PII 마스킹 + safety 신호 (로컬 계층)
│   ├── agentshield_bridge.py    # AgentShield 실연결 (입력/출력 가드 + resilience)
│   ├── adversarial_critic.py    # 교차 모델 적대 검증
│   ├── openrouter_client.py     # OpenRouter (다른 회사 모델)
│   ├── verifier.py              # Atomic Claim citation 검증
│   ├── human_review.py          # 고위험 → 전문가 라우팅
│   ├── learning.py              # 자기진화 학습 배선 (plan/observe)
│   ├── brain.py                 # 학습 저장소 (capture/merge/search/되먹임)
│   ├── model_routing.py         # 비용 인지 모델 선택
│   ├── budget_guard.py          # per-run 예산 상한
│   ├── openai_client.py         # OpenAI (재시도 + 파라미터 폴백)
│   ├── observability.py         # 트레이스
│   ├── audit.py                 # 구조화 audit log
│   └── cli.py                   # 진입점 (doctor/demo/search-law/fetch-article/ask)
├── ops/agentloop/               # 운영 게이트 정책 (SLO/임계값/baseline)
├── scripts/                     # AgentLoop 관측 + 게이트 러너
├── tests/                       # 150 tests
├── .github/workflows/           # CI (agentloop-gate)
└── docs/                        # 아키텍처 + 운영 준비도 + SKILLs 통합
```

---

## 11. 시나리오 데모 (3개)

| 시나리오 | 상황 | 기대 출력 |
|---|---|---|
| **A** | 둘째 임신 + 첫째 4세, 워킹맘 (서울 마포) | 지원 매칭 4건, 권리카드 4+장, 캘린더 8+건, safety 미발동 |
| **B** | 초1 딸 학원 환불 거부 (화성) | 환불 요청서 초안, 환불액 ≈641,667원 (학원법 시행령 별표4 일할 계산) |
| **C** | 어린이집 24개월 아들 사고 | 권리카드 + 사고 경위서·CCTV 열람 신청서 초안, **safety 라우팅 발동 (1577-1391)** |

```bash
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario A
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario B --print-first-card
PYTHONPATH=src python3 -m jaramlaw_agent demo --scenario C
```

---

## 12. 설계 계보 (정직한 표기)

자람법의 아키텍처는 형제 저장소들의 **사상을 미러링**했다. 단, 이들은 **코드 의존성이 아니라 개념적 참조**다 — 자람법 `src/`에 이 프레임워크들의 import는 없다(전부 stdlib + pyyaml).

| 형제 저장소 | 자람법에서의 개념적 반영 |
|---|---|
| **AITHOR-Agent-Framework** | Kernel + Domain Pack 사상 → `family-legal` 워크플로우 구조 (import 없음, 구조 미러) |
| **AgentShield** | `agentshield_bridge.py`가 실제로 `RuntimeGuard`를 로드 (유일한 실 코드 연결) |
| **AgentLoop** | `ops/` + `scripts/`가 실제로 AgentLoop CLI를 호출 (운영 게이트) |

> **왜 이렇게 명시하는가**: "X 프레임워크 기반"이라는 문구는 import·의존성·레지스트리 등록으로 검증되어야 한다. 자람법은 AITHOR를 코드로 import하지 않으므로, "AITHOR 기반"은 사상적 계승이지 런타임 의존이 아니다. AgentShield·AgentLoop만이 실제 코드로 연결된다.

---

## 13. 테스트

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
# 150 tests
```

주요 회귀 차단:
- `test_constitution.py` — 5원칙 회귀 차단
- `test_scenarios.py` — A/B/C e2e + 결정론 재현성
- `test_agentshield_integration.py` — 입력/출력 가드 통합 경로 (인젝션 차단·PII 마스킹·안정성)
- `test_adversarial_critic.py` — 교차 모델 비평가 BLOCK 강제
- `test_learning_loop.py` — 학습 폐루프 (plan → observe → 되먹임)
- `test_agentloop_gate.py` — 운영 게이트 계약
- `test_operational_governance.py` — 모델 라우팅·예산·메모리·독립 검증

---

## 출처 / 라이선스

- 라이선스: MIT
- 데이터 출처: law.go.kr (국가법령정보센터), open.law.go.kr 공동활용 API
- **고지**: 본 서비스는 양육 정보 보조 도구이며, 구체 사안에 대한 법률 자문이 아닙니다.
