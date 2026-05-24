"""Minimal MCP-style tool surface for JaramLaw operations.

This module intentionally keeps side effects local. It can be called from a real
MCP adapter later, but tests and scripts can already use the same tool registry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from .audit import _serialize
from .memory_rag import JaramLawMemoryRAG
from .orchestrator import run_workflow


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def handle_review(args: dict[str, Any]) -> dict[str, Any]:
    raw_input = args.get("raw_input")
    if not isinstance(raw_input, dict):
        return {"status": "error", "message": "raw_input must be an object"}
    report = run_workflow(
        raw_input,
        scenario_id=args.get("scenario_id") if isinstance(args.get("scenario_id"), str) else None,
        write_audit=bool(args.get("write_audit", True)),
    )
    return {"status": "success", "final_report": _serialize(report)}


def handle_memory_search(args: dict[str, Any]) -> dict[str, Any]:
    raw_input = args.get("raw_input")
    if not isinstance(raw_input, dict):
        raw_input = {"scenario": {"query": str(args.get("query") or "")}}
    return {"status": "success", "memory": JaramLawMemoryRAG().recall(raw_input)}


def handle_audit_log(args: dict[str, Any]) -> dict[str, Any]:
    limit = int(args.get("limit", 20) or 20)
    records: list[dict[str, Any]] = []
    if AUDIT_DIR.exists():
        for path in sorted(AUDIT_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return {"status": "success", "count": len(records), "records": records}


TOOLS: dict[str, ToolHandler] = {
    "jaramlaw_review": handle_review,
    "memory_search": handle_memory_search,
    "audit_log": handle_audit_log,
}


def handle_tool(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = TOOLS.get(name)
    if not handler:
        return {"status": "error", "message": f"unknown tool: {name}", "tools": sorted(TOOLS)}
    return handler(args or {})


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    name = str(payload.get("tool") or "")
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    print(json.dumps(handle_tool(name, args), ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
