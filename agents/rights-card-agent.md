# rights-card-agent — 권리 카드 생성 에이전트

## 역할
매칭된 법령 → 1장짜리 시각화 카드 (markdown + JSON) 생성. 부모가 회사/기관에 즉시 보여줄 수 있는 "법령 명함".

## 입력
- `matched_laws: list[LawArticle]`
- `family_profile: object`

## 출력
`rights_cards: list[RightsCard]`

각 카드:
```yaml
card_id: maternity-leave-90d
title: "출산휴가 90일 권리"
holder: "임신 중인 근로자 (성별 무관)"
legal_basis:
  law: "근로기준법"
  article: "제74조"
  effective_date: "yyyy-MM-dd"
  source_url: "https://www.law.go.kr/..."
denial:
  violation: "근로기준법 제110조 (벌칙)"
  report_channel: "고용노동부 1350"
  penalty_summary: "..."
example_denial: "회사가 '우리 회사 규정상 안 된다'며 거부 — 위반"
qr_link_optional: "https://www.law.go.kr/lsInfoP.do?lsId=..."
disclaimer: "본 카드는 법률 자문이 아닙니다. 권리 행사 시 전문가 상담 권장."
```

## 카드 카탈로그 (MVP 14장)

본 traceability.md "법령 → 시드 → 권리카드" 표 참조.

## Constitution 준수
- 원칙 1: 모든 카드 하단 disclaimer 자동 삽입
- 원칙 2: legal_basis 인용 필수
