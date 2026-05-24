"""Agent topology loader for the central team contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TOPOLOGY_PATH = PROJECT_ROOT / "agents" / "team.yaml"


def load_team_topology(path: str | Path = DEFAULT_TOPOLOGY_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "topology_version": "jaramlaw-team/v1",
            "status": "missing",
            "path": str(p),
            "agents": [],
        }
    with p.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("topology_version", "jaramlaw-team/v1")
    data["status"] = "loaded"
    data["path"] = str(p)
    return data


def summarize_team_topology(path: str | Path = DEFAULT_TOPOLOGY_PATH) -> dict[str, Any]:
    topology = load_team_topology(path)
    agents = topology.get("agents", [])
    agents = agents if isinstance(agents, list) else []
    return {
        "topology_version": topology.get("topology_version"),
        "status": topology.get("status"),
        "path": topology.get("path"),
        "orchestration_pattern": topology.get("orchestration_pattern"),
        "agent_count": len(agents),
        "critical_roles": [
            item.get("id")
            for item in agents
            if isinstance(item, dict) and item.get("criticality") in {"deep", "critical"}
        ],
    }
