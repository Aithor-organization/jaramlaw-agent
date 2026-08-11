# 검증 운영 매뉴얼 (Phase 0 산출물 사용법)

> `docs/validation-plan.md`가 "무엇을 할 것인가"라면, 이 문서는 **"매주 무슨 명령을 치는가"**다.
> 전제: 운영자 토큰(`JARAMLAW_API_TOKEN`)이 Railway에 설정돼 있다 (2026-08-12 확인 — 무토큰 접근 401).

```bash
export JL=https://jaramlaw-agent-production.up.railway.app
export JL_TOKEN="<Railway 환경변수 JARAMLAW_API_TOKEN 값>"
```

---

## 🔴 시작 전 딱 한 번 — 볼륨 확인

**이걸 안 하면 나머지가 다 무의미하다.** Dockerfile은 `/app/data`에 쓰는데, Railway에 볼륨이
안 붙어 있으면 재배포마다 계정·상담·퍼널이 **전부 초기화**된다.

1. Railway 대시보드 → 서비스 → **Volumes**
2. `/app/data` 마운트가 있는지 확인
3. 없으면 → Volume 추가, Mount path `/app/data`, 재배포

확인 방법 (가입자가 생긴 뒤):
```bash
curl -s $JL/api/health | grep -o '"history_count":[0-9]*'
# 재배포 후 이 숫자가 0으로 떨어지면 볼륨이 없는 것이다
```

---

## 매주 월요일 — 30분 루틴

### 1. 백업 (2분) — 제일 먼저

```bash
curl -s -H "x-jaramlaw-token: $JL_TOKEN" $JL/api/ops/export \
  > ~/jaramlaw-backups/backup-$(date +%F).json
```

계정·퍼널·피드백이 한 파일로 떨어진다. **Railway CLI 없이 되는 유일한 백업 경로**다.
받은 파일은 `du -h`로 크기만 확인하고(0바이트면 토큰 오류) 지우지 말 것 — 주차별로 남긴다.

### 2. 퍼널 확인 (3분)

```bash
cd jaramlaw-agent/jaramlaw-agent-ui
npm run funnel -- --file ~/jaramlaw-backups/backup-$(date +%F).json
```

```
  첫 화면    20명  100%  ████████████████████
  진단 시작  12명   60%  ████████████  직전 대비 60%
  진단 완주   7명   35%  ███████       직전 대비 58%
  가입        4명   20%  ████          직전 대비 57%
  첫 질문     2명   10%  ██            직전 대비 50%
  재방문      1명    5%  █             직전 대비 50%

  ⚠ 가장 큰 이탈: 첫 화면 → 진단 시작 (8명)
```

**보는 법**: 맨 아래 ⚠ 한 줄만 봐도 된다. 그게 이번 주에 고칠 곳이다.

| 어디서 새는가 | 뜻 | 손댈 곳 |
|---|---|---|
| 첫 화면 → 진단 시작 | 첫 화면이 설득을 못 한다 | 히어로 문구·CTA |
| 진단 시작 → 완주 | 5문항이 길거나 막힌다 | 질문 순서·문구 |
| 완주 → 가입 | 가입 요구가 과하다 | 가입 전 보여주는 양 |
| 가입 → 첫 질문 | 뭘 해야 할지 모른다 | 홈 화면 첫 유도 |
| 첫 질문 → 재방문 | **답이 쓸모없었다** 🔴 | 제품 본질 문제 |

마지막 줄이 무너지면 문구가 아니라 **가설**을 의심할 것.

### 3. 피드백 읽기 (5분)

백업 파일의 `data.feedback` 배열. 또는:
```bash
python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
for f in d['data']['feedback'][-20:]:
    print(f\"[{f['ts'][:10]}] ({f['route']}) {f['text']}\")
    if f.get('contact'): print(f'    ↳ 답장: {f[\"contact\"]}')
" ~/jaramlaw-backups/backup-$(date +%F).json
```

**연락처를 남긴 사람에게는 24시간 안에 답장한다.** 30명 규모에선 가능하고, 이게 리텐션을 만든다.

### 4. 컨시어지 알림 발송 (15분) — 이번 검증의 핵심

```bash
curl -s -H "x-jaramlaw-token: $JL_TOKEN" "$JL/api/ops/reminders?within=14" \
  | python3 -m json.tool
```

```json
{ "status": "success", "within_days": 14, "checked": 32,
  "data": [
    { "nickname": "지원", "email": "...", "region": "서울",
      "due": [ { "name": "첫만남이용권", "amount_krw": 2000000,
                 "application_channel": "정부24 / 주민센터", "days_left": 9 } ] } ] }
```

이 목록을 보고 **직접 카톡/문자를 보낸다.** 자동 발송은 만들지 않는다 —
반응이 없으면 발송 시스템 자체가 필요 없기 때문이다 (`validation-plan.md` Phase 0-3).

#### 문구 템플릿 3종

**① 기한 임박 (가장 자주 씀)**
```
○○님, 자람법입니다.
첫만남이용권 신청 기한이 9일 남았습니다. 200만 원이고, 놓치면 소급이 안 됩니다.
신청은 정부24나 주민센터에서 하시면 됩니다.
자세한 내용은 여기 → https://jaramlaw-agent-production.up.railway.app
```

**② 새 지원 매칭**
```
○○님, 아이 나이 기준으로 새로 받으실 수 있는 지원이 생겨서 알려드립니다.
[지원명] — 신청 기한 [D-day]
앱에 들어가시면 근거 조문이랑 신청처까지 정리돼 있습니다.
```

**③ 기한 지남 (놓친 뒤라도 알린다)**
```
○○님, [지원명] 기한이 지났습니다. 다음에는 미리 알려드리겠습니다.
혹시 이미 신청하셨으면 알려주세요 — 잘못 안내한 거면 고쳐두겠습니다.
```

🔴 **템플릿 그대로 붙여넣지 말 것.** 이름과 상황을 넣고, 말투는 형님 말투로 바꾼다.
받는 사람이 "자동 발송"이라고 느끼는 순간 이 실험의 의미가 사라진다.

#### 발송하면 기록할 것 (스프레드시트 한 장이면 충분)

| 날짜 | 이름 | 보낸 지원 | D-day | 클릭? | 신청함? |
|---|---|---|---|---|---|

**"신청함?" 칸이 이번 검증의 북극성**이다. 4주 뒤 이 칸의 합계가 판정 근거가 된다.

---

## 4주차 — 추적 연락

설문 폼 만들지 말 것. 카톡 한 줄로:

> "지난번에 알려드린 거 있잖아요, **실제로 신청하셨어요?**"

안 했다면 이유를 하나만 더 묻는다 — **잊어서 / 못 믿어서 / 귀찮아서 / 해당 없어서.**
처방이 각각 다르다 (`validation-plan.md` Phase 3 표 참조).

---

## 문제가 생기면

| 증상 | 확인 |
|---|---|
| 백업이 0바이트 | 토큰 오류 → `curl -s -o /dev/null -w "%{http_code}\n" -H "x-jaramlaw-token: $JL_TOKEN" $JL/api/operator/status` (200이어야 정상, 401이면 토큰 불일치) |
| `npm run funnel`이 "기록 없음" | 백업 파일 경로 확인, 또는 `--file` 없이 로컬 데이터 조회 중일 수 있음 |
| reminders가 503 | 파이썬 브리지 중단 → `curl -s $JL/api/health \| grep python_bridge` |
| reminders에 `failed` 배열 | 그 사용자만 워크플로우 실패 — 나머지 발송은 정상 진행하고 원인은 나중에 |
| 재배포 후 가입자 0 | 🔴 **볼륨 미설정** — 맨 위 절차로 |

---

## 이번에 만든 것 (Phase 0 산출물)

| 항목 | 위치 |
|---|---|
| 개인정보 처리방침 · 이용약관 | `/#privacy` · `/#terms` (푸터 링크) |
| 가입 동의 (필수) | 가입 화면 체크박스 + 서버 검증 |
| 퍼널 6단계 기록 | `POST /api/events` → `{DATA}/funnel/events-YYYY-MM.jsonl` |
| 퍼널 리포트 | `npm run funnel` |
| 부모 피드백 | 화면 우하단 버튼 → `{DATA}/feedback.jsonl` |
| 백업 | `GET /api/ops/export` (운영자 토큰) |
| 알림 대상 추출 | `GET /api/ops/reminders?within=14` (운영자 토큰) |

**Google Analytics는 쓰지 않는다.** 이유는 `src/server/telemetry.ts` 헤더 주석에 적어뒀다 —
요약하면 ① 광고차단으로 유실 ② 쿠키 동의 배너가 필요해짐 ③ "외부 전송 최소화"라는
이 서비스의 설계 원칙과 정면 충돌.
