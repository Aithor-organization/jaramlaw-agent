# 배포 전 운영 준비 상태 (Operational Readiness)

> 이 문서의 백로그는 의견이 아니라 **게이트가 기계적으로 도출한 결과**다.
> 항목마다 "왜 배포 전에 중요한가 / 정확한 수정 / 초록이 되는 판정 기준"이 붙어 있고,
> 판정 기준은 대부분 이미 테스트나 게이트 패스로 존재한다.
>
> 측정 시점: 2026-07-14 · 실측 런 4건 (LLM 경로 3건)

---

## 1. 유지보수 게이트란 무엇인가

`AgentLoop`(형제 저장소, 에이전트 lifecycle 유지보수 컴파일러)에 이 저장소가 **실제로 측정한**
런타임 신호를 넣어, 배포를 막아야 할 상태인지 판정한다.

```bash
# 게이트 실행 (report-only — 빌드를 깨지 않는다)
python scripts/run_agentloop_gate.py

# 배포 승격 판정 — block/rollback이면 exit 2
python scripts/run_agentloop_gate.py --fail-on-block

# 현재 측정값을 회귀 baseline으로 동결 (아래 §5 주의사항 필독)
python scripts/run_agentloop_gate.py --update-baseline
```

| 파일 | 역할 |
|---|---|
| `ops/agentloop/jaramlaw.policy.json` | **커밋되는 진실의 원본** — SLO·임계값·컴포넌트 그래프·회귀 baseline |
| `scripts/agentloop_observations.py` | `audit_logs/`에서 **측정된** 지표만 방출 |
| `scripts/run_agentloop_gate.py` | AgentLoop 호출 + 커버리지 단언 + 리포트 |
| `tests/test_agentloop_gate.py` | 위 계약을 고정하는 회귀 테스트 (15건) |
| `.github/workflows/agentloop-gate.yml` | CI 배선 (report-only) |

### 설계 규칙 두 가지 (건드리기 전에 읽을 것)

**① 측정하지 않은 값은 쓰지 않는다.**
AgentLoop의 패스는 지표가 없으면 `Number.isFinite` 가드로 조용히 스킵한다. 즉 **날조한 숫자와
측정한 숫자를 게이트는 구분하지 못한다.** 그래서 방출기는 근거를 댈 수 있는 필드만 쓰고,
채우지 못한 것은 `_coverage.unmeasured`에 남긴다. 러너는 이걸 항상 출력한다 —
**빈 리포트가 "건강함"으로 읽히면 안 되고, "우리가 안 봤음"으로 읽혀야 하기 때문이다.**

**② 컴포넌트 id는 policy와 observations가 정확히 일치해야 한다.**
AgentLoop은 관측을 id로 찾고, 모르는 id는 에러가 아니라 **"데이터 없음"**으로 취급한다.
따라서 id에 오타가 하나 나면 → 전 패스 스킵 → **게이트가 초록으로 통과한다.**
배포 게이트에서 이보다 나쁜 실패는 없다. `run_agentloop_gate.assert_ids_align()`이 이걸
하드 에러로 막고, `tests/test_agentloop_gate.py`가 그 동작을 고정한다.

> ⚠️ **AgentLoop의 JB 어댑터(`src/core/jb.js`)를 복사하지 말 것.** 죽은 키가 3개 있다 —
> `trajectoryDriftDistance`(코드는 `trajectoryDriftMax`를 읽음), `toolCallErrorMax`(미사용),
> `baseline.judgeScores`(코드는 `baseline.judge.scores`를 읽음 — 그래서 JB의 `JUDGE_REGRESSION`은
> 한 번도 발화한 적이 없다). 이 저장소는 **코드가 실제로 읽는 키**를 쓴다.

---

## 2. 현재 게이트 결과 (2026-07-14 실측)

```
status=review  action=pause_canary  (0 error / 2 warn / 0 info, 4 run)

[WARN] TRACE_INCOMPLETE  agent:jaramlaw    trace completeness 60% below SLO 100% (missing tokens, finishReason)
[WARN] TRACE_INCOMPLETE  workflow:consult  trace completeness 60% below SLO 100% (missing tokens, finishReason)
```

**데이터가 없어 아무것도 검사하지 못한 패스 7개** — 이 침묵은 합격이 아니다:

| 비활성 패스 | 이유 |
|---|---|
| budget circuit breaker | `cost_usd`가 null (§3.2) |
| SRE reliability (tail latency) | 런 3건 — p95/p99에는 최소 20건 필요 |
| SRE reliability (MTTR) | 장애 기록 자체가 없음 |
| AgentShield security | 보안 리포트 미연동 (다른 세션 담당) |
| lifecycle / decommission | 폐기 절차 미정의 |
| maintenance overhead | 유지보수 비용 추적 없음 |
| backward compatibility | 모델 pin 일치 (정상 — 어긋나면 발화) |

---

## 3. 배포 전 백로그

### 3.0 🔴 P0 — CI가 존재하지 않았다 *(이번 변경으로 해소)*

**증거**: 이 작업 중 워킹트리에서 `orchestrator.py:341` `UnboundLocalError: scenario_type`이
발견됐다. `learning.plan(scenario_query, scenario_type, ...)`이 341줄에서 호출되는데 정의는
381줄이다. 안전차단 early-return(333줄) 이후의 **메인 경로**라 모든 상담 실행이 크래시한다.

- HEAD 커밋본은 키 없이 **0.81초 / 67 passed·4 skipped — 초록**
- 워킹트리(작업 중)는 **깨져 있음**
- 잡아줄 CI가 **없었다**

→ `.github/workflows/ci.yml` 추가. **비밀키 없이** 돈다 (테스트가 키 부재 시 seed/rule 모드로
degrade하도록 이미 설계돼 있음). 키를 *요구하기 시작하는* 테스트는 회귀다 — 프로덕션도
키 만료를 견뎌야 하기 때문이다.

실측: 신규 체크아웃 + 키 없음 + AgentShield 형제 → **128 passed / 4 skipped / 2.7초**.

> 위 `scenario_type` 회귀는 **다른 세션이 편집 중인 파일**이라 여기서 고치지 않았다.
> 확인 시점(2026-07-14) 기준 해당 세션이 이미 수정 완료.

### 3.0-bis 🔴 P0 — 테스트가 형제 저장소 없이는 skip이 아니라 **에러**난다

**증거**: 깨끗한 체크아웃(=CI, `.env` 없음)에서 `tests/test_agentshield_integration.py`의
**12건이 `ModuleNotFoundError: No module named 'agent_shield'`로 실패**한다.
로컬에서 초록인 이유는 개발 머신에 `~/workspace/AgentShield`가 있기 때문이다 — 전형적인
"내 컴퓨터에선 되는데" 배포 결함이다.

- `src/jaramlaw_agent/agentshield_bridge.py`는 **올바르게 설계돼 있다**:
  설치본 → `$AGENTSHIELD_PATH` → 형제 저장소 순으로 찾고, 없으면 `AGENTSHIELD_AVAILABLE=False`로 degrade.
- 문제는 **테스트 파일**이다. `agent_shield`를 직접 import해서 하드 실패한다 (skip하지 않는다).

**수정 (택1)**:
1. *(권장, 1줄)* `test_agentshield_integration.py` 상단에서
   `pytest.importorskip("agent_shield")` 또는 `AGENTSHIELD_AVAILABLE` 기준 skip —
   브리지가 이미 degrade를 지원하므로 테스트도 그래야 일관된다.
2. `pyproject.toml`에 AgentShield를 정식 의존성으로 선언.

**우회 (이미 적용)**: `ci.yml`이 AgentShield를 형제로 체크아웃하고 `AGENTSHIELD_PATH`를 주입한다.
체크아웃 실패 시 `::error::`로 원인을 명시해 알 수 없는 `ModuleNotFoundError` 대신
행동 가능한 메시지를 남긴다. 다만 이건 **우회지 수정이 아니다** — 위 1번이 진짜 수정이다.

> ⚠️ 이 파일 역시 **보안/안정 담당 세션의 작업물**이라 여기서 고치지 않았다.

### 3.1 🔴 P0 — 토큰 텔레메트리가 디스크에 없다

**왜 중요한가**: 토큰이 안 남으면 비용도, 캐시 효율도, truncation도 사후 추적이 불가능하다.
지금 `ai_answer`에는 `total_tokens`만 있고 `prompt_tokens`/`completion_tokens`/`finish_reason`이 없다.
→ 게이트가 `TRACE_INCOMPLETE 60%`로 잡고 있는 바로 그것.

**수정**: `orchestrator.py`가 `LlmAnswer`의 `prompt_tokens`/`completion_tokens`/`cached_tokens`/
`finish_reason`/`truncated`를 감사 로그에 기록. *코드는 이미 워킹트리에 있다 (미커밋).*
또한 `openai_client.classify()`는 `Optional[str]`만 반환해 **nano 분류 호출의 토큰이 통째로 유실**된다.

**초록 판정**: `tests/test_agentloop_gate.py::test_trace_checklist_goes_green_once_tokens_are_recorded` 통과
+ 게이트의 `observability` 게이트가 `pass`.

### 3.2 🔴 P0 — 실비용이 영원히 `null`

**왜 중요한가**: `budget_guard.actual_usage.cost_usd`는 `JARAMLAW_MODEL_PRICES`(JSON env)가
주입돼야 계산된다. 그런데 이 변수가 **`.env.example`에 없다** → 아무도 주입하지 않는다 →
비용 SLO·예산 서킷브레이커·비용 회귀 패스가 전부 죽어 있다.

`budget_guard.estimated_cost_usd`는 존재하지만 **tier별 하드코딩 상수 합산**이라 실과금과 무관하다.
방출기는 이걸 의도적으로 비용 지표로 쓰지 않는다 (쓰면 게이트가 가짜 숫자를 지키게 된다).

**수정**: `.env.example`에 `JARAMLAW_MODEL_PRICES` 문서화 + 실단가 주입.
누락된 `JARAMLAW_*` 변수 9개 전부 함께 문서화 —
`MODEL_CLASSIFY/ANSWER/DRAFT/CRITICAL/PIN`, `MODEL_PRICES`, `PER_RUN_BUDGET_USD`,
`MONTHLY_BUDGET_USD`, `DISABLE_MEMORY_CAPTURE`, `INJECTION_ENFORCE`.

**초록 판정**: 게이트의 `budget` 게이트가 비활성 → 활성으로 전환.

### 3.3 🟠 P1 — 구조화 로깅이 없다

`import logging` **사용 0건**. CLI는 `print()`만 쓴다. 로그 레벨/핸들러/포맷이 없어
프로덕션에서 로그 수집·필터링·알람이 불가능하다. `observability.py`의 `trace.jsonl`은
메타데이터 전용이라 대체재가 못 된다.

### 3.4 🟠 P1 — 감사 로그가 무한 증가

`audit_logs/*.json`이 건당 **75~85KB**로 쌓이고 **로테이션·보존정책·정리 로직이 없다**.
게다가 gitignore라 로컬 휘발성이다 — 배포 후 감사 추적이 필요한 **법률** 도메인에서
영속 저장소가 없는 것은 규제 리스크다.

### 3.5 🟠 P1 — 헬스체크 엔드포인트가 없다

`jaramlaw-agent-ui/server.ts`에 `/health` 라우트가 없다. 컨테이너/로드밸런서가 살아있음을
확인할 방법이 없다. CLI `jaramlaw doctor`는 있지만 `--deep`은 **실제 유료 ping**을 쏜다 —
헬스체크로 쓰면 안 된다.

### 3.6 🟠 P1 — "품질"이 인용 무결성일 뿐, 답변 정확도가 아니다

게이트의 `quality`/`judge`는 **구조 검사**다 (`verified_ratio` = 인용 검증 비율,
`independent_validation` = PASS/FAIL). 답변 내용이 법적으로 맞는지 평가하는 golden set이나
LLM judge는 **존재하지 않는다**. `cross_model_verifier.py`는 이름과 달리 두 번째 모델을
호출하지 않는 결정론 리뷰어다 (docstring이 명시).

→ 법률 조언 도메인에서 이건 실질 리스크다. golden set 도입 시 AgentLoop의 `evaluate` 명령이
observations를 대신 만들어 준다 (`evaluator.js`).

### 3.7 🟡 P2 — 나머지

- `PYTHON_BIN` 기본값이 `"python"` (`server.ts:47`) — venv 배포에서 깨진다
- Dockerfile / 배포 스크립트 **없음**
- README stale: 존재하지 않는 `freshness_monitor.py`를 가리키고, 테스트 수를 63개로 적음 (실제 100+)
- `datetime.utcnow()` DeprecationWarning 153건
- 커버리지 측정 설정 없음 (`pytest-cov` 미도입)

---

## 4. 배포 전 필수 확인 (게이트가 잡지 못하는 것)

게이트는 CI에서 돌고, CI에는 `LAW_API_KEY`가 없다. 그래서 **"실제 법령 API에 붙는가"는
게이트의 책임이 아니라 배포 시점의 전제조건**이다.

```bash
# 프로덕션 배포 직전, 실제 키를 가진 환경에서:
jaramlaw doctor --deep
python scripts/run_agentloop_gate.py   # law_source.mode == "live" 여야 한다
```

`law_source.mode`가 `cache`/`seed`면 **최신 법령이 아니라 시드 법령으로 답하고 있다는 뜻**이다.
방출기는 이걸 `degradedModeRate`로 보고하되 에러 예산으로는 계산하지 않는다 —
키 없는 개발 머신에서 게이트가 늑대소년이 되면 아무도 안 보게 되기 때문이다.

---

## 5. 게이트를 blocking으로 전환하는 기준

지금은 **report-only**다. 이유는 baseline이 얇기 때문이다 — 회귀 baseline이 **런 4건**에서
동결됐고, 노이즈 많은 baseline으로 빌드를 막으면 그 게이트는 첫 번째 오탐에서 꺼진다.

`--fail-on-block`으로 전환하기 위한 조건:

1. **런 20건 이상** 축적 후 `--update-baseline` 재실행 (p95/p99 tail latency도 이때 활성화)
2. **§3.1 토큰 텔레메트리 해소** → `TRACE_INCOMPLETE` 소멸 (지금은 항상 warn이라 신호가 안 됨)
3. **§3.2 실단가 주입** → 비용/예산 패스 활성화
4. 그 후 `.github/workflows/agentloop-gate.yml`에서 `--fail-on-block` 부착

> ⚠️ **`--update-baseline`은 회귀 직후에 돌리지 말 것.** 지금 측정된 값이 "우리가 방어할
> 의향이 있는 값"일 때만 동결한다. 회귀가 난 뒤 재-baseline하는 것은 게이트를 조용히
> 무장해제하는 가장 흔한 방법이다.

---

## 6. 왜 문서가 아니라 배선인가

이 저장소의 README는 `| AgentLoop | freshness_monitor.py (MVP stub) |`라고 적고 있지만
**그 파일은 존재하지 않는다.** 프레임워크 채택을 산문으로 주장하고 코드로는 0줄인 상태였다.

그래서 이번 변경은 문서가 아니라 **실행되는 것**만 넣었다: 게이트는 실제로 돌고
(`status=review`, finding 2건), 계약은 테스트 15건으로 고정돼 있으며, CI가 그것을 매 PR에서 돌린다.
검증 방법은 README를 읽는 게 아니라 위 명령어를 치는 것이다.
