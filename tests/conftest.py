"""pytest 공통 fixture + 경로 보강."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def laws_dir(project_root: Path) -> Path:
    return project_root / "data" / "seed" / "laws"


@pytest.fixture
def supports_dir(project_root: Path) -> Path:
    return project_root / "data" / "seed" / "supports"


@pytest.fixture
def scenarios_dir(project_root: Path) -> Path:
    return project_root / "data" / "seed" / "scenarios"


@pytest.fixture
def workflow_path(project_root: Path) -> Path:
    return project_root / "workflows" / "family-legal-jaramlaw.workflow.yaml"
