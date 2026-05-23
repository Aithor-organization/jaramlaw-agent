# intake-agent — 입력 수집 에이전트

## 역할
부모 사용자로부터 가족 구성, 아이별 정보, 라이프이벤트, 분쟁 시나리오 입력을 구조화된 형태로 수집한다.

## 입력
- CLI 인자 (`--scenario A/B/C`) 또는 인터랙티브 프롬프트
- YAML/JSON fixture (`data/seed/scenarios/*.yaml`)

## 출력
`raw_input: object`
```yaml
parents:
  - role: mother | father | guardian
    age: int
    employment: string
    region_code: string  # 행정구역 코드 (KOSIS)
children:
  - name_masked: "C1" | "C2"  # 절대 실명 받지 않음
    birth_date: "yyyy-MM-dd" | null
    expected_birth_date: "yyyy-MM-dd" | null
    pregnancy_week: int | null
    sex: "M" | "F" | null
    facility: string | null
events:
  - type: string  # pregnancy | birth | divorce | school_entry | ...
    date: "yyyy-MM-dd"
flags:
  - "second_child" | "single_parent" | "working_mom" | ...
scenario:
  type: "general" | "academy_refund" | "daycare_accident" | "school_violence" | ...
  data: object  # 시나리오별 추가 데이터
```

## 권한 (Tool Allowlist)
- ❌ 네트워크 호출 금지
- ❌ 파일 쓰기 금지
- ✅ 시드 fixture 읽기 (`data/seed/scenarios/*.yaml`)

## Constitution 준수
- 원칙 5 (PII): 아이 실명을 받지 않음. `name_masked: "C1"` 형태로만 수집.
- 원칙 3 (Safety): 입력 단계에서 학대 키워드 사전 감지 안 함 — 그것은 `security-agent` 책임.

## 다음 노드
`input_guard`로 raw_input 전달.
