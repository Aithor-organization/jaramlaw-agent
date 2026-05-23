"""legalize-kr 통합 테스트. 외부 클론이 있을 때만 PASS."""

import pytest

from jaramlaw_agent.legalize_kr_client import LegalizeKrClient, LAW_ID_TO_LEGALIZE_PATH


@pytest.fixture
def client():
    return LegalizeKrClient()


def test_mapping_table_covers_22_laws():
    """시드 22+개 법령이 모두 매핑 표에 있어야 한다."""
    expected = {
        "labor-standards-74", "labor-standards-74-2",
        "equal-employment-18-2", "equal-employment-19",
        "equal-employment-22-2", "equal-employment-37",
        "childcare-33-3", "childcare-15-5", "childcare-34",
        "academy-decree-18", "school-violence-12-17",
        "child-welfare-3", "child-abuse-10", "itnet-31",
        "child-support-enforcement", "single-parent",
        "child-allowance-4", "maternal-health",
        "infectious-disease-24", "low-birth-rate-act",
    }
    assert expected.issubset(set(LAW_ID_TO_LEGALIZE_PATH.keys()))


def test_client_available_or_skip(client):
    if not client.available():
        pytest.skip("legalize-kr 클론 없음 — external/legalize-kr 미설치")
    assert client.kr_dir.exists()


def test_get_current_labor_standards(client):
    if not client.available():
        pytest.skip("legalize-kr 미설치")
    art = client.get_article("labor-standards-74")
    assert art is not None
    # 현행본 자동 선택 — 폐지된 1997 버전이 아닌 최신 시행일자
    assert art.effective_date_iso != "1997-03-13"
    assert "법률(법률).md" in art.file_path or "법률.md" in art.file_path


def test_extract_article_section(client):
    if not client.available():
        pytest.skip("legalize-kr 미설치")
    art = client.extract_article_section("labor-standards-74", "제74조")
    assert art is not None
    # excerpt에 제74조 본문이 포함
    excerpt = art.article_excerpt or ""
    assert "제74조" in excerpt
    assert "출산" in excerpt or "임산부" in excerpt


def test_list_mapped_laws_at_least_20_ok(client):
    if not client.available():
        pytest.skip("legalize-kr 미설치")
    mapped = client.list_mapped_laws()
    ok_count = sum(1 for _, _, x in mapped if x)
    # 20개 이상 매핑 OK
    assert ok_count >= 20
