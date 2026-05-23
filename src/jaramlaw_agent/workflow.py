"""workflow — YAML 파서 + validator.

AITHOR-Agent-Framework `policy_finance_agent.workflow.yaml` 패턴을 mirror하여
require_nodes + require_text 기반 검증.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class WorkflowValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedWorkflow:
    name: str
    purpose: str
    node_ids: tuple[str, ...]
    safety_tokens: tuple[str, ...]
    raw_text: str

    def require_nodes(self, required: tuple[str, ...]) -> None:
        missing = [n for n in required if n not in self.node_ids]
        if missing:
            raise WorkflowValidationError(
                f"missing workflow nodes: {', '.join(missing)}"
            )

    def require_text(self, required: tuple[str, ...]) -> None:
        missing = [t for t in required if t not in self.raw_text]
        if missing:
            raise WorkflowValidationError(
                f"missing workflow tokens: {', '.join(missing)}"
            )


def load_workflow(path: str | Path) -> ParsedWorkflow:
    p = Path(path)
    if not p.exists():
        raise WorkflowValidationError(f"workflow not found: {p}")
    text = p.read_text(encoding="utf-8")
    name = _match_scalar(text, "name") or p.stem
    purpose = _match_scalar(text, "purpose") or ""
    node_ids = tuple(re.findall(r"^\s*-\s+id:\s*([A-Za-z0-9_-]+)\s*$", text, re.MULTILINE))
    safety_match = re.search(r"^safety:\s*$([\s\S]+?)^[A-Za-z]+:", text, re.MULTILINE)
    safety_text = safety_match.group(1) if safety_match else ""
    safety_tokens = tuple(line.strip() for line in safety_text.splitlines() if line.strip())
    return ParsedWorkflow(
        name=name, purpose=purpose, node_ids=node_ids,
        safety_tokens=safety_tokens, raw_text=text,
    )


def _match_scalar(text: str, key: str) -> Optional[str]:
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


REQUIRED_NODES = (
    "intake",
    "input_guard",
    "family_context",
    "law_retrieval",
    "support_matching",
    "parallel_expert_board",
    "document_drafter",
    "verify_atomic_claims",
    "human_review_gate",
    "rights_card_gen",
    "calendar_gen",
    "safety_routing",
    "audit_log",
)

REQUIRED_TOKENS = (
    "AgentShield.RuntimeGuard",
    "pii_redaction_required: true",
    "citation_required: true",
    "external_side_effect_tools_allowed: []",
    "principle_1_non_counsel_boundary",
    "principle_2_citation_required",
    "principle_3_safety_first_routing",
    "principle_4_no_external_side_effects",
    "principle_5_pii_masking",
)


def validate_family_legal_workflow(path: str | Path) -> ParsedWorkflow:
    wf = load_workflow(path)
    wf.require_nodes(REQUIRED_NODES)
    wf.require_text(REQUIRED_TOKENS)
    return wf
