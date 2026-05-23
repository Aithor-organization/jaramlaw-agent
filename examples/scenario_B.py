"""시나리오 B — 초1 딸 학원 환불 거부, 화성.

기대 동작: 환불 요청서 초안 1건, 환불액 641,667원 (±2원).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jaramlaw_agent.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["demo", "--scenario", "B", "--output", "runs/scenario_B.json", "--print-first-card"]))
