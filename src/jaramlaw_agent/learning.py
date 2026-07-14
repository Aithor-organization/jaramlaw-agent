"""학습 계층 — 상담 결과를 판정하고, 배운 것을 다음 상담의 동작에 주입한다.

`brain.py`가 저장소라면 이 모듈은 그 저장소를 워크플로우에 붙이는 배선이다.
두 방향이 있다:

    plan(질의)  → 과거 패턴을 읽어 **이번 실행의 파라미터를 바꾼다** (검색 가산점, 토큰 상한)
    observe(결과) → 이번 실행을 성공/실패로 판정해 저장하고, 적용했던 패턴의 confidence를 갱신한다

핵심은 plan()이 **실제 값**을 돌려준다는 것이다. "과거에 이런 게 있었으니 참고하라"는
텍스트를 LLM에 흘려보내는 게 아니라, 검색 점수와 토큰 상한이라는 숫자를 바꾼다.
LLM의 선의에 기대는 학습은 조사해 보니 대부분 발동하지 않았다.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from . import brain
from .law_retrieval import derive_topic_tags
from .openai_client import DEFAULT_ANSWER_MAX_TOKENS


# 과거 성공 인용 법령에 주는 가산점. 시나리오 태그 매칭(4.0)보다 작게 잡는다 —
# 학습은 검색을 거들어야지, 검색을 대체하면 새 법령을 영원히 못 찾는다.
LEARNED_LAW_BOOST = 2.0

# 절단 이력이 있는 주제에서 답변 상한을 얼마나 올릴지.
TRUNCATION_HEADROOM = 1000
MAX_ANSWER_TOKENS = 4000


class LearningPlan:
    """이번 실행에 적용할 학습 결과."""

    def __init__(
        self,
        topic_tags: list[str],
        law_boosts: dict[str, float],
        max_answer_tokens: int,
        applied_pattern_ids: list[str],
        hits: list[dict[str, Any]],
    ) -> None:
        self.topic_tags = topic_tags
        self.law_boosts = law_boosts
        self.max_answer_tokens = max_answer_tokens
        self.applied_pattern_ids = applied_pattern_ids
        self.hits = hits

    def to_dict(self) -> dict[str, Any]:
        return {
            "learning_version": "jaramlaw-brain/v1",
            "topic_tags": self.topic_tags,
            "law_boosts": self.law_boosts,
            "max_answer_tokens": self.max_answer_tokens,
            "applied_patterns": self.applied_pattern_ids,
            "hits": self.hits,
            # 아무것도 안 바꿨으면 정직하게 그렇게 적는다. 죽은 루프를 숨기지 않는다.
            "changed_behavior": bool(self.law_boosts) or self.max_answer_tokens != DEFAULT_ANSWER_MAX_TOKENS,
        }


def learnable_tags(scenario_query: str) -> list[str]:
    """학습 저장소의 키로 쓸 주제 태그.

    `derive_topic_tags`는 검색용이라 한글 태그(`출산휴가`, `육아휴직`)도 낸다.
    그 태그들은 법령 시드의 한글 태그와 매칭시키려고 있는 것이지 학습 키가 아니다.
    학습 키에 한글이 섞이면 (a) 질의 원문이 흘러든 것과 구분이 안 되고
    (b) PII 게이트의 한글 차단에 걸려 임신·육아휴직 상담은 영원히 학습되지 않는다.
    그래서 여기서 저장소가 아는 닫힌 어휘로 걸러 낸다.
    """
    return sorted(t for t in derive_topic_tags(scenario_query) if t in brain.LEARNABLE_TAGS)


def plan(scenario_query: str, scenario_type: str = "", *, enabled: bool = True) -> LearningPlan:
    """과거 패턴을 읽어 이번 실행의 파라미터를 정한다."""
    tags = learnable_tags(scenario_query)
    if not enabled or not tags:
        return LearningPlan(tags, {}, DEFAULT_ANSWER_MAX_TOKENS, [], [])

    hits = brain.search(tags, scenario_type, top_k=5)

    law_boosts: dict[str, float] = {}
    max_tokens = DEFAULT_ANSWER_MAX_TOKENS
    applied: list[str] = []

    for hit in hits:
        rec = hit.pattern
        applied.append(rec["id"])

        if rec["status"] == brain.SUCCESS:
            # 과거 이 주제에서 실제로 인용된 법령을 위로 끌어올린다.
            for law_id in rec.get("cited_law_ids", []):
                law_boosts[law_id] = max(
                    law_boosts.get(law_id, 0.0),
                    LEARNED_LAW_BOOST * float(rec.get("confidence", 0.5)),
                )
        else:
            # 실패에서 배운 것: 이 주제는 답변이 길어 상한에 걸렸었다 → 미리 늘려 준다.
            if rec.get("metrics", {}).get("truncated"):
                max_tokens = min(MAX_ANSWER_TOKENS, max_tokens + TRUNCATION_HEADROOM)

    return LearningPlan(
        tags,
        law_boosts,
        max_tokens,
        applied,
        [{"id": h.pattern["id"], "status": h.pattern["status"], "score": h.score} for h in hits],
    )


def classify_outcome(report_data: dict[str, Any]) -> tuple[str, list[str]]:
    """이번 상담이 성공인가 실패인가 — 결정론적으로 판정한다.

    LLM에게 자기 성적을 매기게 하지 않는다. 이번 세션에서 실측으로 확보한 신호만 쓴다:
    답변이 잘렸는가, 법령을 인용했는가, 전문가 검토가 필요한가.

    (`verified_ratio`는 쓰지 않는다 — 인용 4요소의 '존재'만 세는 지표라 항상 1.0이 나온다.
     감사에서 위조 법령도 통과시키는 게 확인됐다. 신호가 아니라 도장이다.)
    """
    reasons: list[str] = []
    ai = report_data.get("ai_answer") or {}
    safety = report_data.get("safety_routing") or {}

    # 안전 라우팅이 걸린 건은 애초에 답변을 만들지 않는다 — 성패를 논할 대상이 아니다.
    if safety.get("triggered"):
        return "", ["safety_routed"]

    if ai.get("mode") != "llm":
        return "", ["no_llm_answer"]

    if ai.get("truncated") or ai.get("error") == "truncated_empty":
        reasons.append("truncated")
    if ai.get("error"):
        reasons.append(f"error:{ai['error']}")

    citations = len(ai.get("citations") or [])
    citable = int(ai.get("citable_laws") or 0)
    if citable > 0 and citations == 0:
        # 근거 법령을 줬는데 한 건도 인용하지 않았다 = 답변이 컨텍스트를 못 썼다.
        reasons.append("no_citation_despite_context")

    if reasons:
        return brain.FAILURE, reasons

    reasons.append(f"citations:{citations}")
    return brain.SUCCESS, reasons


def observe(
    report_data: dict[str, Any],
    applied_plan: Optional[LearningPlan] = None,
    *,
    scenario_type: str = "general",
    enabled: bool = True,
) -> dict[str, Any]:
    """상담 결과를 판정해 저장하고, 적용했던 패턴의 confidence를 갱신한다."""
    if not enabled:
        return {"captured": False, "reason": "disabled"}

    status, reasons = classify_outcome(report_data)
    if not status:
        return {"captured": False, "reason": reasons[0] if reasons else "not_applicable"}

    plan_obj = applied_plan
    tags = plan_obj.topic_tags if plan_obj else []
    if not tags:
        return {"captured": False, "reason": "no_topic_tags"}

    ai = report_data.get("ai_answer") or {}

    # 이번에 실제로 인용된 법령 ID — 다음 상담에서 이 법령들을 위로 올린다.
    cited_ids = _cited_law_ids(report_data)

    # 적용했던 패턴이 통했는지 먼저 기록한다 (SEAS가 못 닫은 고리).
    outcome = {}
    if plan_obj and plan_obj.applied_pattern_ids:
        outcome = brain.record_application_outcome(
            plan_obj.applied_pattern_ids, succeeded=(status == brain.SUCCESS)
        )

    captured = brain.capture(
        status=status,
        context=f"{scenario_type}/{'+'.join(tags)}",
        content=";".join(reasons),          # 영문/기계 판독용 — 질의 원문 절대 미포함
        topic_tags=tags,
        cited_law_ids=cited_ids,
        metrics={
            "citations": len(ai.get("citations") or []),
            "truncated": bool(ai.get("truncated")),
            "model": ai.get("model"),
            "completion_tokens": ai.get("completion_tokens"),
        },
    )

    merged = brain.merge(threshold=brain.MERGE_THRESHOLD)
    return {**captured, "outcome_feedback": outcome, "merge": merged}


_ARTICLE_RE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?")


def _cited_law_ids(report_data: dict[str, Any]) -> list[str]:
    """LLM이 실제로 인용한 조문을 law_id로 되짚는다.

    인용 문자열에는 law_id가 없으므로 법령명 + 조문번호로 맞춘다.
    문자열 완전일치는 쓰지 않는다 — 시드는 `제18조 별표4`, LLM은 `제18조 별표 4`라고
    쓴다. 띄어쓰기 하나 때문에 인용을 통째로 놓치면 학습이 영원히 굶는다.
    """
    ai = report_data.get("ai_answer") or {}
    citations = " ".join(ai.get("citations") or [])
    if not citations:
        return []

    cited_articles = {_norm(a) for a in _ARTICLE_RE.findall(citations)}
    out = []
    for law in report_data.get("matched_laws") or []:
        if not isinstance(law, dict):
            continue
        name = str(law.get("law_name") or "")
        if not name or name not in citations:
            continue
        article_match = _ARTICLE_RE.search(str(law.get("article") or ""))
        if article_match and _norm(article_match.group()) not in cited_articles:
            continue
        law_id = law.get("law_id")
        if law_id:
            out.append(str(law_id))
    return sorted(set(out))


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)
