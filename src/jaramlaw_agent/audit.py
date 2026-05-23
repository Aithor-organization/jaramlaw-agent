"""audit — 구조화 audit log 생성 (Constitution observability)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def _serialize(obj: Any) -> Any:
    """dataclass / enum / set 등을 JSON 호환 형식으로 직렬화."""
    if is_dataclass(obj):
        return _serialize(asdict(obj))
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_serialize(v) for v in obj)
    if hasattr(obj, "value") and hasattr(obj, "name"):  # Enum
        return obj.value
    return obj


def write_audit_log(
    final_report: Any,
    base_dir: Optional[Path] = None,
) -> str:
    """final_report → audit_logs/ 디렉토리에 JSON 저장. 파일명은 hash 기반."""
    base_dir = base_dir or (Path(__file__).resolve().parent.parent.parent / "audit_logs")
    base_dir.mkdir(parents=True, exist_ok=True)

    data = _serialize(final_report)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    payload_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:12]
    audit_log_id = f"jaramlaw-{ts}-{h}"
    path = base_dir / f"{audit_log_id}.json"

    out = {
        "audit_log_id": audit_log_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schema_version": "jaramlaw-audit/v1",
        "final_report": data,
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_log_id
