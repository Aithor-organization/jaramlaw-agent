"""Small local memory/RAG layer for workflow operations.

Memory records are sanitized metadata about previous workflow outcomes. They are
not used as legal authority and they do not replace seed-law retrieval.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .audit import _serialize
from .models import FinalReport


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / ".jaramlaw-brain"
MEMORY_PATH = MEMORY_DIR / "memory.jsonl"


class JaramLawMemoryRAG:
    def __init__(self, *, memory_path: Path | None = None) -> None:
        self.memory_path = memory_path or MEMORY_PATH

    def recall(self, redacted_input: dict[str, Any], *, limit: int = 3) -> dict[str, Any]:
        query_tags = _extract_tags(redacted_input)
        records = self._read_records()
        scored: list[tuple[int, dict[str, Any]]] = []
        for record in records:
            tags = set(record.get("tags", [])) if isinstance(record.get("tags"), list) else set()
            score = len(set(query_tags) & tags)
            if score > 0:
                scored.append((score, record))

        matches = [
            {"score": score, "record": record}
            for score, record in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
        ]
        return {
            "memory_version": "jaramlaw-memory/v1",
            "enabled": True,
            "path": str(self.memory_path),
            "query_tags": query_tags,
            "matches": matches,
            "record_count": len(records),
        }

    def capture_outcome(self, report: FinalReport) -> dict[str, Any]:
        if os.environ.get("JARAMLAW_DISABLE_MEMORY_CAPTURE") == "1":
            return {"captured": False, "reason": "disabled"}

        data = _serialize(report)
        record = {
            "memory_version": "jaramlaw-memory/v1",
            "captured_at": datetime.utcnow().isoformat() + "Z",
            "scenario_id": data.get("scenario_id"),
            "workflow_version": data.get("workflow_version"),
            "tags": _report_tags(data),
            "law_ids": [item.get("law_id") for item in data.get("matched_laws", []) if isinstance(item, dict)],
            "support_ids": [item.get("support_id") for item in data.get("support_matches", []) if isinstance(item, dict)],
            "verified_ratio": _nested(data, "verifier_results", "verified_ratio"),
            "human_review_needed": _nested(data, "human_review", "needed"),
            "readonly": True,
            "needs_approval": True,
        }

        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with self.memory_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return {"captured": True, "path": str(self.memory_path), "tags": record["tags"]}

    def _read_records(self) -> list[dict[str, Any]]:
        if not self.memory_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.memory_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
        return records


def _extract_tags(payload: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    scenario = payload.get("scenario") if isinstance(payload, dict) else {}
    scenario = scenario if isinstance(scenario, dict) else {}
    scenario_type = scenario.get("type")
    if isinstance(scenario_type, str) and scenario_type:
        tags.add(f"scenario:{scenario_type}")
    for field in ("flags", "life_stages"):
        values = payload.get(field)
        if isinstance(values, list):
            tags.update(str(item) for item in values if item)
    query = scenario.get("query")
    if isinstance(query, str):
        for token in re.findall(r"[A-Za-z0-9_\-]{4,}", query.lower()):
            tags.add(token[:32])
    return sorted(tags)[:24]


def _report_tags(data: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    scenario_id = data.get("scenario_id")
    if scenario_id:
        tags.add(f"scenario_id:{scenario_id}")
    profile = data.get("family_profile") if isinstance(data.get("family_profile"), dict) else {}
    for item in profile.get("life_stages", []) if isinstance(profile, dict) else []:
        tags.add(str(item))
    for item in profile.get("flags", []) if isinstance(profile, dict) else []:
        tags.add(str(item))
    for law in data.get("matched_laws", []):
        if isinstance(law, dict):
            tags.update(str(tag) for tag in law.get("tags", []) if tag)
    return sorted(tags)[:24]


def _nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
