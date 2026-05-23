"""law_api_client — 법제처 Open API 클라이언트.

엔드포인트:
  - http://www.law.go.kr/DRF/lawSearch.do  (법령 검색)
  - http://www.law.go.kr/DRF/lawService.do (법령 본문 조회)

파라미터:
  - OC: 신청 시 발급된 키 (이메일 ID 형태가 일반적이나 본 서비스는 단순 문자열)
  - target: 'law' / 'admrul' / 'prec' (법령/행정규칙/판례)
  - query: 검색어
  - type: 'XML' / 'JSON' / 'HTML'
  - display: 결과 수

stdlib (urllib + xml/json) 만 사용 — requests 의존 X.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import Config, redact_secret


@dataclass
class LawApiSearchResult:
    """법제처 lawSearch 결과 단일 entry."""

    law_name: str
    law_id: Optional[str] = None
    law_mst: Optional[str] = None
    promulgation_date: Optional[str] = None  # 공포일자
    effective_date: Optional[str] = None      # 시행일자
    department: Optional[str] = None
    law_category: Optional[str] = None  # 법령구분 (법률/대통령령/부령)
    detail_url: Optional[str] = None
    raw_xml: Optional[str] = None


@dataclass
class LawApiArticle:
    """lawService 본문 — 특정 법령 전체 또는 조문."""

    law_name: str
    law_id: Optional[str] = None
    effective_date: Optional[str] = None
    articles: list[dict[str, str]] = field(default_factory=list)
    raw_xml: Optional[str] = None


class LawApiError(RuntimeError):
    pass


class LawApiClient:
    """법제처 Open API 클라이언트.

    환경변수 LAW_API_KEY 없으면 disabled — 호출 시 LawApiError.
    """

    def __init__(self, config: Optional[Config] = None, timeout: float = 10.0):
        self.config = config or Config.from_env()
        self.timeout = timeout
        self.api_key = self.config.law_api_key
        self.base_url = self.config.law_api_base_url

    def enabled(self) -> bool:
        return bool(self.api_key)

    def _http_get(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "jaramlaw-agent/0.1"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace")

    def search_laws(self, query: str, display: int = 10, search_mode: int = 1) -> list[LawApiSearchResult]:
        """법령 검색 (lawSearch.do).

        Args:
            query: 검색어
            display: 결과 수
            search_mode: 1=법령명, 2=본문 검색
        """
        if not self.enabled():
            raise LawApiError("LAW_API_KEY not set")
        params = {
            "OC": self.api_key,
            "target": "law",
            "type": "XML",
            "query": query,
            "display": str(display),
            "search": str(search_mode),
        }
        url = f"{self.base_url}/DRF/lawSearch.do?" + urllib.parse.urlencode(params)
        xml_text = self._http_get(url)

        results: list[LawApiSearchResult] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise LawApiError(f"XML parse failed: {exc}\nResponse: {xml_text[:300]}") from exc

        # 다양한 응답 형식 대응 — <law> 또는 <Law> 요소
        for el in root.iter():
            tag = el.tag.lower()
            if tag in {"law"}:
                results.append(LawApiSearchResult(
                    law_name=(el.findtext("법령명한글") or el.findtext("법령명") or el.findtext("LawName") or "").strip(),
                    law_id=(el.findtext("법령일련번호") or el.findtext("LawID") or "").strip() or None,
                    law_mst=(el.findtext("법령MST") or el.findtext("LawMst") or "").strip() or None,
                    promulgation_date=(el.findtext("공포일자") or el.findtext("PromulgationDate") or "").strip() or None,
                    effective_date=(el.findtext("시행일자") or el.findtext("EffectiveDate") or "").strip() or None,
                    department=(el.findtext("소관부처명") or el.findtext("DeptName") or "").strip() or None,
                    law_category=(el.findtext("법령구분명") or "").strip() or None,
                    detail_url=(el.findtext("법령상세링크") or "").strip() or None,
                    raw_xml=ET.tostring(el, encoding="unicode"),
                ))
        return results

    def get_law_article(self, mst: Optional[str] = None, law_name: Optional[str] = None) -> LawApiArticle:
        """법령 본문 조회 (lawService.do).

        mst 또는 law_name 중 하나 필요.
        """
        if not self.enabled():
            raise LawApiError("LAW_API_KEY not set")
        params = {
            "OC": self.api_key,
            "target": "law",
            "type": "XML",
        }
        if mst:
            params["MST"] = mst
        elif law_name:
            params["LM"] = law_name  # 법령명 (한글)
        else:
            raise LawApiError("mst 또는 law_name 중 하나 필수")
        url = f"{self.base_url}/DRF/lawService.do?" + urllib.parse.urlencode(params)
        xml_text = self._http_get(url)
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise LawApiError(f"XML parse failed: {exc}") from exc

        articles: list[dict[str, str]] = []
        for art in root.iter():
            tag = art.tag.lower()
            if tag == "조문단위" or tag == "article" or tag == "조문":
                articles.append({
                    "article": (art.findtext("조문번호") or art.findtext("ArticleNo") or "").strip(),
                    "title": (art.findtext("조문제목") or "").strip(),
                    "text": (art.findtext("조문내용") or art.findtext("ArticleContent") or "").strip(),
                })

        return LawApiArticle(
            law_name=(root.findtext("법령명한글") or law_name or "").strip(),
            law_id=(root.findtext("법령일련번호") or "").strip() or None,
            effective_date=(root.findtext("시행일자") or "").strip() or None,
            articles=articles,
            raw_xml=xml_text[:5000],  # 디버깅용 일부
        )

    def diagnose(self) -> dict[str, Any]:
        """진단 — API 키 마스킹 + 단순 호출 확인."""
        info: dict[str, Any] = {
            "enabled": self.enabled(),
            "api_key_masked": redact_secret(self.api_key, keep_head=4, keep_tail=2),
            "base_url": self.base_url,
        }
        if not self.enabled():
            info["status"] = "disabled (LAW_API_KEY unset)"
            return info
        try:
            res = self.search_laws("근로기준법", display=1)
            info["status"] = "OK"
            info["sample_count"] = len(res)
            if res:
                info["sample_law"] = res[0].law_name
        except Exception as exc:
            info["status"] = f"error: {type(exc).__name__}: {exc}"
        return info
