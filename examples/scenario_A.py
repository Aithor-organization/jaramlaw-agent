"""시나리오 A — 둘째 임신 + 첫째 4세, 워킹맘, 서울 마포.

기대 동작: 지원 매칭 5+건, 권리카드 4+장, 캘린더 8+건, safety 미발동.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 패키지 경로 자동 보강 (개발 환경 편의)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jaramlaw_agent.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["demo", "--scenario", "A", "--output", "runs/scenario_A.json"]))
