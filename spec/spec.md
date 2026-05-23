# 자람법 SPEC — 시스템 명세서

> 출처: `자람법_제안서_v2.md` (2026-05-22). 본 SPEC은 제안서 §2~§9를 구현 가능한 명세로 변환한다.

## 1. 시스템 개요

**자람법(JaramLaw)** = 부모가 입력한 아이의 생년월일·지역·가족 구성·라이프이벤트를 기준으로 적용 법령·정부지원·권리·의무를 자동 매칭하고, 받은 문서를 분석해 대응 가이드를 생성하는 가족 라이프스테이지 법령 AI 동반자.

**기반**: AITHOR-Agent-Framework Kernel + LAW.OS RAG 패턴 (citation-required)
**도메인팩**: `family-legal`

## 2. 페르소나 (3개)

### P1. 김지원 (32세, 워킹맘, 서울 마포)
- 가족: 본인, 남편, 24개월 아들, 임신 12주 (둘째)
- 핵심 페인: 둘째 출산휴가/육아휴직 권리, 어린이집 사고 대응, 부모급여 변경 추적

### P2. 박민수 (38세, 아빠, 경기 화성)
- 가족: 본인, 아내, 초1 딸, 4세 아들
- 핵심 페인: 학원 환불 거부, 학교폭력 의심, 보육료 변경

### P3. 최영희 (45세, 한부모, 지방)
- 가족: 본인, 중1 아들
- 핵심 페인: 한부모 지원 누락, 양육비 미지급, 사이버불링

## 3. 핵심 기능 (F1-F8)

### F1. 가족 프로필 매니저
- **입력**: 부모 직업·고용형태, 가족 구성, 아이별 생년월일·지역·다니는 시설·소득구간
- **출력**: `FamilyProfile` 객체 + 라이프스테이지 자동 분류 (임신/영아/유아/미취학/초등/중등/고등) + 특수 상황 태그 (다자녀·한부모·다문화·맞벌이·장애아동)
- **모듈**: `family_context.py`

### F2. 지원 매칭 엔진
- **입력**: `FamilyProfile`
- **출력**: `SupportMatch[]` — 지원금명, 근거 법령 조문, 신청기한 D-day, 신청 채널, 예상 금액
- **누락 위험 알림**: 오늘 기준 D-N 임박 항목 강조
- **모듈**: `support_matching.py`

### F3. 우리아이 법령 캘린더
- **입력**: 아이 생년월일
- **출력**: iCal 형식 일정 — 영유아 건강검진, 예방접종, 학교 입학 D-day, 부모급여 전환 시점
- **모듈**: `calendar_gen.py`

### F4. 분쟁 자가진단 + 신고 워크플로우
- **시나리오 카테고리**: 학원환불 / 학교폭력 / 어린이집 사고 / 보육교사 갈등 / 양육비 분쟁 / 면접교섭 분쟁 / 사이버폭력 / 아동학대 의심 / 미성년자 SNS 사고
- **출력**: 관련 법령 조문 + 신고경로 비교 (1차/2차/3차) + 신고서 초안
- **Multi-Agent Board**: Law Retrieval / Family Context / Document Drafter / Contrarian Verifier
- **모듈**: `orchestrator.py` + `document_drafter.py`

### F5. 문서 업로드 분석 (멀티모달)
- **MVP 범위**: stub 처리. 후속 단계에서 OCR + Vision 통합.
- **현재 동작**: 텍스트로 변환된 문서 내용 입력 → 법령 매칭 + 의무·권리 카드 + 대응 옵션

### F6. 권리 카드 (Rights Card)
- **출력**: 1장짜리 시각화 카드 (Markdown + JSON, PDF는 stub)
- **항목**: 권리명, 근거 조문, 시행일, 위반 시 신고처, 거부 사례 예시
- **모듈**: `rights_card.py`

### F7. 법령 변화 영향 푸시 (AgentLoop)
- **MVP**: 시드 데이터 변경 감지 → 영향 가구 식별 로직만 구현 (실제 푸시 X)
- **모듈**: `freshness_monitor.py` (stub)

### F8. 똑똑맘 콘텐츠 연계
- **MVP**: 키워드 → 채널 콘텐츠 URL 매핑 stub
- **모듈**: `content_link.py` (stub)

## 4. 데모 시나리오 (3개 — D-7 MVP 범위)

### 시나리오 A: 둘째 임신 + 첫째 4세, 워킹맘, 서울
- **입력**: FamilyProfile (P1 김지원)
- **기대 출력**: 지원 매칭 7건 + 권리 카드 5장 + 캘린더 (D-30~D+180) + 체크리스트 PDF stub

### 시나리오 B: 초1 딸 학원 환불 거부, 화성
- **입력**: 학원명, 결제일, 금액, 사용기간, 학원 답변
- **기대 출력**: 학원법 시행령 별표4 환불액 자동 계산 + 대응 옵션 4단계 + 환불 요청서 초안

### 시나리오 C: 어린이집 24개월 아들 사고
- **입력**: 알림장 내용 (텍스트), 부모 관찰
- **기대 출력**: 법령 진단 (영유아보육법 33조의3 + 15조의5) + 부모 권리 카드 4장 + 체크리스트 + 학대 의심 라우팅 안내 (1577-1391)

## 5. 안전성·법률 리스크 (Constitution 5원칙 매핑)

| 리스크 | 대응 | Constitution |
|---|---|---|
| 변호사법 위반 | "법률 자문 아님" 고지 문구 자동 삽입, 구체 사건 자문 거부 | 원칙 1 |
| 무근거 답변 | 모든 claim에 조문/시행일 인용 강제 | 원칙 2 |
| 학대 의심 신호 | 1577-1391 라우팅 | 원칙 3 |
| 자동 신고 발사 | external_side_effect_tools_allowed: [] | 원칙 4 |
| 아동 PII 누설 | PIIRedactor 자동 마스킹 | 원칙 5 |

## 6. 입출력 데이터 모델

### FamilyProfile
```yaml
parents:
  - role: mother
    age: 32
    employment: "정규직 (대기업)"
    region_code: "11440"  # 서울 마포구
  - role: father
    age: 34
    employment: "정규직 (중소기업)"
children:
  - name_masked: "C1"
    birth_date: "2024-05-01"
    sex: "M"
    facility: "어린이집"
  - name_masked: "C2"
    expected_birth_date: "2026-12-15"
    pregnancy_week: 14
events:
  - type: "pregnancy"
    date: "2026-09-15"
flags:
  - "second_child"
  - "working_mom"
```

### SupportMatch
```yaml
support_id: "first-meeting-voucher"
name: "첫만남이용권"
amount_krw: 2000000
condition_summary: "출생아 1인당 1회"
legal_basis:
  law: "저출산고령사회기본법"
  article: "시행령 (해당 조문 명시)"
  effective_date: "..."
application_channel: "정부24"
deadline_days_left: 60
matched_at: "2026-05-24T..."
```

### RightsCard
```yaml
card_id: "maternity-leave-90d"
title: "출산휴가 90일 권리"
holder: "임신 중인 근로자"
legal_basis:
  law: "근로기준법"
  article: "제74조"
  effective_date: "..."
denial_violation:
  penalty: "..."
  report_channel: "고용노동부 1350"
example_denial: "회사 규모/규정을 이유로 거부 — 위반"
```

### LawArticle (시드 yaml)
```yaml
law_id: "labor-standards-74"
law_name: "근로기준법"
article: "제74조"
title: "임산부의 보호"
effective_date: "..."
text_summary: "..."
applies_to_personas: ["P1", "P2-mother", "P3"]
tags: ["maternity", "pregnancy", "work-leave"]
source_url: "https://www.law.go.kr/..."
```

## 7. 시스템 경계 (out-of-scope)

- 실제 신고/제출 자동화 (Constitution 원칙 4)
- 구체 사건 승소 예측 (Constitution 원칙 1)
- 의학적 진단 (Constitution 원칙 3)
- 실시간 OCR/Vision 멀티모달 (F5 — MVP 후속)
- 실제 push notification 전송 (F7 — MVP 후속)

## 8. 성공 기준 (Acceptance Criteria)

- AC1: 시나리오 A/B/C 각각 deterministic 동작 (seeded mode, 동일 입력 → 동일 출력)
- AC2: 모든 출력에 Constitution 원칙 1 고지 문구 포함
- AC3: 모든 법령 claim에 조문/시행일/출처 인용 (verifier 통과)
- AC4: PII 입력 (예: 아이 실명) → 처리 전 마스킹 확인
- AC5: 학대 의심 키워드 입력 → safety 라우팅 발동
- AC6: 시나리오 B 환불액이 학원법 시행령 별표4 기준으로 ±1원 이내 정확
- AC7: pytest 15+ unit 테스트 PASS
- AC8: workflow YAML이 AITHOR validator 패턴 (`require_nodes`, `require_text`) 통과
