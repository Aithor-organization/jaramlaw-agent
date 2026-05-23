# support-matching-agent — 정부지원 매칭 에이전트

## 역할
가족 프로필 → 받을 자격 있는 정부지원 자동 매칭 + 신청기한 D-day 계산.

## 입력
- `family_profile: object`
- `life_stages: list`
- `family_flags: list`

## 출력
`support_matches: list[SupportMatch]`

각 SupportMatch:
- `support_id`, `name`, `amount_krw`, `condition_summary`
- `legal_basis: {law, article, effective_date}`
- `application_channel` (정부24 / 거주지 행정복지센터 / 고용보험 / etc.)
- `deadline_days_left`
- `eligibility_evidence: list` — 매칭 사유

## 매칭 로직

1. 시드 `data/seed/supports/*.yaml` 전수 로드
2. 각 지원의 `eligibility_rules` 평가 (DSL → boolean)
   - `child_age_months_between: [0, 96]` → children 중 만 0-8세 존재 여부
   - `is_pregnant: true` → events에 pregnancy 존재
   - `single_parent: true` → flags에 single_parent
   - `region_code_in: ["11440", ...]` → 지역 매칭
3. 매칭된 지원 → D-day 계산
   - 출산 예정일 기준 (60일 이내), 만 나이 전환 기준, 입학 기준 등
4. 결과 정렬: 임박순 (deadline_days_left ASC)

## 권한 (Tool Allowlist)
- ✅ `search_supports(filters)` — 시드 YAML 조회
- ❌ 네트워크 호출 금지 (MVP — 미래 정부24 API 통합 후속)

## Constitution 준수
- 원칙 2: 각 지원에 legal_basis 인용 필수
- 원칙 4: 자동 신청 발사 X — 신청 채널 안내만

## 다음 노드
`parallel_expert_board` (board_opinions에 합류)
