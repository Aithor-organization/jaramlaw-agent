"""자람법 학습 저장소 — 상담 결과에서 성공/실패 패턴을 배우고 다음 상담에 쓴다.

## 왜 새로 쓰는가

SEAS(self-evolving-agent-system)와 Compliance-Sentinel의 학습 루프를 조사한 뒤,
그대로 베끼지 않고 두 시스템이 **닫지 못한 고리**를 처음부터 닫기로 했다.

1. **SEAS: confidence가 결과를 모른다.**
   `OutcomeTracker`가 미구현이라, "그 패턴을 적용해서 실제로 성공했는가"가
   confidence에 한 번도 반영된 적이 없다. confidence는 캡처 기본값 + 반복 기록 +
   시간 감쇠로만 움직인다 — 학습이 아니라 집계다.
   → 여기서는 `record_application_outcome()`으로 **적용 결과가 confidence를 바꾼다.**

2. **SEAS: `severity: critical = Hard Block`이 문서에만 있다.**
   어떤 코드도 강제하지 않는다. 실제 차단은 사람이 별도 hook에 손으로 옮겨 적었다.
   → 여기서는 학습 결과를 프롬프트 텍스트가 아니라 **결정론적 값**(검색 가산점,
   토큰 상한)으로 컴파일한다. LLM의 선의에 기대지 않는다.

3. **jaramlaw 기존 memory_rag: 저장만 하고 아무도 안 읽는 죽은 루프.**
   `recall()` 결과가 리포트에 실려 화면에 표시될 뿐 어떤 분기도 바꾸지 않았다.
   게다가 태그에 시드 코퍼스 전체가 들어가 모든 레코드가 모든 질의에 매칭됐다(변별력 0).
   → 여기서는 **질의에서 파생된 좁은 주제 태그**만 키로 쓴다.

## 개인정보

이 저장소에는 **어떤 개인정보도 들어가지 않는다.** 아이 생년월일·이름·지역·가족 구성은
물론이고 **부모가 입력한 질의 원문 자체가 저장되지 않는다.** 저장되는 것은
"학원비 환불 주제에서 학원법 시행령 제18조가 인용에 성공했다" 같은
**법적 주제와 법령 ID뿐**이다. `pii_gate.assert_clean()`이 저장 직전에 기계적으로 막는다.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def brain_dir() -> Path:
    """저장소 위치. 기본은 프로젝트 루트의 `.jaramlaw-brain/`.

    경로를 모듈 상수로 두고 함수 기본 인자에 박아 두면 정의 시점에 바인딩되어
    테스트에서도 배포에서도 바꿀 수 없다. 매번 읽는다 — 이 비용은 무시할 만하다.
    """
    override = os.environ.get("JARAMLAW_BRAIN_DIR")
    return Path(override) if override else PROJECT_ROOT / ".jaramlaw-brain"


def pending_file() -> Path:
    return brain_dir() / "pending_patterns.jsonl"


def brain_file() -> Path:
    return brain_dir() / "patterns.jsonl"


def apply_log_file() -> Path:
    return brain_dir() / "apply.log"


SUCCESS = "SUCCESS_PATTERN"
FAILURE = "FAILURE_PATTERN"

# 캡처 시 기본 신뢰도. 실패를 더 높게 잡는 건 SEAS와 같다 —
# 실패는 드물고, 한 번 겪은 실패를 다시 겪는 비용이 크다.
DEFAULT_CONFIDENCE = {SUCCESS: 0.6, FAILURE: 0.75}

# pending → patterns 승격 임계. 이만큼 쌓이면 자동 병합한다.
MERGE_THRESHOLD = int(os.environ.get("JARAMLAW_BRAIN_MERGE_THRESHOLD", "10"))


# ---------------------------------------------------------------------------
# PII 게이트 — 저장 직전 마지막 방어선
# ---------------------------------------------------------------------------

# 학습 레코드에 허용된 필드. 화이트리스트다 — 여기 없는 키는 저장되지 않는다.
ALLOWED_KEYS = {
    "id", "status", "context", "content", "confidence", "learned_at",
    "tags", "topic_tags", "cited_law_ids", "metrics", "applications", "wins", "losses",
}

# 값에서 절대 허용하지 않는 것.
_DATE_RE = re.compile(r"\b(19|20)\d{2}[-./]\d{1,2}[-./]\d{1,2}\b")   # 생년월일
_RRN_RE = re.compile(r"\b\d{6}\s*-\s*\d{7}\b")                        # 주민등록번호
_PHONE_RE = re.compile(r"\b01[0-9]-?\d{3,4}-?\d{4}\b")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_HANGUL_RE = re.compile(r"[가-힣]")

# 학습 키로 쓸 수 있는 **닫힌 어휘**. 블랙리스트가 아니라 화이트리스트다.
#
# 처음엔 가족 속성(dual_income, toddler...)을 블랙리스트로 막았는데 두 가지가 걸렸다:
#   1. `pregnancy`는 주제 태그(임신·출산휴가 법령을 물었다)이면서 동시에 가족 속성
#      (실제로 임신 중이다)이다. 문자열이 같아 블랙리스트로는 구분이 안 된다.
#   2. 블랙리스트는 "내가 생각 못 한 새 필드"를 놓친다. 개인정보 방어는 열거가 아니라
#      허용 목록이어야 한다.
# 그래서 `law_retrieval.derive_topic_tags`가 낼 수 있는 값만 허용한다.
# 가족 속성은 이 목록에 없으므로 구조적으로 들어올 수 없다.
LEARNABLE_TAGS = {
    "academy", "refund",
    "maternity", "pregnancy",
    "parental-leave",
    "daycare", "safety", "accident-report", "cctv",
    "school-violence",
    "child-support",
}


class PiiLeakError(ValueError):
    """학습 레코드에 개인정보가 섞였다. 저장을 거부한다."""


def assert_clean(record: dict[str, Any]) -> None:
    """저장 직전 기계적 차단.

    한글이 섞인 자유 텍스트는 통째로 거부한다. 부모가 쓴 문장이 흘러들어올 수 있는
    유일한 경로이기 때문이다. 학습에 필요한 것은 법적 주제(영문 슬러그)와 법령 ID뿐이라,
    한글을 막아도 잃는 게 없다.
    """
    extra = set(record) - ALLOWED_KEYS
    if extra:
        raise PiiLeakError(f"허용되지 않은 필드: {sorted(extra)}")

    for tag in list(record.get("topic_tags") or []) + list(record.get("tags") or []):
        if tag not in LEARNABLE_TAGS:
            raise PiiLeakError(
                f"허용된 주제 어휘가 아니다: {tag!r} — 가족 속성이나 질의 원문이 태그로 샜을 수 있다"
            )

    for key in ("context", "content"):
        value = str(record.get(key) or "")
        if _HANGUL_RE.search(value):
            raise PiiLeakError(f"{key}에 한글 자유 텍스트가 있다 — 질의 원문 유입 의심: {value[:40]!r}")
        for name, pattern in (
            ("생년월일/날짜", _DATE_RE), ("주민번호", _RRN_RE),
            ("전화번호", _PHONE_RE), ("이메일", _EMAIL_RE),
        ):
            if pattern.search(value):
                raise PiiLeakError(f"{key}에 {name} 형태가 있다: {value[:40]!r}")


# ---------------------------------------------------------------------------
# 패턴
# ---------------------------------------------------------------------------


@dataclass
class Pattern:
    """학습된 패턴 하나.

    필드를 7개로 줄였다. SEAS는 15개 넘는 필드를 정의했지만 실측 결과 `hypothesis`는
    1,084건 중 0건, `severity`는 5건만 채워졌다. 강제하지 않는 필드는 안 채워진다.
    """

    id: str
    status: str                       # SUCCESS_PATTERN | FAILURE_PATTERN
    context: str                      # 상황 슬러그 (영문. 예: "academy_refund/academy+refund")
    content: str                      # 교훈 (영문/기계 판독용)
    confidence: float
    learned_at: str
    topic_tags: list[str] = field(default_factory=list)    # 질의 파생 주제 태그 (PII 아님)
    cited_law_ids: list[str] = field(default_factory=list)  # 실제로 인용에 성공한 법령
    metrics: dict[str, Any] = field(default_factory=dict)
    # 적용 결과 추적 — SEAS가 닫지 못한 고리.
    applications: int = 0
    wins: int = 0
    losses: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _rewrite(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        for r in records:
            fp.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# 캡처
# ---------------------------------------------------------------------------


def capture(
    *,
    status: str,
    context: str,
    content: str,
    topic_tags: list[str],
    cited_law_ids: Optional[list[str]] = None,
    metrics: Optional[dict[str, Any]] = None,
    pending_path: Optional[Path] = None,
) -> dict[str, Any]:
    """패턴을 pending에 적재한다. 승격은 merge()가 따로 한다.

    2단계로 나누는 이유: 한 번의 상담 결과로 곧장 영구 저장소를 바꾸면 일시적 잡음이
    그대로 굳는다. pending에 모아 두었다가 임계치를 넘을 때 품질 게이트를 통과한 것만 올린다.
    """
    if status not in (SUCCESS, FAILURE):
        raise ValueError(f"status는 {SUCCESS} 또는 {FAILURE}: {status!r}")
    if not topic_tags:
        # 주제 태그가 없으면 나중에 아무 질의와도 매칭되지 않는다 = 저장할 가치가 없다.
        return {"captured": False, "reason": "no_topic_tags"}

    record = Pattern(
        id=f"PND-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}",
        status=status,
        context=context,
        content=content,
        confidence=DEFAULT_CONFIDENCE[status],
        learned_at=_now(),
        topic_tags=sorted(set(topic_tags)),
        cited_law_ids=sorted(set(cited_law_ids or [])),
        metrics=metrics or {},
    ).to_dict()

    assert_clean(record)   # 여기서 막힌다. 통과 못 하면 예외.
    _append(pending_path or pending_file(), record)
    return {"captured": True, "id": record["id"], "status": status}


# ---------------------------------------------------------------------------
# 병합 (pending → patterns) + 중복 통합
# ---------------------------------------------------------------------------


def merge(
    *,
    pending_path: Optional[Path] = None,
    brain_path: Optional[Path] = None,
    threshold: int = 0,
) -> dict[str, Any]:
    """pending을 본 저장소로 승격한다. 같은 (status, context)는 하나로 합친다.

    SEAS는 내용 기반 중복 제거가 없어 같은 교훈이 계속 쌓였다. 여기서는 context를
    키로 병합하고, 같은 교훈이 반복될수록 confidence를 올린다 — 단 상한을 둔다.
    반복 기록만으로 확신이 무한정 오르면 그건 학습이 아니라 메아리다.
    """
    pending_path = pending_path or pending_file()
    brain_path = brain_path or brain_file()
    pending = _read(pending_path)
    if len(pending) < threshold:
        return {"merged": 0, "pending": len(pending), "reason": "below_threshold"}
    if not pending:
        return {"merged": 0, "pending": 0}

    existing = _read(brain_path)
    by_key: dict[tuple[str, str], dict[str, Any]] = {
        (r["status"], r["context"]): r for r in existing
    }

    merged = 0
    for rec in pending:
        key = (rec["status"], rec["context"])
        prior = by_key.get(key)
        if prior is None:
            rec = dict(rec)
            rec["id"] = f"LP-{len(by_key) + 1:04d}"
            by_key[key] = rec
            merged += 1
            continue

        # 같은 상황을 또 겪었다 — 확신을 조금 올리되, 결과 없이 오르는 상한을 둔다.
        prior["confidence"] = min(0.85, round(prior["confidence"] + 0.05, 3))
        prior["learned_at"] = rec["learned_at"]
        prior["topic_tags"] = sorted(set(prior.get("topic_tags", [])) | set(rec.get("topic_tags", [])))
        prior["cited_law_ids"] = sorted(
            set(prior.get("cited_law_ids", [])) | set(rec.get("cited_law_ids", []))
        )
        prior["metrics"] = rec.get("metrics", {})
        merged += 1

    records = list(by_key.values())
    for r in records:
        assert_clean(r)
    _rewrite(brain_path, records)
    _rewrite(pending_path, [])
    return {"merged": merged, "total": len(records)}


# ---------------------------------------------------------------------------
# 검색 — 가중 태그 매칭 (임베딩 없음. 의존성 0.)
# ---------------------------------------------------------------------------


@dataclass
class Hit:
    pattern: dict[str, Any]
    score: float


def search(
    topic_tags: list[str],
    scenario_type: str = "",
    *,
    top_k: int = 5,
    brain_path: Optional[Path] = None,
) -> list[Hit]:
    """현재 질의의 주제 태그와 겹치는 패턴을 찾는다.

    점수 = 태그 겹침 비율 × confidence × (실패면 1.3)
    실패에 가산점을 주는 건 SEAS와 같다 — 실패는 희소하고, 놓치면 같은 실수를 반복한다.
    """
    brain_path = brain_path or brain_file()
    query = set(topic_tags)
    if not query:
        return []

    hits: list[Hit] = []
    for rec in _read(brain_path):
        tags = set(rec.get("topic_tags", []))
        if not tags:
            continue
        overlap = len(query & tags)
        if not overlap:
            continue
        # 자카드가 아니라 질의 기준 커버리지 — 저장된 패턴이 질의를 얼마나 설명하는가.
        score = overlap / len(query | tags)
        if scenario_type and rec.get("context", "").startswith(scenario_type):
            score *= 1.5
        score *= float(rec.get("confidence", 0.5))
        if rec.get("status") == FAILURE:
            score *= 1.3
        hits.append(Hit(pattern=rec, score=round(score, 4)))

    hits.sort(key=lambda h: -h.score)
    return hits[:top_k]


# ---------------------------------------------------------------------------
# 적용 결과 → confidence  (SEAS가 닫지 못한 고리)
# ---------------------------------------------------------------------------


def record_application_outcome(
    applied_ids: list[str],
    succeeded: bool,
    *,
    brain_path: Optional[Path] = None,
    apply_log: Optional[Path] = None,
) -> dict[str, Any]:
    """적용한 패턴이 실제로 통했는지로 confidence를 갱신한다.

    이것이 이 저장소가 '집계'가 아니라 '학습'인 유일한 이유다.
    통하면 confidence가 오르고, 통하지 않으면 내려간다. 계속 실패하는 패턴은
    바닥(0.1)까지 내려가 검색에서 사실상 사라진다 — 삭제하지 않아도 조용해진다.
    """
    if not applied_ids:
        return {"updated": 0}

    brain_path = brain_path or brain_file()
    apply_log = apply_log or apply_log_file()
    records = _read(brain_path)
    targets = set(applied_ids)
    updated = 0
    for rec in records:
        if rec.get("id") not in targets:
            continue
        rec["applications"] = int(rec.get("applications", 0)) + 1
        if succeeded:
            rec["wins"] = int(rec.get("wins", 0)) + 1
            rec["confidence"] = min(0.98, round(float(rec["confidence"]) + 0.03, 3))
        else:
            rec["losses"] = int(rec.get("losses", 0)) + 1
            rec["confidence"] = max(0.10, round(float(rec["confidence"]) - 0.10, 3))
        updated += 1

    if updated:
        _rewrite(brain_path, records)

    # 활용 로그는 1일차부터 깐다. SEAS는 6개월 뒤에 붙여서 그전 데이터가 없었다.
    apply_log.parent.mkdir(parents=True, exist_ok=True)
    with apply_log.open("a", encoding="utf-8") as fp:
        fp.write(f"{_now()}\t{'win' if succeeded else 'loss'}\t{','.join(sorted(targets))}\n")
    return {"updated": updated, "succeeded": succeeded}


def utilization(*, apply_log: Optional[Path] = None, days: int = 30) -> dict[str, Any]:
    """학습이 실제로 쓰이고 있는지. 쌓이기만 하는 저장소를 조기에 감지한다."""
    apply_log = apply_log or apply_log_file()
    if not apply_log.exists():
        return {"applications": 0, "wins": 0, "losses": 0, "win_rate": None}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    wins = losses = 0
    for line in apply_log.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            when = datetime.fromisoformat(parts[0])
        except ValueError:
            continue
        if when < cutoff:
            continue
        if parts[1] == "win":
            wins += 1
        else:
            losses += 1
    total = wins + losses
    return {
        "applications": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total, 3) if total else None,
    }
