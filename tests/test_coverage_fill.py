"""나머지 갭 커버 — human_review / mcp_server / openrouter_client / budget_guard."""

from __future__ import annotations

import pytest

from jaramlaw_agent.human_review import determine_human_review, EXPERT_CONTACTS
from jaramlaw_agent.models import SafetyRouting, VerifierResults


# === human_review: safety 카테고리별 전문가 라우팅 ===


@pytest.mark.parametrize("category,expect_contact", [
    ("child_abuse_suspected", "1577-1391"),
    ("medical_emergency", "119"),
    ("self_harm_signal", "1393"),
    ("domestic_violence", "1366"),
])
def test_human_review_by_safety_category(category, expect_contact):
    sr = SafetyRouting(triggered=True, category=category, contact="", reason="test")
    section = determine_human_review(verifier_results=None, safety_routing=sr)
    assert section.needed is True
    contacts = " ".join(e["contact_info"] for e in section.recommended_experts)
    assert expect_contact in contacts


def test_human_review_unverifiable_adds_lawyer():
    vr = VerifierResults(unverifiable_count=2)
    section = determine_human_review(verifier_results=vr, safety_routing=None)
    assert section.needed is True
    assert any("변호사" in e["kind"] for e in section.recommended_experts)


def test_human_review_none_needed():
    vr = VerifierResults(unverifiable_count=0)
    sr = SafetyRouting(triggered=False)
    section = determine_human_review(verifier_results=vr, safety_routing=sr)
    assert section.needed is False


# === mcp_server ===


def test_mcp_handle_review_runs_workflow():
    from jaramlaw_agent import mcp_server
    raw = {"parents": [{"role": "guardian", "age": 30}], "children": [],
           "scenario": {"query": "육아휴직 신청", "type": "labor"}}
    out = mcp_server.handle_review({"raw_input": raw, "write_audit": False})
    assert out["status"] == "success"
    assert "final_report" in out


def test_mcp_handle_review_bad_input():
    from jaramlaw_agent import mcp_server
    out = mcp_server.handle_review({"raw_input": "not a dict"})
    assert out["status"] == "error"


def test_mcp_handle_memory_search():
    from jaramlaw_agent import mcp_server
    out = mcp_server.handle_memory_search({"query": "환불"})
    assert out["status"] == "success"
    assert "memory" in out


def test_mcp_handle_audit_log():
    from jaramlaw_agent import mcp_server
    out = mcp_server.handle_audit_log({"limit": 5})
    assert out["status"] == "success"
    assert "records" in out


def test_mcp_handle_tool_unknown():
    from jaramlaw_agent import mcp_server
    out = mcp_server.handle_tool("nonexistent")
    assert out["status"] == "error"
    assert "tools" in out


def test_mcp_handle_tool_dispatch():
    from jaramlaw_agent import mcp_server
    out = mcp_server.handle_tool("memory_search", {"query": "x"})
    assert out["status"] == "success"


# === openrouter_client ===


def test_openrouter_no_key():
    from jaramlaw_agent.openrouter_client import OpenRouterClient
    c = OpenRouterClient(api_key="")
    resp = c.critique("sys", "user")
    assert resp.error == "no_api_key"
    assert resp.available is False


def test_openrouter_critique_success(monkeypatch):
    from jaramlaw_agent.openrouter_client import OpenRouterClient
    c = OpenRouterClient(api_key="key")
    monkeypatch.setattr(c, "_post", lambda model, msgs, mt: {
        "model": model,
        "choices": [{"message": {"content": '{"verdict":"PASS"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    })
    resp = c.critique("sys", "user")
    assert resp.available is True
    assert "PASS" in resp.text
    assert resp.fallback_used is False


def test_openrouter_fallback_on_primary_failure(monkeypatch):
    from jaramlaw_agent.openrouter_client import OpenRouterClient, OpenRouterError
    c = OpenRouterClient(api_key="key")
    calls = {"n": 0}

    def _post(model, msgs, mt):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OpenRouterError("HTTP 500")
        return {"model": model, "choices": [{"message": {"content": "ok"}}], "usage": {}}

    monkeypatch.setattr(c, "_post", _post)
    resp = c.critique("sys", "user")
    assert resp.available is True
    assert resp.fallback_used is True
    assert calls["n"] == 2


def test_openrouter_all_fail(monkeypatch):
    from jaramlaw_agent.openrouter_client import OpenRouterClient, OpenRouterError
    c = OpenRouterClient(api_key="key")
    def _post(model, msgs, mt):
        raise OpenRouterError("down")
    monkeypatch.setattr(c, "_post", _post)
    resp = c.critique("sys", "user")
    assert resp.error is not None
    assert resp.available is False


def test_openrouter_empty_content_then_fail(monkeypatch):
    from jaramlaw_agent.openrouter_client import OpenRouterClient
    c = OpenRouterClient(api_key="key")
    monkeypatch.setattr(c, "_post", lambda model, msgs, mt: {"choices": [{"message": {"content": "   "}}]})
    resp = c.critique("sys", "user")
    assert resp.available is False


# === budget_guard ===


def test_actual_usage_cost_no_price():
    from jaramlaw_agent.budget_guard import actual_usage_cost
    usage = actual_usage_cost("gpt-unknown", prompt_tokens=1000, completion_tokens=200, cached_tokens=400)
    assert usage["pricing_known"] is False
    assert usage["cost_usd"] is None
    assert usage["billable_input_tokens"] == 600
    assert usage["cache_hit_ratio"] == 0.4


def test_actual_usage_cost_with_price(monkeypatch):
    import jaramlaw_agent.budget_guard as bg
    monkeypatch.setattr(bg, "MODEL_PRICES_USD_PER_1K", {"gpt-x": {"in": 1.0, "out": 2.0}})
    usage = bg.actual_usage_cost("gpt-x", prompt_tokens=1000, completion_tokens=500, cached_tokens=0)
    assert usage["pricing_known"] is True
    # 1.0*(1000/1000) + 2.0*(500/1000) = 1.0 + 1.0 = 2.0
    assert usage["cost_usd"] == 2.0


def test_budget_guard_authorize_within():
    from jaramlaw_agent.budget_guard import BudgetGuard
    g = BudgetGuard(per_run_limit_usd=0.25)
    plan = {"assignments": [{"tier": "shallow"}, {"tier": "standard"}]}
    decision = g.authorize(plan)
    assert decision.allowed is True
    assert decision.estimated_cost_usd < 0.25


def test_budget_guard_authorize_exceeds():
    from jaramlaw_agent.budget_guard import BudgetGuard
    g = BudgetGuard(per_run_limit_usd=0.005)
    plan = {"assignments": [{"tier": "critical"}, {"tier": "critical"}, {"tier": "deep"}]}
    decision = g.authorize(plan)
    assert decision.allowed is False
    assert "exceeds" in decision.reason
    d = decision.to_dict()
    assert d["allowed"] is False


def test_estimate_plan_cost_bad_input():
    from jaramlaw_agent.budget_guard import estimate_plan_cost
    assert estimate_plan_cost({"assignments": "not a list"}) == 0.0
    assert estimate_plan_cost({}) == 0.0


def test_budget_guard_from_env(monkeypatch):
    from jaramlaw_agent.budget_guard import BudgetGuard
    monkeypatch.setenv("JARAMLAW_PER_RUN_BUDGET_USD", "0.50")
    monkeypatch.setenv("JARAMLAW_MONTHLY_BUDGET_USD", "not_a_number")
    g = BudgetGuard.from_env()
    assert g.per_run_limit_usd == 0.50
    assert g.monthly_limit_usd == 25.0  # 파싱 실패 → 폴백
