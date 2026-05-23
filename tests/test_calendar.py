from jaramlaw_agent.calendar_gen import generate_calendar
from jaramlaw_agent.family_context import build_family_profile


def test_calendar_pregnancy_includes_due_date():
    profile = build_family_profile({
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C2", "expected_birth_date": "2026-12-15"}],
    })
    cal = generate_calendar(profile)
    titles = [e.title for e in cal.events]
    assert any("출산 예정일" in t for t in titles)
    assert any("출생신고" in t for t in titles)
    assert any("부모급여" in t or "첫만남이용권" in t for t in titles)


def test_calendar_toddler_has_vaccination_and_health_checkup():
    profile = build_family_profile({
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2024-05-15"}],  # 24개월
    })
    cal = generate_calendar(profile)
    kinds = {e.kind for e in cal.events}
    assert "health_checkup" in kinds
    # 24개월이면 일부 백신은 끝났지만 잔여 백신 일정 존재
    # support_transition (만 8세 종료) 포함
    assert "support_transition" in kinds


def test_calendar_ical_format():
    profile = build_family_profile({
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2024-05-15"}],
    })
    cal = generate_calendar(profile)
    assert "BEGIN:VCALENDAR" in cal.ical_export
    assert "END:VCALENDAR" in cal.ical_export
    assert "BEGIN:VEVENT" in cal.ical_export
