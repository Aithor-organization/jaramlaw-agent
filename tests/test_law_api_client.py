"""law_api_client — 법제처 Open API 클라이언트 (urllib mock).

네트워크를 타지 않고 _http_get을 canned XML로 대체해 파싱·에러 분기를 커버한다.
"""

from __future__ import annotations

import urllib.error

import pytest

from jaramlaw_agent import agentshield_bridge as bridge
from jaramlaw_agent.config import Config
from jaramlaw_agent.law_api_client import (
    LawApiArticle,
    LawApiAuthError,
    LawApiClient,
    LawApiError,
    LawApiPermanentError,
    _normalize_article_no,
    build_source_url,
)


def _client(key="testkey"):
    cfg = Config(law_api_key=key, law_api_base_url="https://www.law.go.kr")
    return LawApiClient(cfg, timeout=1.0)


# === _normalize_article_no ===


@pytest.mark.parametrize("raw,expected", [
    ("제74조", "74"),
    ("74", "74"),
    ("제74조의2", "74-2"),
    ("74-2", "74-2"),
    ("", ""),
    ("근로기준법", "근로기준법"),
])
def test_normalize_article_no(raw, expected):
    assert _normalize_article_no(raw) == expected


# === build_source_url ===


def test_build_source_url_with_mst_and_article():
    url = build_source_url("근로기준법", mst="12345", article_no="제18조의2")
    assert "MST=12345" in url
    assert "JO=001802" in url


def test_build_source_url_mst_only():
    url = build_source_url("근로기준법", mst="12345")
    assert "MST=12345" in url
    assert "JO=" not in url


def test_build_source_url_name_only():
    url = build_source_url("근로기준법")
    assert "%EA" in url or "근로기준법" in url  # quoted or raw


# === enabled / disabled ===


def test_disabled_client_raises():
    c = _client(key="")
    assert c.enabled() is False
    with pytest.raises(LawApiError):
        c.search_laws("근로기준법")
    with pytest.raises(LawApiError):
        c.get_law_article(mst="123")


# === search_laws 파싱 ===


SEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
  <law>
    <법령일련번호>264617</법령일련번호>
    <법령명한글>근로기준법</법령명한글>
    <법령ID>001234</법령ID>
    <공포일자>20210101</공포일자>
    <시행일자>20210701</시행일자>
    <소관부처명>고용노동부</소관부처명>
    <법령구분명>법률</법령구분명>
    <법령상세링크>/DRF/lawService.do?x=1</법령상세링크>
  </law>
</LawSearch>"""


def test_search_laws_parses(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_get", lambda url: SEARCH_XML)
    results = c.search_laws("근로기준법", display=5, search_mode=1)
    assert len(results) == 1
    r = results[0]
    assert r.law_name == "근로기준법"
    assert r.law_mst == "264617"
    assert r.department == "고용노동부"
    assert r.detail_url.startswith("https://www.law.go.kr")


def test_search_laws_bad_xml_raises(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_get", lambda url: "<<not xml")
    with pytest.raises(LawApiError):
        c.search_laws("x")


def test_search_laws_auth_error(monkeypatch):
    """법제처는 인증 실패도 HTTP 200 <Response>로 준다 → LawApiAuthError."""
    c = _client()
    auth_xml = "<Response><result>error</result><msg>OC not registered</msg></Response>"
    monkeypatch.setattr(c, "_http_get", lambda url: auth_xml)
    with pytest.raises(LawApiAuthError):
        c.search_laws("x")


# === get_law_article 파싱 ===


ARTICLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawService>
  <기본정보>
    <법령명_한글>근로기준법</법령명_한글>
    <시행일자>20210701</시행일자>
    <법령일련번호>264617</법령일련번호>
  </기본정보>
  <조문>
    <조문단위>
      <조문여부>전문</조문여부>
      <조문내용>제3장 근로계약</조문내용>
    </조문단위>
    <조문단위>
      <조문여부>조문</조문여부>
      <조문번호>74</조문번호>
      <조문제목>임산부의 보호</조문제목>
      <조문내용>제74조(임산부의 보호)</조문내용>
      <항><항내용>① 사용자는 임신 중의 여성에게 출산 전후 휴가를 주어야 한다.</항내용></항>
    </조문단위>
  </조문>
</LawService>"""


def test_get_law_article_parses_and_filters(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_get", lambda url: ARTICLE_XML)
    art = c.get_law_article(mst="264617")
    assert isinstance(art, LawApiArticle)
    assert art.law_name == "근로기준법"
    assert art.effective_date == "20210701"
    # 전문(장 제목)은 걸러지고 조문만 남는다
    assert len(art.articles) == 1
    assert art.articles[0]["article"] == "74"
    assert "출산 전후 휴가" in art.articles[0]["text"]


def test_get_law_article_find_article(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_get", lambda url: ARTICLE_XML)
    art = c.get_law_article(mst="264617")
    found = art.find_article("제74조")
    assert found is not None
    assert found["title"] == "임산부의 보호"
    assert art.find_article("제99조") is None


def test_get_law_article_requires_mst_or_name():
    c = _client()
    with pytest.raises(LawApiError):
        c.get_law_article()


# === _http_get: urlopen mock + HTTPError 분기 ===


def test_http_get_success(monkeypatch):
    c = _client()
    bridge.reset_breakers()

    class _Resp:
        headers = type("H", (), {"get_content_charset": lambda self: "utf-8"})()
        def read(self): return "<ok/>".encode("utf-8")
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _Resp())
    assert c._http_get("https://x") == "<ok/>"


def test_http_get_4xx_permanent(monkeypatch):
    c = _client()
    bridge.reset_breakers()

    def _boom(req, timeout=None):
        raise urllib.error.HTTPError("u", 400, "Bad", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(LawApiPermanentError):
        c._http_get("https://x")


def test_http_get_5xx_retried_then_error(monkeypatch):
    c = _client()
    bridge.reset_breakers()

    def _boom(req, timeout=None):
        raise urllib.error.HTTPError("u", 503, "Down", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(LawApiError):
        c._http_get("https://x")


def test_http_get_urlerror(monkeypatch):
    c = _client()
    bridge.reset_breakers()

    def _boom(req, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(LawApiError):
        c._http_get("https://x")


# === diagnose ===


def test_diagnose_disabled():
    c = _client(key="")
    info = c.diagnose()
    assert info["enabled"] is False
    assert "disabled" in info["status"]


def test_diagnose_ok(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_get", lambda url: SEARCH_XML)
    info = c.diagnose()
    assert info["status"] == "OK"
    assert info["sample_law"] == "근로기준법"


def test_diagnose_error(monkeypatch):
    c = _client()
    def _boom(url):
        raise LawApiError("boom")
    monkeypatch.setattr(c, "_http_get", _boom)
    info = c.diagnose()
    assert "error" in info["status"]
