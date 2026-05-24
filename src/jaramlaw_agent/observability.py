"""Workflow trace export for JaramLaw.

Trace events are intentionally metadata-only. The workflow should pass redacted
counts, status values, and IDs rather than raw user text.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .audit import _serialize


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TRACE_LOG = PROJECT_ROOT / "audit_logs" / "trace.jsonl"


@dataclass(frozen=True)
class TraceEvent:
    trace_id: str
    session_id: str
    node: str
    generated_at: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkflowTracer:
    def __init__(self, *, session_id: Optional[str] = None, trace_path: Optional[Path] = None) -> None:
        self.session_id = session_id or f"trace-{uuid.uuid4().hex[:12]}"
        self.trace_path = trace_path or TRACE_LOG
        self.events: list[TraceEvent] = []
        self._exported_count = 0

    def trace(self, node: str, **data: Any) -> TraceEvent:
        event = TraceEvent(
            trace_id=f"{self.session_id}-{len(self.events) + 1:03d}",
            session_id=self.session_id,
            node=node,
            generated_at=datetime.utcnow().isoformat() + "Z",
            data=_safe_data(data),
        )
        self.events.append(event)
        return event

    def export(self) -> None:
        if self._exported_count >= len(self.events):
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as fp:
            for event in self.events[self._exported_count:]:
                fp.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        self._exported_count = len(self.events)

    def summary(self) -> dict[str, Any]:
        return {
            "trace_version": "jaramlaw-trace/v1",
            "session_id": self.session_id,
            "events": len(self.events),
            "nodes": [event.node for event in self.events],
            "local_trace": str(self.trace_path),
        }


def _safe_data(data: dict[str, Any]) -> dict[str, Any]:
    serialized = _serialize(data)
    return _truncate_strings(serialized)


def _truncate_strings(value: Any, *, limit: int = 220) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "...[truncated]"
    if isinstance(value, list):
        return [_truncate_strings(item, limit=limit) for item in value]
    if isinstance(value, dict):
        return {str(key): _truncate_strings(item, limit=limit) for key, item in value.items()}
    return value
