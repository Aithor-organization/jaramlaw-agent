# 자람법 Agent Contracts

자람법 Multi-Agent Board를 구성하는 9개 에이전트 contract.

| Agent | 역할 | Workflow Node | 권한 |
|---|---|---|---|
| [intake-agent](intake-agent.md) | 부모 입력 수집 | intake | read-only |
| [security-agent](security-agent.md) | PII 마스킹 + safety 라우팅 | input_guard, safety_routing | redact-only |
| [family-context-agent](family-context-agent.md) | 라이프스테이지 분류 | family_context | read-only |
| [law-retrieval-agent](law-retrieval-agent.md) | 법령 조문 매칭 | law_retrieval | search-only |
| [support-matching-agent](support-matching-agent.md) | 정부지원 자격 매칭 | support_matching | search-only |
| [document-drafter-agent](document-drafter-agent.md) | 신청서·신고서 초안 | document_drafter | draft-only (no submit) |
| [contrarian-verifier](contrarian-verifier.md) | 반증·예외 검증 | parallel_expert_board | review-only |
| [atomic-claim-verifier](atomic-claim-verifier.md) | citation 검증 | verify_atomic_claims | review-only |
| [human-review-gate](human-review-gate.md) | 고위험 라우팅 | human_review_gate | route-only |

모든 agent는 Constitution 5원칙을 강제 따른다.
Workflow YAML이 모든 agent의 tool allowlist를 통제 — agent는 정의된 tool 외 호출 불가.

## 위임 보드

상세: [`../handoff/delegation-board.md`](../handoff/delegation-board.md)
