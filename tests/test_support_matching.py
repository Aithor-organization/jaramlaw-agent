from jaramlaw_agent.family_context import build_family_profile
from jaramlaw_agent.support_matching import match_supports


def test_match_supports_scenario_a_pregnancy():
    raw = {
        "reference_date": "2026-05-24",
        "parents": [
            {"role": "mother", "age": 32, "employment": "정규직", "region_code": "11440"},
            {"role": "father", "age": 34, "employment": "정규직", "region_code": "11440"},
        ],
        "children": [
            {"name_masked": "C1", "birth_date": "2024-05-15", "facility": "어린이집"},
            {"name_masked": "C2", "expected_birth_date": "2026-12-15"},
        ],
    }
    profile = build_family_profile(raw)
    matches = match_supports(profile)
    names = {m.name for m in matches}
    # 핵심 매칭 보장 — 첫째 24개월 + 둘째 임신 중 시점
    # 첫째 부모급여(0-23개월)는 종료 / 둘째 부모급여는 출생 후. 아동수당 + 출산휴가/육아휴직급여 매칭.
    assert any("아동수당" in n for n in names)
    assert any("출산휴가" in n or "육아휴직" in n for n in names)


def test_match_supports_scenario_b_school_age():
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "father", "age": 38, "employment": "정규직", "region_code": "41590"}],
        "children": [
            {"name_masked": "C1", "birth_date": "2019-08-10"},  # 초1
            {"name_masked": "C2", "birth_date": "2022-03-15", "facility": "어린이집"},
        ],
    }
    profile = build_family_profile(raw)
    matches = match_supports(profile)
    names = {m.name for m in matches}
    assert any("아동수당" in n for n in names)


def test_match_supports_single_parent():
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 45, "employment": "자영업"}],
        "children": [{"name_masked": "C1", "birth_date": "2013-06-01"}],  # 중1
        "income_decile": 4,
    }
    profile = build_family_profile(raw)
    matches = match_supports(profile)
    names = {m.name for m in matches}
    assert any("한부모" in n for n in names)


def test_supports_have_citation():
    """모든 매칭된 지원금의 legal_basis가 완전한 citation."""
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직", "region_code": "11440"}],
        "children": [{"name_masked": "C1", "birth_date": "2024-05-15"}],
    }
    profile = build_family_profile(raw)
    matches = match_supports(profile)
    assert matches
    for m in matches:
        assert m.legal_basis.is_complete(), f"{m.support_id} missing citation"
