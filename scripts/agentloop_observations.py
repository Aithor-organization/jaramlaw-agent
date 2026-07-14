#!/usr/bin/env python3
"""Emit AgentLoop observations for jaramlaw-agent from *measured* runtime artifacts.

Design contract (the reason this file exists):

  AgentLoop's passes guard every metric with `Number.isFinite` and skip silently
  when it is absent. That means a fabricated number is indistinguishable from a
  measured one at the gate, while a missing number costs nothing but coverage.
  So this emitter only ever writes a field it can trace back to a real artifact,
  and records the ones it *cannot* fill in `_coverage.unmeasured`, which the gate
  runner prints. An empty report must never be readable as "healthy" — it has to
  be readable as "we did not measure this".

Sources (all under the repo, all produced by the running agent):
  audit_logs/jaramlaw-*.json   final_report.{verifier_results,independent_validation,
                               safety_routing,trace_summary,law_source,ai_answer,budget_guard}
  audit_logs/trace.jsonl       per-session node timeline -> wall-clock latency
  data/cache/law_api/*.json    law cache freshness
  pyproject.toml               project version
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

# Component ids. These MUST match ops/agentloop/jaramlaw.policy.json exactly:
# AgentLoop looks observations up by id and treats an unknown id as "no data",
# which makes every pass skip and the gate report a false pass. run_agentloop_gate.py
# asserts the two sets are equal before trusting any result.
AGENT = "agent:jaramlaw"
WORKFLOW = "workflow:consult"
MODEL_CLASSIFY = "model:classify"
MODEL_ANSWER = "model:answer"
MODEL_DRAFT = "model:draft"
PROMPT_ANSWER = "prompt:answer-system"
RAG_LAW = "rag:law-index"
TOOL_LAW_API = "tool:law-api"
TOOL_AUDIT = "tool:audit-log"

# Roles are resolved the same way the agent resolves them at runtime, so a model
# swapped in via env shows up as a signature change instead of passing unnoticed.
MODEL_ROLE_ENV = {
    MODEL_CLASSIFY: ("JARAMLAW_MODEL_CLASSIFY", "gpt-5.4-nano"),
    MODEL_ANSWER: ("JARAMLAW_MODEL_ANSWER", "gpt-5.6-luna"),
    MODEL_DRAFT: ("JARAMLAW_MODEL_DRAFT", "gpt-5.6-terra"),
}

MAX_RUNS = 20  # how many recent audit logs feed the aggregates
MIN_RUNS_FOR_TAIL_LATENCY = 20  # p95/p99 on a handful of runs is noise, not a metric


# --------------------------------------------------------------------------- io


def _load_audit_logs(target: Path, limit: int = MAX_RUNS) -> list[dict]:
    files = sorted(
        (target / "audit_logs").glob("jaramlaw-*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    runs: list[dict] = []
    for path in files[-limit:]:
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue  # a corrupt log is not a metric; drop it rather than guess
    return runs


def _load_session_latencies(target: Path) -> dict[str, float]:
    """Wall-clock ms per session, from the first to the last trace event."""
    trace = target / "audit_logs" / "trace.jsonl"
    if not trace.exists():
        return {}
    stamps: dict[str, list[datetime]] = {}
    for line in trace.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            session = event["session_id"]
            stamps.setdefault(session, []).append(_parse_ts(event["generated_at"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return {
        session: (max(ts) - min(ts)).total_seconds() * 1000.0
        for session, ts in stamps.items()
        if len(ts) >= 2
    }


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _project_version(target: Path) -> str:
    match = re.search(
        r"^version\s*=\s*['\"]([^'\"]+)['\"]",
        (target / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1) if match else "unknown"


# ---------------------------------------------------------------- measurements


def _mean(values: Iterable[float]) -> float | None:
    data = [v for v in values if isinstance(v, (int, float))]
    return statistics.fmean(data) if data else None


def _put(target: dict, key: str, value: Any) -> None:
    """Write only measured values. A None never reaches the observation."""
    if value is not None:
        target[key] = value


def _output_signature(report: dict) -> str:
    """A stable shape-of-the-answer signature, not its wording.

    Drift here means the workflow started returning a structurally different
    report (a section vanished, a new one appeared) — which is what breaks the UI
    and downstream consumers. Wording drift is the judge's job, not this one.
    """
    sections = sorted(k for k, v in report.items() if v not in (None, [], {}, ""))
    answer_mode = (report.get("ai_answer") or {}).get("mode") or "none"
    return f"{answer_mode}|{'.'.join(sections)}"


def _trace_checklist(report: dict) -> dict[str, bool]:
    """Does one run actually leave behind the five things an operator needs?

    This is the observability contract, measured rather than asserted. It is
    expected to be partially false today; that is the point — TRACE_INCOMPLETE is
    the finding that turns "we have no logging" into a gate result.
    """
    answer = report.get("ai_answer") or {}
    law = report.get("law_source") or {}
    return {
        # the request that produced this run is reconstructible
        "input": bool(report.get("family_profile")) and bool(report.get("scenario_id")),
        # external calls recorded their inputs/outputs
        "toolIo": bool(law.get("details")),
        # token accounting present (needs prompt/completion, not just a total)
        "tokens": answer.get("prompt_tokens") is not None
        and answer.get("completion_tokens") is not None,
        # guardrail verdict recorded
        "guardrail": report.get("safety_routing") is not None,
        # we know why generation stopped (truncation vs natural stop)
        "finishReason": answer.get("finish_reason") is not None,
    }


def _is_llm_run(report: dict) -> bool:
    return (report.get("ai_answer") or {}).get("mode") == "llm"


def _agent_observation(
    reports: list[dict],
    latencies: dict[str, float],
    unmeasured: list[str],
) -> dict:
    obs: dict[str, Any] = {"metadata": {}}
    latest = reports[-1]

    # Latency and cost are only comparable across runs that took the same path. A
    # rule-mode fallback run never calls a model, so folding it into the mean would
    # quietly drag the baseline down and mask a real LLM latency regression later.
    # Quality and safety are structural checks that apply to every run, so they are
    # aggregated over all of them.
    llm_runs = [r for r in reports if _is_llm_run(r)]
    if len(llm_runs) < len(reports):
        obs["metadata"]["nonLlmRunsExcluded"] = len(reports) - len(llm_runs)

    # quality — citation verification ratio. Structural integrity of the answer's
    # legal grounding, NOT its substantive correctness. There is no answer-accuracy
    # eval in this repo yet (see docs/operational-readiness.md).
    _put(obs, "quality", _mean(
        (r.get("verifier_results") or {}).get("verified_ratio") for r in reports
    ))

    # safety — the independent validator's verdict, per run.
    validations = [
        1.0 if (r.get("independent_validation") or {}).get("status") == "PASS" else 0.0
        for r in reports
        if (r.get("independent_validation") or {}).get("status")
    ]
    _put(obs, "safety", _mean(validations))

    # latency — real wall clock, joined through trace_summary.session_id.
    run_latencies = [
        latencies[sid]
        for r in llm_runs
        if (sid := (r.get("trace_summary") or {}).get("session_id")) in latencies
    ]
    _put(obs, "latencyMs", _mean(run_latencies))

    # cost — actual_usage.cost_usd is None until JARAMLAW_MODEL_PRICES is injected.
    # estimated_cost_usd exists but is a per-tier constant, unrelated to real billing,
    # so it is deliberately NOT used as a cost metric.
    costs = [
        c for r in llm_runs
        if (c := ((r.get("budget_guard") or {}).get("actual_usage") or {}).get("cost_usd")) is not None
    ]
    if costs:
        _put(obs, "costUsd", _mean(costs))
        _put(obs["metadata"], "singleRequestMaxUsd", max(costs))
    else:
        unmeasured.append(
            "costUsd — budget_guard.actual_usage.cost_usd is null "
            "(JARAMLAW_MODEL_PRICES not injected); cost + budget passes stay inactive"
        )

    obs["outputSignature"] = _output_signature(latest)

    # trajectory — the node path the workflow actually walked.
    summary = latest.get("trace_summary") or {}
    nodes = summary.get("nodes")
    if isinstance(nodes, list) and nodes:
        law_errors = len((latest.get("law_source") or {}).get("errors") or [])
        obs["trajectory"] = {
            "toolSequence": nodes,
            "toolCallErrors": law_errors,
            "stepCount": summary.get("events") or len(nodes),
        }

    # judge — measured structural rubrics. Not an LLM judge; named for what it is.
    scores: dict[str, float] = {}
    citation = _mean((r.get("verifier_results") or {}).get("verified_ratio") for r in reports)
    if citation is not None:
        scores["citation_integrity"] = round(citation, 4)
    if validations:
        scores["independent_validation"] = round(statistics.fmean(validations), 4)
    if scores:
        obs["judge"] = {"scores": scores}

    obs["trace"] = {"checklist": _trace_checklist(latest)}

    # error rate — a run that produced no usable answer. A rule-mode fallback DID
    # answer, so it is not an error; it is a degradation, tracked separately below.
    errored = [
        1.0 if (r.get("ai_answer") or {}).get("mode") in {"error", None} else 0.0
        for r in reports
    ]
    _put(obs["metadata"], "errorRate", _mean(errored))

    # tail latency needs a real sample; refuse to compute it from a handful of runs.
    if len(run_latencies) >= MIN_RUNS_FOR_TAIL_LATENCY:
        ordered = sorted(run_latencies)
        obs["metadata"]["latencyP95Ms"] = ordered[int(len(ordered) * 0.95) - 1]
        obs["metadata"]["latencyP99Ms"] = ordered[int(len(ordered) * 0.99) - 1]
    else:
        unmeasured.append(
            f"latencyP95Ms/latencyP99Ms — only {len(run_latencies)} run(s) on disk, "
            f"need >={MIN_RUNS_FOR_TAIL_LATENCY}; SRE tail-latency pass stays inactive"
        )

    unmeasured.append(
        "mttrMinutes — no incident record exists; MTTR pass stays inactive"
    )

    # external tools this agent can reach (law API + OpenAI). Workflow nodes are
    # pipeline stages, not tools, so they are deliberately not counted here.
    obs["metadata"]["toolCount"] = 2

    # Only a hard failure marks the dependency unhealthy. Seed/cache mode means the
    # law API was unreachable or unkeyed — real, but it is a deploy precondition
    # (see docs/operational-readiness.md), not a CI failure: CI has no LAW_API_KEY.
    law_mode = (latest.get("law_source") or {}).get("mode")
    obs["dependencies"] = {
        TOOL_LAW_API: {"status": "unhealthy" if law_mode == "error" else "healthy"}
    }
    return obs


def _law_api_observation(reports: list[dict], unmeasured: list[str]) -> dict:
    """Live-law dependency health.

    `law_source.errors` carries two very different things: a real API failure, and a
    "no LAW_API_KEY — seed mode" notice. Counting the latter as an error-budget burn
    would make the gate cry wolf on a laptop with no key, and a gate that cries wolf
    gets ignored. So a *degraded* run (served from seed/cache instead of live law) is
    reported as degradation, and only mode=="error" counts against the error budget.
    """
    latest_law = reports[-1].get("law_source") or {}
    obs: dict[str, Any] = {"metadata": {}}

    # Latency is only meaningful for runs that actually hit the network.
    live_latencies = [
        e for r in reports
        if (law := (r.get("law_source") or {})).get("mode") == "live"
        and isinstance(e := law.get("elapsed_ms"), (int, float))
    ]
    if live_latencies:
        _put(obs, "latencyMs", _mean(live_latencies))
    else:
        unmeasured.append(
            "tool:law-api latencyMs — no run reached the live API "
            "(LAW_API_KEY unset?); latency regression pass stays inactive"
        )

    modes = [(r.get("law_source") or {}).get("mode") for r in reports]
    obs["metadata"]["errorRate"] = _mean([1.0 if m == "error" else 0.0 for m in modes]) or 0.0
    degraded = [1.0 if m not in ("live", "error") else 0.0 for m in modes]
    obs["metadata"]["degradedModeRate"] = _mean(degraded) or 0.0
    obs["outputSignature"] = f"mode={latest_law.get('mode')}"
    return obs


def _rag_observation(target: Path) -> dict:
    """Law cache freshness. lastEvaluatedAt in the policy drives the staleness pass;
    here we report how much of the cache is actually present."""
    cache = list((target / "data" / "cache" / "law_api").glob("*.json"))
    return {
        "metadata": {"cachedLawCount": len(cache)},
        "outputSignature": f"cached={len(cache)}",
    }


def _audit_observation(target: Path, reports: list[dict]) -> dict:
    """auditCompletenessPass fires when a 'tool' component whose id contains 'audit'
    reports auditCount == 0 while the policy requires >= 1."""
    count = len(list((target / "audit_logs").glob("jaramlaw-*.json")))
    return {"metadata": {"auditCount": count}}


def _model_observation(component_id: str, policy_pinned: str | None) -> dict:
    """A model role resolved at runtime. If the resolved id differs from the model the
    policy was reviewed against, that is a backward-compat break — the deployed agent is
    not the agent that was signed off on."""
    env_var, default = MODEL_ROLE_ENV[component_id]
    resolved = os.environ.get("JARAMLAW_MODEL_PIN") or os.environ.get(env_var) or default
    obs: dict[str, Any] = {"metadata": {"resolvedModel": resolved}}
    if policy_pinned and resolved != policy_pinned:
        obs["toolSignatureChanged"] = True
        obs["metadata"]["pinnedModel"] = policy_pinned
    return obs


# ------------------------------------------------------------------- assembly


def build_observations(target: Path, policy: dict | None = None) -> dict:
    reports = [r["final_report"] for r in _load_audit_logs(target) if "final_report" in r]
    unmeasured: list[str] = []
    components: dict[str, dict] = {}

    pinned = {}
    if policy:
        pinned = {c["id"]: c.get("version") for c in policy.get("components", [])}

    if not reports:
        # No run has happened. Emit an empty-but-honest document: every pass will
        # skip, and the runner will refuse to call that a pass.
        unmeasured.append(
            "ALL runtime metrics — audit_logs/ contains no jaramlaw-*.json; "
            "run the workflow once before trusting this gate"
        )
    else:
        latencies = _load_session_latencies(target)
        components[AGENT] = _agent_observation(reports, latencies, unmeasured)
        components[WORKFLOW] = {
            "outputSignature": _output_signature(reports[-1]),
            "trace": {"checklist": _trace_checklist(reports[-1])},
        }
        components[TOOL_LAW_API] = _law_api_observation(reports, unmeasured)
        components[TOOL_AUDIT] = _audit_observation(target, reports)

    components[RAG_LAW] = _rag_observation(target)
    # The system prompt has no runtime metric — it is carried so the staleness pass
    # can remind us to re-review it (policy.lastEvaluatedAt), and so the observation
    # id set stays equal to the policy id set (see the coverage assertion in the runner).
    components[PROMPT_ANSWER] = {"metadata": {"definedIn": "src/jaramlaw_agent/openai_client.py"}}
    for model_id in MODEL_ROLE_ENV:
        components[model_id] = _model_observation(model_id, pinned.get(model_id))

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "jaramlaw-agent/scripts/agentloop_observations.py",
        "components": components,
        # Not part of AgentLoop's schema — the runner reads it and prints it so that
        # a thin report is never mistaken for a clean one.
        "_coverage": {
            "runsAnalyzed": len(reports),
            "projectVersion": _project_version(target),
            "unmeasured": unmeasured,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit AgentLoop observations for jaramlaw-agent")
    parser.add_argument("--target", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path, help="policy file, used to detect model pin drift")
    parser.add_argument("--out", type=Path, help="write here instead of stdout")
    args = parser.parse_args(argv)

    policy = json.loads(args.policy.read_text(encoding="utf-8")) if args.policy else None
    observations = build_observations(args.target, policy)
    payload = json.dumps(observations, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
