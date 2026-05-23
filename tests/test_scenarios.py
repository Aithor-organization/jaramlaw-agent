"""3개 시나리오 e2e — AC1 deterministic 동작 보장."""

import yaml

from jaramlaw_agent.orchestrator import run_workflow


def _load_fixture(scenarios_dir, name):
    with (scenarios_dir / name).open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def _run(fixture):
    raw = fixture["family_profile"]
    raw["scenario"] = fixture.get("scenario", {})
    raw["reference_date"] = fixture.get("reference_date")
    raw["persona"] = fixture.get("persona")
    return run_workflow(raw, scenario_id=fixture["scenario_id"], write_audit=False)


def test_scenario_a_pregnancy_workmom(scenarios_dir):
    fx = _load_fixture(scenarios_dir, "A_pregnancy_workmom.yaml")
    report = _run(fx)
    exp = fx["expected_outputs"]

    assert not report.safety_routing.triggered  # 일반 시나리오
    assert len(report.support_matches) >= exp["support_matches_min"]
    assert len(report.rights_cards) >= exp["rights_cards_min"]
    assert report.calendar and len(report.calendar.events) >= exp["calendar_events_min"]
    # citation 완전성
    assert report.verifier_results.unverifiable_count <= exp["unverifiable_claims_max"]


def test_scenario_b_academy_refund(scenarios_dir):
    fx = _load_fixture(scenarios_dir, "B_academy_refund.yaml")
    report = _run(fx)
    exp = fx["expected_outputs"]

    assert not report.safety_routing.triggered
    assert len(report.draft_documents) >= exp["draft_documents_min"]
    # 환불 요청서 존재 + 환불액 검증
    refund_docs = [d for d in report.draft_documents if d.kind == "refund_request"]
    assert refund_docs
    calc = refund_docs[0].calculation_breakdown
    assert "refund_krw" in calc
    expected_refund = exp["expected_refund_krw"]
    tolerance = exp["expected_refund_tolerance"]
    assert abs(calc["refund_krw"] - expected_refund) <= tolerance, \
        f"refund {calc['refund_krw']} vs expected {expected_refund} (±{tolerance})"


def test_scenario_c_daycare_accident(scenarios_dir):
    fx = _load_fixture(scenarios_dir, "C_daycare_accident.yaml")
    report = _run(fx)
    exp = fx["expected_outputs"]

    # safety 라우팅 발동 — "멍이 크다" 키워드
    assert report.safety_routing.triggered == exp["safety_routing_triggered"]
    if exp["safety_routing_triggered"]:
        assert report.safety_routing.category == exp["safety_category"]
        assert exp["safety_contact"] in report.safety_routing.contact

    # safety 발동 시 일반 워크플로우 우회됨 — 권리카드/문서 없을 수 있음 (orchestrator design)
    # 그러나 human_review는 발동
    assert report.human_review.needed
    assert any(
        e.get("contact_info", "").find("1577-1391") >= 0
        for e in report.human_review.recommended_experts
    )


def test_scenario_deterministic_reruns(scenarios_dir):
    """동일 입력 → 동일 출력 (AC1 deterministic)."""
    fx = _load_fixture(scenarios_dir, "B_academy_refund.yaml")
    r1 = _run(fx)
    r2 = _run(fx)
    # 핵심 출력은 동일
    assert len(r1.support_matches) == len(r2.support_matches)
    assert len(r1.rights_cards) == len(r2.rights_cards)
    assert len(r1.draft_documents) == len(r2.draft_documents)
    # 환불액 정확 동일
    if r1.draft_documents and r2.draft_documents:
        calc1 = r1.draft_documents[0].calculation_breakdown
        calc2 = r2.draft_documents[0].calculation_breakdown
        if calc1 and calc2:
            assert calc1.get("refund_krw") == calc2.get("refund_krw")
