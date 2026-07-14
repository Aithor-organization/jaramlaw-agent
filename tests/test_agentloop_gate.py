"""Contract tests for the AgentLoop pre-deploy maintenance gate.

These pin the two properties that decide whether the gate is worth having:

  1. it never invents a metric it did not measure, and
  2. it refuses to report a pass when it actually measured nothing.

(2) is the sharp edge. AgentLoop resolves observations by component id and treats an
unknown id as "no data", so every pass skips and the report comes back clean — a typo
in a component id would turn the gate green. That must fail loudly, and it is tested
here rather than trusted.

Fully offline: every test builds its own audit-log fixture, so nothing depends on what
happens to be sitting in the developer's audit_logs/ directory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agentloop_observations import build_observations  # noqa: E402
from run_agentloop_gate import (  # noqa: E402
    DEFAULT_POLICY,
    assert_ids_align,
    pass_coverage,
    run_gate,
    update_baseline,
)

POLICY = json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))


def _write_run(
    target: Path,
    *,
    session: str,
    answer_mode: str = "llm",
    verified_ratio: float = 1.0,
    validation: str = "PASS",
    law_mode: str = "live",
    law_errors: list[str] | None = None,
    with_tokens: bool = False,
) -> None:
    """Write one audit log + its trace events, in the real on-disk shape."""
    audit = target / "audit_logs"
    audit.mkdir(parents=True, exist_ok=True)

    answer: dict = {"mode": answer_mode, "total_tokens": 4626, "model": "gpt-5.6-luna"}
    if with_tokens:
        answer |= {"prompt_tokens": 3000, "completion_tokens": 1626, "finish_reason": "stop"}

    report = {
        "scenario_id": "academy_refund",
        "family_profile": {"children": 1},
        "verifier_results": {"verified_ratio": verified_ratio},
        "independent_validation": {"status": validation, "findings": []},
        "safety_routing": {"triggered": False},
        "law_source": {
            "mode": law_mode,
            "elapsed_ms": 600,
            "errors": law_errors or [],
            "details": [{"law": "x", "article": "1"}],
        },
        "ai_answer": answer,
        "budget_guard": {
            "allowed": True,
            "estimated_cost_usd": 0.027,
            "actual_usage": {"model": "gpt-5.6-luna", "pricing_known": False, "cost_usd": None},
        },
        "trace_summary": {
            "session_id": session,
            "events": 18,
            "nodes": ["workflow_start", "input_guard", "ai_answer", "audit_log"],
        },
    }
    (audit / f"jaramlaw-{session}.json").write_text(
        json.dumps({"final_report": report}, ensure_ascii=False), encoding="utf-8"
    )
    with (audit / "trace.jsonl").open("a", encoding="utf-8") as fh:
        for idx, stamp in enumerate(("2026-07-14T11:00:00.000000Z", "2026-07-14T11:00:07.000000Z")):
            fh.write(json.dumps({
                "trace_id": f"{session}-{idx:03d}",
                "session_id": session,
                "node": "workflow_start" if idx == 0 else "audit_log",
                "generated_at": stamp,
                "data": {},
            }) + "\n")


@pytest.fixture(autouse=True)
def _no_ambient_model_env(monkeypatch) -> None:
    """Model resolution reads the environment. A developer with JARAMLAW_MODEL_PIN
    exported would otherwise see different results than CI."""
    for var in ("JARAMLAW_MODEL_PIN", "JARAMLAW_MODEL_CLASSIFY",
                "JARAMLAW_MODEL_ANSWER", "JARAMLAW_MODEL_DRAFT"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def target(tmp_path: Path) -> Path:
    (tmp_path / "data" / "cache" / "law_api").mkdir(parents=True)
    (tmp_path / "data" / "cache" / "law_api" / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('version = "0.1.0"\n', encoding="utf-8")
    _write_run(tmp_path, session="s1")
    return tmp_path


# --- the false-pass guard --------------------------------------------------


def test_policy_and_emitter_agree_on_component_ids(target: Path) -> None:
    """The shipped policy and the emitter must describe the same system."""
    assert_ids_align(POLICY, build_observations(target, POLICY))


def test_unknown_component_id_is_rejected_instead_of_silently_skipped(target: Path) -> None:
    observations = build_observations(target, POLICY)
    observations["components"]["model:typo"] = {"quality": 1.0}
    with pytest.raises(RuntimeError, match="false pass"):
        assert_ids_align(POLICY, observations)


def test_missing_component_observation_is_rejected(target: Path) -> None:
    observations = build_observations(target, POLICY)
    del observations["components"]["agent:jaramlaw"]
    with pytest.raises(RuntimeError, match="never observed"):
        assert_ids_align(POLICY, observations)


# --- never fabricate -------------------------------------------------------


def test_cost_is_omitted_not_guessed_when_pricing_is_unknown(target: Path) -> None:
    """actual_usage.cost_usd is null until JARAMLAW_MODEL_PRICES is injected. The
    emitter must leave costUsd absent rather than fall back to budget_guard's
    estimated_cost_usd, which is a per-tier constant unrelated to real billing."""
    observations = build_observations(target, POLICY)
    agent = observations["components"]["agent:jaramlaw"]
    assert "costUsd" not in agent
    assert any("costUsd" in note for note in observations["_coverage"]["unmeasured"])


def test_tail_latency_is_not_computed_from_a_handful_of_runs(target: Path) -> None:
    observations = build_observations(target, POLICY)
    metadata = observations["components"]["agent:jaramlaw"]["metadata"]
    assert "latencyP95Ms" not in metadata
    assert "latencyP99Ms" not in metadata


def test_rule_mode_runs_are_excluded_from_latency(target: Path) -> None:
    """A rule-mode fallback never calls a model; folding it into the latency mean would
    drag the baseline down and mask a later LLM regression."""
    _write_run(target, session="s2", answer_mode="rule")
    observations = build_observations(target, POLICY)
    agent = observations["components"]["agent:jaramlaw"]
    assert agent["metadata"]["nonLlmRunsExcluded"] == 1
    assert agent["latencyMs"] == pytest.approx(7000, rel=0.01)  # only s1, the llm run


def test_seed_mode_is_degradation_not_an_error_budget_burn(target: Path) -> None:
    """`LAW_API_KEY unset -> seed mode` lands in law_source.errors, but it is a
    misconfiguration, not an API failure. Counting it as an error would make the gate
    cry wolf on any machine without a key — and a gate that cries wolf gets ignored."""
    _write_run(target, session="s2", law_mode="cache", law_errors=["LAW_API_KEY 미설정 — 시드 모드"])
    law = build_observations(target, POLICY)["components"]["tool:law-api"]
    assert law["metadata"]["errorRate"] == 0.0
    assert law["metadata"]["degradedModeRate"] == pytest.approx(0.5)


# --- what the gate actually catches ----------------------------------------


def test_missing_token_telemetry_surfaces_as_incomplete_trace(target: Path) -> None:
    checklist = build_observations(target, POLICY)["components"]["agent:jaramlaw"]["trace"]["checklist"]
    assert checklist["tokens"] is False
    assert checklist["finishReason"] is False
    assert checklist["guardrail"] is True


def test_trace_checklist_goes_green_once_tokens_are_recorded(target: Path) -> None:
    """The exit criterion for the observability backlog item, pinned as a test."""
    _write_run(target, session="s2", with_tokens=True)
    checklist = build_observations(target, POLICY)["components"]["agent:jaramlaw"]["trace"]["checklist"]
    assert checklist["tokens"] is True
    assert checklist["finishReason"] is True


def test_model_swapped_by_env_is_flagged_as_a_compat_break(target: Path, monkeypatch) -> None:
    """The deployed agent must be the agent that was reviewed. A model pinned in the
    policy but overridden at runtime is a backward-compat break, not a detail."""
    monkeypatch.setenv("JARAMLAW_MODEL_ANSWER", "gpt-5.6-sol")
    answer = build_observations(target, POLICY)["components"]["model:answer"]
    assert answer["toolSignatureChanged"] is True
    assert answer["metadata"]["pinnedModel"] == "gpt-5.6-luna"


def test_matching_model_is_not_flagged(target: Path) -> None:
    answer = build_observations(target, POLICY)["components"]["model:answer"]
    assert "toolSignatureChanged" not in answer


# --- coverage honesty ------------------------------------------------------


def test_passes_without_data_are_reported_as_inactive(target: Path) -> None:
    """Silence from a pass that ran on nothing must not read as a pass."""
    active, inactive = pass_coverage(POLICY, build_observations(target, POLICY))
    assert "budget circuit breaker" in inactive  # no cost data
    assert "SRE reliability (MTTR)" in inactive  # no incident record
    assert "judge eval" in active
    assert "trace completeness" in active


def test_no_runs_on_disk_is_reported_rather_than_passed(tmp_path: Path) -> None:
    (tmp_path / "audit_logs").mkdir()
    (tmp_path / "data" / "cache" / "law_api").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('version = "0.1.0"\n', encoding="utf-8")
    observations = build_observations(tmp_path, POLICY)
    assert observations["_coverage"]["runsAnalyzed"] == 0
    assert any("ALL runtime metrics" in n for n in observations["_coverage"]["unmeasured"])


# --- gate wiring -----------------------------------------------------------


def test_gate_skips_cleanly_when_agentloop_is_absent(target: Path, tmp_path: Path) -> None:
    """AgentLoop is a sibling repo and may not be checked out (it is private). The gate
    must degrade to a skip, not crash the build."""
    summary = run_gate(
        target=target,
        agentloop_root=tmp_path / "nope",
        out_dir=tmp_path / "reports",
    )
    assert summary["status"] == "skipped"
    assert summary["runtime_action"] == "unknown"


@pytest.mark.parametrize(
    ("action", "expected_exit"),
    [("block", 2), ("rollback", 2), ("pause_canary", 0), ("promote", 0)],
)
def test_fail_on_block_exit_code(monkeypatch, action: str, expected_exit: int) -> None:
    """The contract CI will lean on when the gate flips from report-only to blocking."""
    import run_agentloop_gate as gate

    monkeypatch.setattr(gate, "run_gate", lambda **_: {
        "status": "block" if expected_exit else "review",
        "runtime_action": action,
        "summary_counts": {},
        "findings": [],
        "coverage": {"runs_analyzed": 1, "inactive_passes": [], "unmeasured": []},
    })
    assert gate.main(["--fail-on-block"]) == expected_exit
    assert gate.main([]) == 0, "without --fail-on-block the gate must never break the build"


def test_baseline_is_written_where_agentloop_actually_reads_it(target: Path) -> None:
    """AgentLoop reads baseline.judge.scores (passes.js). Writing baseline.judgeScores —
    as the JB adapter does — silently disables JUDGE_REGRESSION forever."""
    policy = json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))
    updated = update_baseline(policy, build_observations(target, POLICY))
    agent = next(c for c in updated["components"] if c["id"] == "agent:jaramlaw")
    assert agent["baseline"]["judge"]["scores"]["citation_integrity"] == 1.0
    assert "judgeScores" not in agent["baseline"]
