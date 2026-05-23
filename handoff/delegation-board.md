# 자람법 Delegation Board — 위임 흐름

> 9개 에이전트 간 위임 경로 + 책임 매트릭스 (RACI). 모든 위임은 workflow YAML의 edges를 따른다.

## 위임 흐름도

```
사용자 입력
  ↓
[intake-agent] ──→ raw_input
  ↓
[security-agent] ──→ redacted_input + safety_routing
  ↓ (safety_triggered ? → human-review-gate 직행 : 계속)
[family-context-agent] ──→ family_profile + life_stages + family_flags
  ↓
  ├──→ [law-retrieval-agent] ──→ matched_laws
  └──→ [support-matching-agent] ──→ support_matches
  ↓
[parallel_expert_board: 5 에이전트 병렬 검토]
  ├ law-retrieval-agent
  ├ family-context-agent
  ├ support-matching-agent
  ├ document-drafter-agent (안)
  └ contrarian-verifier (반증)
  ↓ board_opinions
[document-drafter-agent] ──→ draft_documents
  ↓
[atomic-claim-verifier] ──→ atomic_claims + verifier_results
  ↓
[human-review-gate] ──→ human_review_needed
  ↓
[rights-card-agent + calendar-agent + freshness-monitor 병렬]
  ↓
[audit-log] ──→ final_report + audit_log_id
```

## RACI 매트릭스

| 작업 | R (Responsible) | A (Accountable) | C (Consulted) | I (Informed) |
|---|---|---|---|---|
| 입력 수집 | intake | intake | — | — |
| PII 마스킹 | security | security | — | intake |
| Safety 라우팅 | security | human-review-gate | family-context | all |
| 라이프스테이지 분류 | family-context | family-context | — | law-retrieval, support-matching |
| 법령 매칭 | law-retrieval | law-retrieval | family-context | parallel_expert_board |
| 지원 매칭 | support-matching | support-matching | family-context | parallel_expert_board |
| 신청서 초안 | document-drafter | document-drafter | law-retrieval, contrarian-verifier | atomic-claim-verifier |
| Citation 검증 | atomic-claim-verifier | atomic-claim-verifier | law-retrieval | human-review-gate |
| 권리카드 생성 | rights-card-agent | rights-card-agent | law-retrieval | audit-log |
| 캘린더 생성 | calendar-agent | calendar-agent | family-context | audit-log |
| 고위험 라우팅 | human-review-gate | human-review-gate | atomic-claim-verifier, security | all |
| Audit log | lifecycle-operator | lifecycle-operator | all | — |

## 권한 격리

| 에이전트 | 읽기 | 쓰기 | 외부 |
|---|---|---|---|
| intake | scenarios/ | — | — |
| security | (입력만) | — | — |
| family-context | regions/ | — | — |
| law-retrieval | laws/, [api] | — | law.go.kr (옵션) |
| support-matching | supports/ | — | — |
| document-drafter | templates/, laws/ | — | — |
| contrarian-verifier | laws/, board_opinions | — | — |
| atomic-claim-verifier | laws/, all_claims | — | — |
| human-review-gate | expert_contacts/ | — | — |
| lifecycle-operator | all | audit_logs/ | — |

Constitution 원칙 4 (외부 발송 금지)에 따라 어떤 에이전트도 외부 시스템에 쓰기 권한 없음.

## 에스컬레이션 프로토콜

각 에이전트가 다음 상황 발생 시 `## ESCALATION` 블록으로 메인 오케스트레이터에 반환:

| 사유 | 라우팅 |
|---|---|
| 시드 데이터에 매칭 없음 (curated gap) | freshness_monitor 후속 |
| 인용 확보 실패 (citation_gap) | human-review-gate |
| Contrarian이 critical 발견 | parallel_expert_board 재검토 |
| safety 신호 (인식 누락) | security-agent로 역방향 |

`escalation-return-protocol.md` (SEAS 본 저장소 참조) 패턴을 그대로 따른다.

## 책임 분리 (Builder ≠ Verifier)

- **Builder**: document-drafter-agent, rights-card-agent, calendar-agent, support-matching-agent
- **Verifier**: atomic-claim-verifier, contrarian-verifier, human-review-gate

이 격리가 Constitution 원칙 2 (Citation) + 원칙 1 (Non-Counsel) 강제의 본질.
