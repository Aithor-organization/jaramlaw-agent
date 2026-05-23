import pytest

from jaramlaw_agent.workflow import (
    WorkflowValidationError,
    load_workflow,
    validate_family_legal_workflow,
)


def test_validate_workflow_yaml(workflow_path):
    wf = validate_family_legal_workflow(workflow_path)
    assert wf.name == "family-legal-jaramlaw"
    # 14 노드 검증
    expected_subset = {
        "intake", "input_guard", "family_context", "law_retrieval",
        "support_matching", "parallel_expert_board", "document_drafter",
        "verify_atomic_claims", "human_review_gate", "rights_card_gen",
        "calendar_gen", "safety_routing", "audit_log",
    }
    assert expected_subset.issubset(set(wf.node_ids))


def test_workflow_contains_safety_tokens(workflow_path):
    text = workflow_path.read_text(encoding="utf-8")
    # Constitution 원칙 요건
    assert "AgentShield.RuntimeGuard" in text
    assert "pii_redaction_required: true" in text
    assert "citation_required: true" in text
    assert "external_side_effect_tools_allowed: []" in text


def test_workflow_missing_file_raises(tmp_path):
    fake = tmp_path / "missing.yaml"
    with pytest.raises(WorkflowValidationError):
        load_workflow(fake)
