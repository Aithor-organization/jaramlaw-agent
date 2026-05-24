# Operational Agent Architecture

JaramLaw now has an explicit operational layer on top of the original
deterministic 14-node workflow. The goal is to match the formal structure of a
production AI-agent system without introducing external model calls.

## Runtime Flow

```text
input_guard
  -> model_routing
  -> budget_guard
  -> memory_recall
  -> family_context
  -> retrieval / matching / drafting
  -> board review
  -> verifier retry loop
  -> human review gate
  -> independent validation
  -> memory capture
  -> audit log
  -> trace export
```

## Added Contracts

- `agents/team.yaml`: central topology for manager, workers, gates, verifier, memory, budget, and observability roles.
- `workflows/jaramlaw-model-routing.workflow.yaml`: deterministic tier assignment, role isolation, and budget estimation.
- `workflows/jaramlaw-brain.workflow.yaml`: metadata-only memory recall/capture workflow.
- `src/jaramlaw_agent/model_routing.py`: criticality classification and writer/verifier/validator isolation.
- `src/jaramlaw_agent/budget_guard.py`: per-run and monthly budget guard metadata.
- `src/jaramlaw_agent/memory_rag.py`: local `.jaramlaw-brain/memory.jsonl` metadata memory.
- `src/jaramlaw_agent/observability.py`: metadata trace export to `audit_logs/trace.jsonl`.
- `src/jaramlaw_agent/cross_model_verifier.py`: independent final-report validation gate.
- `src/jaramlaw_agent/mcp_server.py`: MCP-style tool registry for review, memory search, and audit log access.

## Safety Boundaries

- External model calls remain disabled.
- Memory stores workflow metadata only; it is not legal authority.
- Raw user text is not captured in memory records.
- Writer, verifier, and independent validator roles are separated by isolation group.
- Human review remains mandatory for safety-triggered or high-risk outcomes.

## UI/Ops Surface

The React UI exposes an Ops tab and server APIs:

- `GET /api/ops/workflow/status`
- `GET /api/ops/audit/logs`
- `GET /api/ops/traces`
- `POST /api/ops/workflow/publish`
- `POST /api/ops/batch-consult`

`POST /api/ops/workflow/publish` writes a local manifest to
`runs/workflow-publish.json`; it does not publish to an external service.
