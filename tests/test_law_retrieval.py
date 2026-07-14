from jaramlaw_agent.family_context import build_family_profile
from jaramlaw_agent.law_api_client import LawApiClient, _normalize_article_no, build_source_url
from jaramlaw_agent.law_retrieval import load_all_laws, retrieve_matched_laws


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


def test_law_api_client_disabled_without_key():
    """LAW_API_KEY가 없으면 enabled=False — 조용히 빈 결과를 주는 대신 명시적으로 꺼진다."""
    from jaramlaw_agent.config import Config

    client = LawApiClient(config=Config(law_api_key=None))
    assert client.enabled() is False


def test_normalize_article_no():
    """'제18조의2' 같은 가지번호 조문이 장(章) 번호와 섞이지 않아야 한다."""
    assert _normalize_article_no("제74조") == "74"
    assert _normalize_article_no("74") == "74"
    assert _normalize_article_no("제18조의2") == "18-2"
    assert _normalize_article_no("제33조의3") == "33-3"


def test_build_source_url_jo_format():
    """JO는 조번호 4자리 + 가지번호 2자리 (인용 4요소의 출처주소)."""
    url = build_source_url("근로기준법", mst="265959", article_no="제74조")
    assert "MST=265959" in url
    assert "JO=007400" in url
    sub = build_source_url("남녀고용평등과 일·가정 양립 지원에 관한 법률", mst="276851", article_no="제18조의2")
    assert "JO=001802" in sub
    # MST가 없으면 법령명 기반 주소로라도 출처를 채운다
    assert build_source_url("근로기준법").startswith("https://www.law.go.kr/")
