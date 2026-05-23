from jaramlaw_agent.family_context import build_family_profile
from jaramlaw_agent.law_retrieval import LawApiClient, load_all_laws, retrieve_matched_laws


def test_load_all_laws():
    laws = load_all_laws()
    assert len(laws) >= 20  # 시드 20+ 보장
    # 핵심 조문 존재
    ids = {l.law_id for l in laws}
    expected = {
        "labor-standards-74",
        "equal-employment-19",
        "childcare-33-3",
        "academy-decree-18",
    }
    assert expected.issubset(ids)


def test_retrieve_pregnancy_workmom():
    """시나리오 A — 임신 키워드 매칭."""
    raw = {
        "reference_date": "2026-05-24",
        "parents": [
            {"role": "mother", "age": 32, "employment": "정규직"},
            {"role": "father", "age": 34, "employment": "정규직"},
        ],
        "children": [
            {"name_masked": "C1", "birth_date": "2024-05-15"},
            {"name_masked": "C2", "expected_birth_date": "2026-12-15"},
        ],
    }
    profile = build_family_profile(raw)
    laws = retrieve_matched_laws(profile, "둘째 임신 출산휴가 육아휴직", persona_hint="P1")
    law_ids = {l.law_id for l in laws}
    # 핵심 매칭 보장
    assert "labor-standards-74" in law_ids  # 출산휴가
    assert "equal-employment-19" in law_ids  # 육아휴직


def test_retrieve_academy_refund():
    """시나리오 B — 학원 환불."""
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "father", "age": 38, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2019-08-10"}],
    }
    profile = build_family_profile(raw)
    laws = retrieve_matched_laws(profile, "학원 환불 거부", persona_hint="P2")
    law_ids = {l.law_id for l in laws}
    assert "academy-decree-18" in law_ids


def test_retrieve_daycare_accident():
    """시나리오 C — 어린이집 사고."""
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2024-05-15"}],
    }
    profile = build_family_profile(raw)
    laws = retrieve_matched_laws(profile, "어린이집 사고 멍 CCTV", persona_hint="P1")
    law_ids = {l.law_id for l in laws}
    assert "childcare-33-3" in law_ids
    assert "childcare-15-5" in law_ids


def test_law_api_client_seeded_mode():
    client = LawApiClient(api_key=None)
    assert client.seeded
    results = client.search_current_laws("출산휴가")
    assert results
    one = client.get_current_law_article("labor-standards-74")
    assert one is not None
    assert one.law_id == "labor-standards-74"
