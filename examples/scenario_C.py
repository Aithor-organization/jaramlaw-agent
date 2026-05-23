"""시나리오 C — 어린이집 24개월 아들 사고.

기대 동작:
  - 권리카드 2+장 (사고 보고 + CCTV)
  - 초안 문서 2건 (사고 경위서 + CCTV 열람)
  - safety 라우팅 발동 (child_abuse_suspected, 1577-1391)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jaramlaw_agent.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["demo", "--scenario", "C", "--output", "runs/scenario_C.json"]))
