"""학습 루프 회귀 방지.

조사해 보니 SEAS와 Compliance-Sentinel 양쪽 모두 같은 자리에서 루프가 끊겼다.
저장은 하는데 아무도 안 읽거나(죽은 루프), 읽기는 하는데 결과가 confidence로
돌아오지 않는다(집계). 여기 테스트는 그 두 지점을 못박는 것이 전부다.

그리고 이 저장소에는 아동 개인정보가 절대 들어가면 안 된다 — 그것도 여기서 막는다.
"""

import pytest

from jaramlaw_agent import brain, learning


@pytest.fixture()
def isolated_brain(tmp_path, monkeypatch):
    monkeypatch.setenv("JARAMLAW_BRAIN_DIR", str(tmp_path))
    return tmp_path


# --- 개인정보 배제 --------------------------------------------------------


def test_query_text_cannot_be_stored(isolated_brain):
    """부모가 쓴 문장이 저장소에 들어가면 안 된다."""
    with pytest.raises(brain.PiiLeakError):
        brain.capture(
            status=brain.SUCCESS,
            context="academy_refund/academy",
            content="학원비 환불을 거부당했어요",   # 질의 원문
            topic_tags=["academy"],
        )


def test_child_birth_date_cannot_be_stored(isolated_brain):
    with pytest.raises(brain.PiiLeakError):
        brain.capture(
            status=brain.SUCCESS,
            context="academy/2019-08-10",
            content="ok",
            topic_tags=["academy"],
        )


def test_family_attributes_cannot_be_stored(isolated_brain):
    """가족 구성은 단독 가구에서 준식별자가 된다 — 주제 어휘에 없으면 거부."""
    for tag in ("dual_income", "single_parent", "toddler", "second_child_pregnancy"):
        with pytest.raises(brain.PiiLeakError):
            brain.capture(
                status=brain.SUCCESS,
                context="a/b",
                content="ok",
                topic_tags=["academy", tag],
            )


def test_learning_key_is_topic_not_family():
    """학습 키는 '무엇을 물었나'(주제)이지 '누가 물었나'(가족)가 아니다."""
    tags = learning.learnable_tags("학원비 환불을 거부당했어요")
    assert set(tags) == {"academy", "refund"}
    assert all(t in brain.LEARNABLE_TAGS for t in tags)

    # 한글 태그는 검색용이라 학습 키에서 걸러진다 (PII 게이트의 한글 차단과 충돌 방지).
    maternity = learning.learnable_tags("출산휴가 며칠인가요")
    assert "출산휴가" not in maternity
    assert "maternity" in maternity


def test_clean_record_is_stored(isolated_brain):
    result = brain.capture(
        status=brain.SUCCESS,
        context="academy_refund/academy+refund",
        content="citations:3",
        topic_tags=["academy", "refund"],
        cited_law_ids=["academy-decree-18"],
        metrics={"citations": 3, "truncated": False},
    )
    assert result["captured"] is True


# --- 루프가 실제로 닫히는가 (핵심) ---------------------------------------


def test_learning_changes_retrieval_ranking(isolated_brain):
    """저장만 하고 아무도 안 읽으면 죽은 루프다. 랭킹이 실제로 바뀌어야 한다."""
    from jaramlaw_agent.family_context import build_family_profile
    from jaramlaw_agent.law_retrieval import retrieve_matched_laws

    query = "양육비를 못 받고 있어요"
    profile = build_family_profile(
        {"reference_date": "2026-07-14", "parents": [], "children": [], "events": [], "flags": []}
    )

    def rank_of(law_id, boosts):
        laws = retrieve_matched_laws(
            family_profile=profile, scenario_query=query, persona_hint="P1",
            top_k=15, learned_boosts=boosts,
        )
        return next((i for i, l in enumerate(laws, 1) if l.law_id == law_id), None)

    before_plan = learning.plan(query, "child_support_unpaid")
    assert before_plan.law_boosts == {}
    assert before_plan.to_dict()["changed_behavior"] is False
    before = rank_of("single-parent", before_plan.law_boosts)

    # 과거 상담에서 이 법령이 실제로 인용에 성공했다.
    brain.capture(
        status=brain.SUCCESS,
        context="child_support_unpaid/child-support",
        content="citations:2",
        topic_tags=["child-support"],
        cited_law_ids=["single-parent"],
        metrics={"citations": 2, "truncated": False},
    )
    brain.merge()

    after_plan = learning.plan(query, "child_support_unpaid")
    assert after_plan.law_boosts.get("single-parent")
    assert after_plan.to_dict()["changed_behavior"] is True
    after = rank_of("single-parent", after_plan.law_boosts)

    # 검색되지 않던 법령이 등장했거나(before=None), 있던 법령이 위로 올라왔어야 한다.
    assert after is not None, "학습한 법령이 여전히 검색되지 않는다 = 죽은 루프"
    if before is not None:
        assert after <= before, f"순위가 개선되지 않았다: {before} → {after}"


def test_truncation_failure_raises_token_ceiling(isolated_brain):
    """실패에서 배운다: 이 주제는 답변이 잘렸었다 → 다음엔 상한을 늘려 시작한다."""
    from jaramlaw_agent.openai_client import DEFAULT_ANSWER_MAX_TOKENS

    query = "학교폭력 신고 절차가 궁금해요"
    assert learning.plan(query, "school_violence").max_answer_tokens == DEFAULT_ANSWER_MAX_TOKENS

    brain.capture(
        status=brain.FAILURE,
        context="school_violence/school-violence",
        content="truncated",
        topic_tags=["school-violence"],
        metrics={"truncated": True},
    )
    brain.merge()

    assert learning.plan(query, "school_violence").max_answer_tokens > DEFAULT_ANSWER_MAX_TOKENS


def test_outcome_feeds_back_into_confidence(isolated_brain):
    """SEAS가 끝내 구현하지 못한 고리 — 적용 결과가 confidence를 바꾼다.

    이게 없으면 confidence는 '몇 번 기록됐나'일 뿐 '실제로 통했나'가 아니다.
    """
    brain.capture(
        status=brain.SUCCESS,
        context="academy_refund/academy",
        content="citations:3",
        topic_tags=["academy"],
        cited_law_ids=["academy-decree-18"],
    )
    brain.merge()
    pattern_id = brain._read(brain.brain_file())[0]["id"]
    start = brain._read(brain.brain_file())[0]["confidence"]

    brain.record_application_outcome([pattern_id], succeeded=True)
    after_win = brain._read(brain.brain_file())[0]["confidence"]
    assert after_win > start

    for _ in range(5):
        brain.record_application_outcome([pattern_id], succeeded=False)
    after_losses = brain._read(brain.brain_file())[0]
    assert after_losses["confidence"] < start
    assert after_losses["losses"] == 5
    # 계속 틀리는 패턴은 바닥으로 내려가 검색에서 조용해진다 — 삭제하지 않아도 된다.
    assert after_losses["confidence"] <= 0.35

    util = brain.utilization()
    assert util["applications"] == 6 and util["wins"] == 1


# --- 결과 판정 -----------------------------------------------------------


def test_outcome_classification_is_deterministic():
    """LLM에게 자기 성적을 매기게 하지 않는다."""
    success, reasons = learning.classify_outcome(
        {"ai_answer": {"mode": "llm", "citations": ["근로기준법 제74조"], "citable_laws": 5}}
    )
    assert success == brain.SUCCESS

    truncated, reasons = learning.classify_outcome(
        {"ai_answer": {"mode": "llm", "truncated": True, "citations": [], "citable_laws": 5}}
    )
    assert truncated == brain.FAILURE
    assert "truncated" in reasons

    # 근거를 줬는데 한 건도 인용 안 함 = 답변이 컨텍스트를 못 썼다.
    no_cite, reasons = learning.classify_outcome(
        {"ai_answer": {"mode": "llm", "citations": [], "citable_laws": 8}}
    )
    assert no_cite == brain.FAILURE
    assert "no_citation_despite_context" in reasons

    # 안전 라우팅 건은 답변 자체를 안 만든다 — 성패를 논할 대상이 아니다.
    skipped, reasons = learning.classify_outcome(
        {"safety_routing": {"triggered": True}, "ai_answer": {}}
    )
    assert skipped == ""
    assert reasons == ["safety_routed"]
