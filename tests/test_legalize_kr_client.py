"""legalize_kr_client — tmp_path에 가짜 legalize-kr 저장소를 만들어 파일 로직 커버.

get_article / extract_article_section / search_full_text / list_mapped_laws /
_pick_current_law_file(충돌 해소) / _parse_frontmatter 전 경로.
"""

from __future__ import annotations

import pytest

from jaramlaw_agent.config import Config
from jaramlaw_agent.legalize_kr_client import (
    LegalizeKrClient,
    _parse_frontmatter,
)


LAW_MD = """---
제목: 근로기준법
시행일자: 20210701
공포일자: 20210101
출처: https://law.go.kr/근로기준법
---
# 근로기준법

##### 제74조(임산부의 보호)
① 사용자는 임신 중의 여성에게 출산 전후 휴가를 90일 주어야 한다.

##### 제75조(육아 시간)
생후 1년 미만 유아를 가진 여성 근로자의 청구가 있으면 휴게 시간을 준다.
"""


@pytest.fixture
def legalize_repo(tmp_path):
    """가짜 legalize-kr 저장소 구조를 만든다: {root}/kr/근로기준법/법률.md"""
    kr = tmp_path / "kr" / "근로기준법"
    kr.mkdir(parents=True)
    (kr / "법률.md").write_text(LAW_MD, encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(legalize_repo):
    cfg = Config(legalize_kr_path=legalize_repo)
    return LegalizeKrClient(cfg)


# === _parse_frontmatter ===


def test_parse_frontmatter_ok():
    fm, body = _parse_frontmatter(LAW_MD)
    assert fm["제목"] == "근로기준법"
    assert fm["시행일자"] == 20210701
    assert "제74조" in body


def test_parse_frontmatter_none():
    fm, body = _parse_frontmatter("no frontmatter here")
    assert fm == {}
    assert body == "no frontmatter here"


# === available ===


def test_available(client):
    assert client.available() is True


def test_unavailable(tmp_path):
    cfg = Config(legalize_kr_path=tmp_path / "nope")
    assert LegalizeKrClient(cfg).available() is False


# === get_article ===


def test_get_article(client):
    art = client.get_article("labor-standards-74")
    assert art is not None
    assert art.law_name == "근로기준법"
    assert art.effective_date_iso == "20210701"
    assert art.source_url == "https://law.go.kr/근로기준법"
    assert art.title == "근로기준법"
    assert "제74조" in art.body_full


def test_get_article_unmapped(client):
    assert client.get_article("nonexistent-law") is None


def test_get_article_missing_dir(tmp_path):
    cfg = Config(legalize_kr_path=tmp_path)
    (tmp_path / "kr").mkdir()
    c = LegalizeKrClient(cfg)
    # 매핑은 있으나 디렉토리 부재
    assert c.get_article("labor-standards-74") is None


# === extract_article_section ===


def test_extract_article_section(client):
    art = client.extract_article_section("labor-standards-74", "제74조")
    assert art is not None
    assert art.article_excerpt is not None
    assert "출산 전후 휴가" in art.article_excerpt
    # 다음 조문(제75조)은 excerpt에 포함되지 않아야
    assert "육아 시간" not in art.article_excerpt


def test_extract_article_not_found_returns_full(client):
    art = client.extract_article_section("labor-standards-74", "제999조")
    assert art is not None
    # 조문 못 찾으면 전체 body 반환 (excerpt None)
    assert art.article_excerpt is None


def test_extract_article_unmapped(client):
    assert client.extract_article_section("nonexistent", "제1조") is None


# === search_full_text ===


def test_search_full_text_hit(client):
    results = client.search_full_text("출산 전후 휴가", max_results=5)
    assert len(results) >= 1
    assert results[0].law_name == "근로기준법"
    assert results[0].article_excerpt is not None


def test_search_full_text_no_hit(client):
    results = client.search_full_text("존재하지않는키워드XYZ")
    assert results == []


# === list_mapped_laws ===


def test_list_mapped_laws(client):
    mapped = client.list_mapped_laws()
    # 매핑 표 전체가 나오고, 근로기준법만 True
    assert len(mapped) > 20
    labor = [row for row in mapped if row[0] == "labor-standards-74"]
    assert labor and labor[0][2] is True
    # 저장소에 없는 다른 법령은 False
    others = [row for row in mapped if row[0] == "civil-law-custody"]
    assert others and others[0][2] is False


# === _pick_current_law_file (충돌 해소) ===


def test_pick_current_prefers_newer_disambiguated(tmp_path):
    """법률(법률).md 처럼 충돌 해소 파일이 여럿이면 시행일자 최신 우선."""
    kr = tmp_path / "kr" / "근로기준법"
    kr.mkdir(parents=True)
    old = "---\n시행일자: 20200101\n---\n# old"
    new = "---\n시행일자: 20250101\n---\n# new"
    (kr / "법률.md").write_text(old, encoding="utf-8")
    (kr / "법률(법률).md").write_text(new, encoding="utf-8")

    cfg = Config(legalize_kr_path=tmp_path)
    c = LegalizeKrClient(cfg)
    art = c.get_article("labor-standards-74")
    assert art is not None
    assert "new" in art.body_full  # 최신 시행일자 파일 선택
