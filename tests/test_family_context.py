from datetime import date

from jaramlaw_agent.family_context import (
    build_family_profile,
    classify_life_stage,
    compute_age_months,
)
from jaramlaw_agent.models import Child, LifeStage


def test_compute_age_months():
    ref = date(2026, 5, 24)
    assert compute_age_months("2024-05-15", ref) == 24
    assert compute_age_months("2024-05-25", ref) == 23
    assert compute_age_months(None, ref) is None


def test_classify_life_stage_pregnancy():
    c = Child(name_masked="C2", expected_birth_date="2026-12-15", pregnancy_week=12)
    assert classify_life_stage(c, date(2026, 5, 24)) == LifeStage.PREGNANCY


def test_classify_life_stage_toddler():
    c = Child(name_masked="C1", birth_date="2024-05-15")  # 24개월
    assert classify_life_stage(c, date(2026, 5, 24)) == LifeStage.TODDLER


def test_classify_life_stage_elementary():
    c = Child(name_masked="C1", birth_date="2019-08-10")  # 만 6세 9개월 → elementary
    assert classify_life_stage(c, date(2026, 5, 24)) == LifeStage.ELEMENTARY


def test_build_family_profile_flags_second_child_pregnancy():
    raw = {
        "reference_date": "2026-05-24",
        "parents": [
            {"role": "mother", "age": 32, "employment": "정규직"},
            {"role": "father", "age": 34, "employment": "정규직"},
        ],
        "children": [
            {"name_masked": "C1", "birth_date": "2024-05-15"},
            {"name_masked": "C2", "expected_birth_date": "2026-12-15", "pregnancy_week": 12},
        ],
    }
    profile = build_family_profile(raw)
    assert "second_child_pregnancy" in profile.flags
    assert "second_child" in profile.flags
    assert "dual_income" in profile.flags
    assert "working_mom" in profile.flags
    assert "pregnancy" in profile.life_stages
    assert "toddler" in profile.life_stages


def test_build_family_profile_single_parent():
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 45, "employment": "자영업"}],
        "children": [{"name_masked": "C1", "birth_date": "2013-06-01"}],  # 중1
    }
    profile = build_family_profile(raw)
    assert "single_parent" in profile.flags
    assert "middle" in profile.life_stages
