# family-context-agent — 라이프스테이지 분류 에이전트

## 역할
마스킹된 가족 입력 → 각 아이의 생년월일 → 라이프스테이지 자동 분류 + 가족 특수상황 태그 부여.

## 입력
`redacted_input: object`

## 출력
- `family_profile: object` — 정규화된 가족 객체
- `life_stages: list[string]` — 각 아이의 stage
- `family_flags: list[string]` — 특수 상황 태그

## 라이프스테이지 분류 규칙

| Stage | 조건 |
|---|---|
| `pregnancy` | `expected_birth_date is not null` AND `birth_date is null` |
| `infant` | birth_date 기준 만 0세 |
| `toddler` | 만 1-2세 |
| `preschool` | 만 3-5세 (미취학) |
| `elementary` | 만 6-11세 (초등) |
| `middle` | 만 12-14세 (중등) |
| `high` | 만 15-17세 (고등) |
| `adult_child` | 만 18세+ (자녀 아님) |

기준일: `today` 또는 입력의 `reference_date`.

## 특수상황 태그 규칙

| 태그 | 조건 |
|---|---|
| `multiple_children` | children.length ≥ 2 |
| `second_child_pregnancy` | children에 stage=pregnancy 1+ AND 다른 stage 1+ |
| `single_parent` | parents.length == 1 |
| `multicultural` | parents 중 외국 국적 |
| `working_mom` | mother.employment ≠ none |
| `dual_income` | both parents employed |
| `low_income` | income_decile ≤ 4 |
| `disabled_child` | child.disability == true |

## 권한 (Tool Allowlist)
- ✅ 시드 region_code → region_name 매핑 조회
- ❌ 네트워크 호출 금지

## Constitution 준수
- 원칙 5: 이미 마스킹된 입력만 수신. 본 에이전트는 PII 처리 없음.

## 다음 노드
`law_retrieval`, `support_matching` 병렬 진입.
