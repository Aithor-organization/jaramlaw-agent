"""런타임 산출물 경로 단일 정의.

감사 로그(`audit_logs/`), 워크플로우 산출물(`runs/`), 학습 메모리
(`.jaramlaw-brain/`)는 모두 컨테이너가 살아 있는 동안 쌓이는 상태다.
저장소 루트에 흩어놓으면 Railway처럼 **서비스당 볼륨을 하나만** 허용하는
플랫폼에서 볼륨 한 개로 덮을 수 없다(docs.railway.com/reference/volumes).
그래서 셋을 `JARAMLAW_DATA_DIR` 아래로 모은다 — 볼륨 하나를 그 경로에
마운트하면 셋 다 영속화된다.

변수를 설정하지 않으면 저장소 루트를 쓴다. 로컬 개발과 기존 경로는 그대로다.

경로를 모듈 상수로 두지 않고 함수로 두는 이유는 brain.py와 같다: 상수는
import 시점에 바인딩되어 테스트에서도 배포에서도 바꿀 수 없다. 매번 읽는
비용은 무시할 만하다.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def data_root() -> Path:
    """런타임 상태의 뿌리. 미설정 시 저장소 루트."""
    override = os.environ.get("JARAMLAW_DATA_DIR")
    return Path(override) if override else PROJECT_ROOT


def audit_dir() -> Path:
    """상담 감사 로그 `*.json` 저장 위치."""
    return data_root() / "audit_logs"


def trace_log_path() -> Path:
    """워크플로우 trace 이벤트 append 대상."""
    return audit_dir() / "trace.jsonl"


def runs_dir() -> Path:
    """워크플로우 실행 산출물(매니페스트 등)."""
    return data_root() / "runs"


def brain_dir() -> Path:
    """학습 메모리.

    `JARAMLAW_BRAIN_DIR`을 먼저 본다 — 이 변수는 `JARAMLAW_DATA_DIR`보다 먼저
    존재했고 이미 배포에 쓰이고 있을 수 있어서 하위호환으로 우선한다.
    """
    override = os.environ.get("JARAMLAW_BRAIN_DIR")
    return Path(override) if override else data_root() / ".jaramlaw-brain"


def memory_path() -> Path:
    """RAG 메모리 레코드 파일."""
    return brain_dir() / "memory.jsonl"
