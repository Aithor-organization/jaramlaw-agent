# AI-research-SKILLs 통합 가이드

자람법은 `/home/cafe66/workspace/AI-research-SKILLs` 67+ 카테고리 중 10개 직접 활용. 각 스킬이 자람법의 어떤 코드/문서에 매핑되는지 명시.

## 활용 매트릭스

| AI-research-SKILLs | 자람법 모듈/문서 | 통합 방식 |
|---|---|---|
| **14-agents** | `orchestrator._board_opinions()`, `agents/*.md` | Multi-Agent Board 5 에이전트 패턴. Builder ≠ Verifier 격리 사상. |
| **15-rag** | `law_retrieval.py` | Hybrid BM25 + Tag matching + RRF (Reciprocal Rank Fusion). citation-required generation. |
| **07-safety-alignment** | `guard.py`, `spec/constitution.md` | Constitution 5원칙 (변호사법/citation/safety/no-side-effect/PII). SafetySignalDetector → 1577-1391 라우팅. |
| **11-evaluation** | `verifier.py`, `tests/test_scenarios.py`, `tests/test_constitution.py` | Atomic Claim verifier. e2e 시나리오 회귀. 5원칙 회귀 차단. |
| **17-observability** | `audit.py`, `audit_logs/*.json` | 구조화 audit log + audit_log_id. 입력/단계별 출력/citation/safety 라우팅 기록. |
| **24-spec-driven-planner** | `spec/constitution.md`, `spec/spec.md`, `spec/plan.md`, `spec/tasks.md`, `spec/traceability.md` | SDD 산출물 5문서 패턴. 본 프로젝트 자체가 spec-driven 사례. |
| **25-backend-architect** | `workflow.py`, `workflows/family-legal-jaramlaw.workflow.yaml`, `orchestrator.py` | 14노드 graph 아키텍처. AITHOR Agent Framework 패턴. |
| **28-agent-memory** | `models.FamilyProfile`, `data/seed/scenarios/*.yaml` | 가족 컨텍스트 영속화. 시나리오 fixture를 통한 deterministic replay. |
| **62-mcp-agent-protocols** | `law_retrieval.LawApiClient` | LAW.OS `law_mcp_server` 인터페이스 stub. 후속 MCP 통합 시 `LawApiClient.search_current_laws()`를 MCP tool 호출로 전환. |
| **68-claude-native-agent-systems** | `agents/*.md`, `handoff/delegation-board.md` | 에이전트 contract 패턴 + delegation board (RACI). frontmatter, tool allowlist, 권한 격리. |

## 통합 깊이

### 직접 채택 (코드/문서가 스킬 패턴 mirror)

- `14-agents` (Multi-Agent Board)
- `15-rag` (Hybrid retrieval)
- `24-spec-driven-planner` (SDD 5문서)
- `25-backend-architect` (워크플로우 아키텍처)
- `68-claude-native-agent-systems` (agent contract)

### 사상 흡수 (정책/원칙으로 반영)

- `07-safety-alignment` → Constitution 5원칙
- `11-evaluation` → Atomic Claim + 회귀 테스트
- `17-observability` → audit log 구조화

### 인터페이스 stub (후속 통합 예정)

- `28-agent-memory` (현재는 in-memory FamilyProfile, 후속 영속화)
- `62-mcp-agent-protocols` (현재는 seeded mode, 후속 LAW.OS MCP 통합)

## 후속 활용 가능 스킬 (MVP 후속)

| 스킬 | 활용 시점 |
|---|---|
| `04-mechanistic-interpretability` | 특정 권리카드/지원 매칭이 왜 발생했는지 설명 가능성 강화 |
| `08-distributed-training` | 베타 출시 후 사용자 fine-tuning 데이터 활용 |
| `12-inference-serving` | B2C 출시 시 vLLM 등 inference serving |
| `13-mlops` | 모델 운영 관측 |
| `16-prompt-engineering` | LLM 호출 단계 추가 시 프롬프트 최적화 |
| `18-multimodal` | F5 문서 업로드 분석 (OCR + Vision) |
| `26-investment-trading-systems` | 본 도메인 무관 (제외) |
| `27-ai-agent-sandbox` | E2B 통합으로 격리 실행 |
| `35-personal-ai-assistant` | 가족 단위 personal assistant 사상 |
| `36-self-evolving-learning-system` | 사용자 피드백 → 시드 데이터 보강 자동화 |

## 외부 저장소 read-only 참조

자람법은 AI-research-SKILLs를 **수정하지 않음**. 다음 명령으로 read-only 참조:

```bash
# 특정 카테고리 SKILL.md 확인
cat /home/cafe66/workspace/AI-research-SKILLs/14-agents/SKILL.md
cat /home/cafe66/workspace/AI-research-SKILLs/15-rag/SKILL.md

# 직접 ls
ls /home/cafe66/workspace/AI-research-SKILLs/68-claude-native-agent-systems/
```

소유권/수명주기 격리 — AI-research-SKILLs는 별도 저장소이며 자람법 후속 변경의 영향을 받지 않음.

## 출처

- AI-research-SKILLs 저장소: `Aithor-organization/AI-research-SKILLs` (GitHub)
- 본 프로젝트 통합 결정: 2026-05-24 (T07-T11 코어 모듈 구현 시점)
