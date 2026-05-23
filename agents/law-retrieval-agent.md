# law-retrieval-agent — 법령 조문 매칭 에이전트

## 역할
가족 프로필 + 시나리오 키워드 → 적용 가능한 법령 조문 hybrid retrieval. LAW.OS LawApiClient 또는 시드 모드.

## 입력
- `family_profile: object`
- `life_stages: list`
- `redacted_input.scenario: object` (시나리오 키워드)

## 출력
`matched_laws: list[LawArticle]` — 각 항목에 `relevance_score`, `applies_reason` 포함

## 매칭 로직 (Hybrid)

### 1. Tag matching (정확)
- `family_flags` ∩ `LawArticle.applies_to_personas` 교집합
- `life_stages` ∩ `LawArticle.tags` 교집합

### 2. BM25 score (시나리오 키워드)
- 시나리오 텍스트 vs `LawArticle.text_summary`
- 시드 시 단순 IDF-weighted 토큰 매칭으로 대체

### 3. RRF (Reciprocal Rank Fusion)
- tag rank + BM25 rank 조합
- 최종 top-K (기본 K=10) 반환

### 4. LawApiClient (옵션)
- 환경변수 `LAW_API_KEY` 설정 시 law.go.kr 실시간 조회로 보강
- 미설정 시 시드 데이터만 사용 (seeded mode)

## 권한 (Tool Allowlist)
- ✅ `search_current_laws(query, filters)`
- ✅ `get_current_law_article(law_id, article_no)`
- ❌ 네트워크 쓰기 금지

## Constitution 준수
- 원칙 2: 매칭된 각 조문은 시드 YAML의 source_url + effective_date를 반드시 포함하여 반환. 미완성 항목은 반환 X.

## 다음 노드
`parallel_expert_board` → `document_drafter` → `verify_atomic_claims`
