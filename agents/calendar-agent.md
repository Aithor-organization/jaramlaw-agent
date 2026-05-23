# calendar-agent — 라이프스테이지 캘린더 에이전트

## 역할
아이 생년월일 → 영유아 건강검진 + 예방접종 + 학교 입학 + 지원금 전환 시점 자동 캘린더 생성. iCal/JSON 출력.

## 입력
- `family_profile.children: list`
- `today: date`

## 출력
`calendar: object`
```yaml
events:
  - kind: "health_checkup"
    title: "영유아 건강검진 (4~6개월)"
    legal_basis: {law: "모자보건법", article: "..."}
    target_age_months: 5
    scheduled_date: "yyyy-MM-dd"
    notes: "..."
  - kind: "vaccination"
    title: "BCG 예방접종"
    legal_basis: {law: "감염병예방법", article: "제24조"}
    ...
  - kind: "school_entry"
    title: "초등학교 입학"
    target_age_years: 6
    ...
  - kind: "support_transition"
    title: "부모급여 만 1세 전환 (100만원 → 50만원)"
    ...
ical_export: "BEGIN:VCALENDAR\n..." (iCal RFC 5545 형식)
```

## 알고리즘

1. 각 child별 생년월일 → 만 나이 (개월)
2. 시드 `data/seed/calendar/`의 표준 일정 (예방접종 표 / 영유아 건강검진 표 / 학사일정) 매핑
3. 부모급여 전환: 만 1세 / 만 2세 / 만 8세 (아동수당 종료)
4. iCal 직렬화

## Constitution 준수
- 원칙 2: 각 이벤트에 legal_basis 인용
