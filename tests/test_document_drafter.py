from jaramlaw_agent.document_drafter import (
    compute_academy_refund,
    draft_academy_refund_request,
    draft_daycare_accident_report_demand,
    draft_documents_for_scenario,
)
from jaramlaw_agent.family_context import build_family_profile


def test_compute_academy_refund_scenario_b():
    """시나리오 B 환불액 ±2원 정확."""
    calc = compute_academy_refund(
        total_paid_krw=1_050_000,
        days_used=35,
        total_days=90,
    )
    # 1050000 * 55 / 90 = 641666.67
    assert abs(calc["refund_krw"] - 641667) <= 2
    assert calc["remaining_days"] == 55


def test_compute_academy_refund_zero_days_used():
    calc = compute_academy_refund(total_paid_krw=300_000, days_used=0, total_days=30)
    assert calc["refund_krw"] == 300_000


def test_draft_academy_refund_has_citation():
    profile = build_family_profile({
        "reference_date": "2026-05-24",
        "parents": [{"role": "father", "age": 38, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2019-08-10"}],
    })
    doc = draft_academy_refund_request(profile, {
        "academy_name": "테스트학원",
        "total_paid_krw": 1_050_000,
        "days_used": 35,
        "total_days": 90,
        "months_paid": 3,
    })
    assert "학원의 설립" in doc.body_markdown  # 정식 법령명 인용
    assert "환불" in doc.title
    assert any(lb.law and lb.article for lb in doc.legal_basis)
    # disclaimer 포함 (Constitution 원칙 1)
    assert "법률 자문이 아닙니다" in doc.body_markdown


def test_draft_daycare_accident_demand():
    profile = build_family_profile({
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2024-05-15"}],
    })
    doc = draft_daycare_accident_report_demand(profile, {
        "notification_text": "낮잠 후 미끄러져 멍",
        "parent_observation": "멍이 큼",
    })
    assert "영유아보육법" in doc.body_markdown
    assert "1577-1391" in doc.body_markdown


def test_drafter_router_daycare_with_cctv_denied():
    profile = build_family_profile({
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2024-05-15"}],
    })
    docs = draft_documents_for_scenario(
        "daycare_accident",
        profile,
        {"notification_text": "x", "parent_observation": "y", "cctv_access_denied": True},
    )
    assert len(docs) == 2  # 사고 경위서 + CCTV 신청서
    kinds = {d.kind for d in docs}
    assert "accident_report_demand" in kinds
    assert "cctv_access" in kinds
