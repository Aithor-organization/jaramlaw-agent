#!/usr/bin/env python3
"""Run AgentLoop as jaramlaw-agent's pre-deploy maintenance gate.

What this does, in order:

  1. locate the AgentLoop CLI (sibling repo); skip cleanly if it is not there
  2. emit observations from *measured* audit logs (scripts/agentloop_observations.py)
  3. assert the policy's component ids and the observations' component ids are the
     same set  <-- the reason this script exists rather than a two-line subprocess call
  4. `node src/cli.js validate` then `analyze --format json`
  5. print findings, the 10 runtime gates, and which passes had no data to run on
  6. exit 2 when --fail-on-block and the runtime action is block/rollback

On (3): AgentLoop looks observations up by component id. An id that does not match
is not an error there — it is simply "no data", so every pass skips and the report
comes back clean. A typo would therefore turn this gate green, which is the worst
possible failure for a thing whose whole job is to say "not yet". So we check.

On (5): the same logic applies to coverage. A gate with nothing to measure reports
`pass`. Printing the inactive passes is what keeps "we didn't look" from reading as
"we looked and it was fine".
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentloop_observations import build_observations  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "ops" / "agentloop" / "jaramlaw.policy.json"
DEFAULT_OUT_DIR = ROOT / "reports" / "agentloop"
TIMEOUT_SECONDS = 120

BLOCKING_ACTIONS = {"block", "rollback"}

# Which observation fields each AgentLoop pass needs before it can produce a finding.
# Mirrors the `Number.isFinite` / `typeof` guards in AgentLoop's src/core/passes.js —
# if none of a pass's inputs are present anywhere, the pass ran on nothing.
PASS_INPUTS: dict[str, list[str]] = {
    "drift": ["outputSignature", "outputEmbedding"],
    "regression (quality/safety)": ["quality", "safety"],
    "cost/latency regression": ["costUsd", "latencyMs"],
    "dependency health": ["dependencies", "version"],
    "knowledge staleness": ["@policy:lastEvaluatedAt"],
    "backward compatibility": ["schemaBreaking", "toolSignatureChanged"],
    "AgentShield security": ["metadata.agentShieldStatus"],
    "audit completeness": ["metadata.auditCount"],
    "lifecycle/decommission": ["metadata.requestsLast24h", "metadata.activeCredentials", "metadata.decommission"],
    "tool sprawl": ["metadata.toolCount"],
    "maintenance overhead": ["metadata.maintenanceOverheadUsd"],
    "budget circuit breaker": ["metadata.dailySpendRatio", "metadata.singleRequestMaxUsd", "metadata.spendRateMultiplier"],
    "SRE reliability (error budget)": ["metadata.errorBudgetBurnRate", "metadata.errorRate"],
    "SRE reliability (tail latency)": ["metadata.latencyP95Ms", "metadata.latencyP99Ms"],
    "SRE reliability (MTTR)": ["metadata.mttrMinutes"],
    "judge eval": ["judge"],
    "trajectory eval": ["trajectory"],
    "trace completeness": ["trace"],
}


# ----------------------------------------------------------------- agentloop io


def resolve_agentloop_root(explicit: Path | None = None) -> Path:
    if explicit:
        return explicit
    if env := os.environ.get("AGENTLOOP_ROOT"):
        return Path(env)
    return ROOT.parent / "AgentLoop"


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",  # AgentLoop emits UTF-8; without this Windows decodes as cp949
        errors="replace",
        capture_output=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"agentloop command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def _extract_json(text: str) -> dict:
    """`analyze` prints the payload and then a human summary line, so slice at the JSON."""
    start = text.find("{")
    if start < 0:
        raise RuntimeError("AgentLoop analyze emitted no JSON payload")
    payload, _end = json.JSONDecoder().raw_decode(text[start:])
    return payload


# ------------------------------------------------------------------ correctness


def assert_ids_align(policy: dict, observations: dict) -> None:
    """A mismatched id makes AgentLoop skip every pass and report `pass`. Refuse to run."""
    policy_ids = {c["id"] for c in policy.get("components", [])}
    observed_ids = set(observations.get("components", {}))
    if policy_ids == observed_ids:
        return
    missing = sorted(policy_ids - observed_ids)
    unknown = sorted(observed_ids - policy_ids)
    raise RuntimeError(
        "policy/observation component ids diverged — AgentLoop would silently skip "
        "these and report a false pass.\n"
        f"  declared in policy but never observed: {missing or '(none)'}\n"
        f"  observed but not declared in policy:   {unknown or '(none)'}\n"
        "Fix ops/agentloop/jaramlaw.policy.json or scripts/agentloop_observations.py "
        "so the two id sets match exactly."
    )


def _has(observation: dict, dotted: str) -> bool:
    node: Any = observation
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return node not in (None, {}, [])


def pass_coverage(policy: dict, observations: dict) -> tuple[list[str], list[str]]:
    """Split AgentLoop's passes into the ones that had data and the ones that did not."""
    components = observations.get("components", {})
    staleness_types = {"rag_index", "memory", "prompt"}
    has_staleable = any(
        c.get("type") in staleness_types and c.get("lastEvaluatedAt")
        for c in policy.get("components", [])
    )
    active, inactive = [], []
    for name, fields in PASS_INPUTS.items():
        if fields == ["@policy:lastEvaluatedAt"]:
            (active if has_staleable else inactive).append(name)
            continue
        fired = any(_has(obs, f) for obs in components.values() for f in fields)
        (active if fired else inactive).append(name)
    return active, inactive


def apply_measured_lifecycle(policy: dict, target: Path) -> dict:
    """Keep `lastEvaluatedAt` truthful for the law index: it is when the cache was last
    refreshed, not when someone last edited the policy file by hand."""
    cache = list((target / "data" / "cache" / "law_api").glob("*.json"))
    if not cache:
        return policy
    newest = max(p.stat().st_mtime for p in cache)
    stamp = datetime.fromtimestamp(newest, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    for component in policy.get("components", []):
        if component["id"] == "rag:law-index":
            component["lastEvaluatedAt"] = stamp
    return policy


# ------------------------------------------------------------------- baselining


def update_baseline(policy: dict, observations: dict) -> dict:
    """Freeze the currently measured values as the regression baseline.

    Regression passes compare against this. Re-run only when the new numbers are the
    ones you are willing to defend — re-baselining right after a regression is how a
    gate gets quietly disarmed.
    """
    carry = ("quality", "safety", "latencyMs", "costUsd", "outputSignature")
    observed = observations.get("components", {})
    for component in policy.get("components", []):
        obs = observed.get(component["id"], {})
        baseline = {key: obs[key] for key in carry if key in obs}
        if "judge" in obs:
            baseline["judge"] = obs["judge"]  # AgentLoop reads baseline.judge.scores
        if "trajectory" in obs:
            baseline["trajectory"] = {
                "toolSequence": obs["trajectory"].get("toolSequence", []),
                "stepCount": obs["trajectory"].get("stepCount"),
            }
        component["baseline"] = baseline
    policy["_baselineMeasuredAt"] = observations.get("generatedAt")
    policy["_baselineRuns"] = observations.get("_coverage", {}).get("runsAnalyzed")
    return policy


# ------------------------------------------------------------------------- gate


def run_gate(
    *,
    target: Path = ROOT,
    policy_path: Path = DEFAULT_POLICY,
    agentloop_root: Path | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict:
    agentloop_root = resolve_agentloop_root(agentloop_root)
    cli = agentloop_root / "src" / "cli.js"
    if not cli.exists():
        return {
            "status": "skipped",
            "runtime_action": "unknown",
            "reason": f"AgentLoop CLI not found at {cli} (set AGENTLOOP_ROOT)",
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    policy = apply_measured_lifecycle(
        json.loads(policy_path.read_text(encoding="utf-8")), target
    )
    observations = build_observations(target, policy)
    assert_ids_align(policy, observations)

    # AgentLoop reads files, and its cwd is its own repo, so both paths must be absolute.
    resolved_policy = out_dir / "policy.resolved.json"
    resolved_obs = out_dir / "observations.current.json"
    resolved_policy.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    resolved_obs.write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")

    _run(["node", "src/cli.js", "validate",
          "--policy", str(resolved_policy), "--observations", str(resolved_obs)],
         cwd=agentloop_root)
    analysis = _run(["node", "src/cli.js", "analyze",
                     "--policy", str(resolved_policy), "--observations", str(resolved_obs),
                     "--format", "json"],
                    cwd=agentloop_root)
    payload = _extract_json(analysis.stdout)

    report = payload.get("report", {})
    runtime_plan = payload.get("runtimePlan", {})
    active, inactive = pass_coverage(policy, observations)
    coverage = observations.get("_coverage", {})

    summary = {
        "status": report.get("summary", {}).get("status", "unknown"),
        "runtime_action": runtime_plan.get("action", "unknown"),
        "summary_counts": report.get("summary", {}),
        "findings": report.get("findings", []),
        "gates": runtime_plan.get("gates", []),
        "next_steps": runtime_plan.get("nextSteps", []),
        "coverage": {
            "runs_analyzed": coverage.get("runsAnalyzed", 0),
            "active_passes": active,
            "inactive_passes": inactive,
            "unmeasured": coverage.get("unmeasured", []),
        },
        "artifacts": {
            "policy": str(resolved_policy),
            "observations": str(resolved_obs),
        },
    }
    (out_dir / "gate_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "report.md").write_text(_markdown(summary), encoding="utf-8")
    return summary


def _markdown(summary: dict) -> str:
    counts = summary.get("summary_counts", {})
    lines = [
        "# AgentLoop Maintenance Gate — jaramlaw-agent",
        "",
        f"- status: **{summary['status'].upper()}**",
        f"- runtime action: **{summary['runtime_action']}**",
        f"- findings: {counts.get('error', 0)} error / {counts.get('warn', 0)} warn / {counts.get('info', 0)} info",
        f"- runs analyzed: {summary['coverage']['runs_analyzed']}",
        "",
        "## Findings",
    ]
    for f in summary["findings"]:
        lines.append(
            f"- **{f.get('severity', '').upper()} {f.get('code', '')}** "
            f"(`{f.get('componentId', '')}`): {f.get('message', '')}"
        )
    if not summary["findings"]:
        lines.append("- none")

    lines += ["", "## Runtime gates", ""]
    lines += [f"- `{g['name']}`: {g['status']}" for g in summary.get("gates", [])]

    lines += ["", "## Coverage — what this gate could NOT check", ""]
    lines.append(
        "A pass with no data reports nothing. These ran on nothing, so their silence "
        "is not evidence of health:"
    )
    lines += [f"- ⚪ {name}" for name in summary["coverage"]["inactive_passes"]] or ["- (none)"]
    if summary["coverage"]["unmeasured"]:
        lines += ["", "### Why", ""]
        lines += [f"- {u}" for u in summary["coverage"]["unmeasured"]]
    lines.append("")
    return "\n".join(lines)


def _print_human(summary: dict) -> None:
    if summary["status"] == "skipped":
        print(f"AgentLoop gate: SKIPPED — {summary['reason']}")
        return
    counts = summary["summary_counts"]
    print(
        f"AgentLoop gate: status={summary['status']} action={summary['runtime_action']} "
        f"({counts.get('error', 0)} error / {counts.get('warn', 0)} warn / {counts.get('info', 0)} info, "
        f"{summary['coverage']['runs_analyzed']} run(s))"
    )
    for f in summary["findings"]:
        print(f"  [{f.get('severity', '').upper():5}] {f.get('code')} {f.get('componentId')}: {f.get('message')}")
    inactive = summary["coverage"]["inactive_passes"]
    if inactive:
        print(f"  passes with no data ({len(inactive)}) — silence here is NOT a pass:")
        for name in inactive:
            print(f"    - {name}")
    for note in summary["coverage"]["unmeasured"]:
        print(f"  ! {note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgentLoop maintenance gate for jaramlaw-agent")
    parser.add_argument("--target", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--agentloop-root", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--fail-on-block", action="store_true",
                        help="exit 2 when the runtime action is block/rollback")
    parser.add_argument("--update-baseline", action="store_true",
                        help="freeze current measurements as the regression baseline and rewrite the policy")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.update_baseline:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        observations = build_observations(args.target, policy)
        assert_ids_align(policy, observations)
        policy = update_baseline(policy, observations)
        args.policy.write_text(
            json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        runs = observations.get("_coverage", {}).get("runsAnalyzed", 0)
        print(f"baseline updated from {runs} run(s) -> {args.policy}")
        if runs == 0:
            print("  warning: no runs on disk; the baseline is empty and regression passes stay inactive")
        return 0

    summary = run_gate(
        target=args.target,
        policy_path=args.policy,
        agentloop_root=args.agentloop_root,
        out_dir=args.out_dir,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_human(summary)

    if args.fail_on_block and summary.get("runtime_action") in BLOCKING_ACTIONS:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
