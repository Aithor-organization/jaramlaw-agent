import yaml

from jaramlaw_agent.agent_topology import summarize_team_topology
from jaramlaw_agent.budget_guard import BudgetGuard
from jaramlaw_agent.memory_rag import JaramLawMemoryRAG
from jaramlaw_agent.model_routing import plan_model_routing
from jaramlaw_agent.models import FamilyProfile, FinalReport, SafetyRouting
from jaramlaw_agent.orchestrator import run_workflow


def _raw_input():
    return {
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 34, "employment": "unknown", "region_code": "11440"}],
        "children": [{"name_masked": "C1", "birth_date": "2024-05-15"}],
        "scenario": {"type": "academy_refund", "query": "academy refund refusal", "data": {}},
    }


def test_model_routing_isolated_and_budgeted():
    plan = plan_model_routing(_raw_input(), SafetyRouting(triggered=False))
    assert plan["model_guard"]["status"] == "PASS"
    assert plan["criticality"] == "standard"
    assert any(item["role"] == "atomic_claim_verifier" for item in plan["assignments"])

    decision = BudgetGuard(per_run_limit_usd=1.0).authorize(plan)
    assert decision.allowed
    assert decision.estimated_cost_usd > 0


def test_team_topology_contract_loads():
    summary = summarize_team_topology()
    assert summary["status"] == "loaded"
    assert summary["agent_count"] >= 8
    assert "independent-validator" in summary["critical_roles"]


def test_run_workflow_attaches_operational_metadata():
    with open("data/seed/scenarios/B_academy_refund.yaml", "r", encoding="utf-8") as fp:
        fixture = yaml.safe_load(fp)
    raw = fixture["family_profile"]
    raw["scenario"] = fixture["scenario"]
    raw["reference_date"] = fixture["reference_date"]
    raw["persona"] = fixture["persona"]
    report = run_workflow(raw, scenario_id="ops-test", write_audit=False)

    assert report.model_routing["model_guard"]["status"] == "PASS"
    assert report.budget_guard["allowed"] is True
    assert report.memory_context["memory_version"] == "jaramlaw-memory/v1"
    assert report.independent_validation["status"] in {"PASS", "WARN"}
    assert report.trace_summary["events"] >= 10
    assert report.verifier_results.retry_summary["attempts_used"] >= 1
    assert report.board_opinions["contrarian_verifier"]["verdict"] in {"PASS", "NEEDS_WORK", "BLOCK"}


def test_memory_capture_is_metadata_only(tmp_path):
    memory = JaramLawMemoryRAG(memory_path=tmp_path / "memory.jsonl")
    report = FinalReport(
        family_profile=FamilyProfile(life_stages=["toddler"], flags=["dual_income"]),
        scenario_id="memory-test",
        workflow_version="test/v1",
    )

    capture = memory.capture_outcome(report)
    recall = memory.recall({"scenario": {"type": "general", "query": "dual_income toddler support"}})

    assert capture["captured"] is True
    assert recall["record_count"] == 1
    assert recall["matches"][0]["record"]["readonly"] is True
    assert "raw_input" not in recall["matches"][0]["record"]
