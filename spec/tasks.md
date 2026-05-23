# 자람법 TASKS — 구현 태스크 분해

| ID | 작업 | 의존 | 모듈/파일 | AC |
|---|---|---|---|---|
| T01 | 프로젝트 스캐폴드 + pyproject | — | 디렉토리 트리, pyproject.toml | — |
| T02 | SDD 문서 (constitution/spec/plan/tasks/traceability) | T01 | spec/*.md | — |
| T03 | workflow YAML 작성 | T02 | workflows/family-legal-jaramlaw.workflow.yaml | AC8 |
| T04 | Agent contracts (9개) + delegation board | T03 | agents/*.md, handoff/delegation-board.md | — |
| T05 | 법령 시드 데이터 (22+ 조문) | T01 | data/seed/laws/*.yaml | F4 |
| T06 | 정부지원 시드 (10+) + 시나리오 fixture (3) | T01 | data/seed/supports/*.yaml, data/seed/scenarios/*.yaml | F2, AC1 |
| T07 | 코어 모듈 — models + family_context + law_retrieval | T05, T06 | src/jaramlaw_agent/{models,family_context,law_retrieval}.py | F1, F4 |
| T08 | support_matching + rights_card + calendar_gen | T07 | src/jaramlaw_agent/{support_matching,rights_card,calendar_gen}.py | F2, F3, F6 |
| T09 | document_drafter (환불액 계산 + 5 템플릿) | T05, T08 | src/jaramlaw_agent/document_drafter.py | F4 |
| T10 | guard (PIIRedactor + SafetySignalDetector) + verifier + human_review | T07 | src/jaramlaw_agent/{guard,verifier,human_review}.py | 원칙 2, 3, 5 |
| T11 | orchestrator + workflow runner + audit | T03, T09, T10 | src/jaramlaw_agent/{orchestrator,workflow,audit}.py | AC8 |
| T12 | CLI + 3개 시나리오 예제 | T11 | src/jaramlaw_agent/cli.py, examples/scenario_{A,B,C}.py | AC1 |
| T13 | 테스트 (15+) | T07-T12 | tests/test_*.py | AC1-AC8 |
| T14 | docs (architecture + SKILLs integration + README) | T11 | docs/*.md, README.md | — |
| T15 | 통합 검증 — pytest + CLI 실행 + workflow validate | T13 | (실행만) | AC1-AC8 |

## 의존성 DAG

```
T01 ── T02 ── T03 ── T04
  │       │      │
  │       │      └── T11 ── T12
  │       │              │     │
  ├── T05 ─┴─ T07 ── T08 ─┘     │
  │               │             │
  └── T06 ────────┤             │
                  │             │
                  └─ T09 ────────┤
                                 │
                  T10 ───────────┤
                                 │
                                 T13 ── T14 ── T15
```

## 완료 기준

전체 15 태스크 모두 completed + AC1-AC8 검증 PASS.
