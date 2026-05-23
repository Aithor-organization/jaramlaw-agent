from jaramlaw_agent.family_context import build_family_profile
from jaramlaw_agent.law_retrieval import retrieve_matched_laws
from jaramlaw_agent.rights_card import generate_rights_cards, render_card_markdown


def test_generate_rights_cards_scenario_a():
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
    laws = retrieve_matched_laws(profile, "둘째 임신 출산휴가 육아휴직 배우자", persona_hint="P1")
    cards = generate_rights_cards(laws, profile)
    titles = {c.title for c in cards}
    assert any("출산휴가" in t for t in titles)
    assert any("육아휴직" in t for t in titles)


def test_card_markdown_disclaimer_present():
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "expected_birth_date": "2026-12-15"}],
    }
    profile = build_family_profile(raw)
    laws = retrieve_matched_laws(profile, "임신 출산휴가", persona_hint="P1")
    cards = generate_rights_cards(laws, profile)
    if not cards:
        return
    md = render_card_markdown(cards[0])
    assert "법률 자문이 아닙니다" in md
    assert "근거 법령" in md
    assert "신고" in md


def test_card_has_citation():
    raw = {
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 32, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "expected_birth_date": "2026-12-15"}],
    }
    profile = build_family_profile(raw)
    laws = retrieve_matched_laws(profile, "임신 출산휴가", persona_hint="P1")
    cards = generate_rights_cards(laws, profile)
    for c in cards:
        assert c.legal_basis.is_complete(), f"card {c.card_id} missing citation"
