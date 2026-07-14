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
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Optional

from .agentshield_bridge import resilient_call
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

    def find_article(self, article_no: str) -> Optional[dict[str, str]]:
        """'제74조' / '74' 어느 표기로도 조문 1건 조회."""
        wanted = _normalize_article_no(article_no)
        if not wanted:
            return None
        for art in self.articles:
            if _normalize_article_no(art.get("article", "")) == wanted:
                return art
        return None


def _normalize_article_no(raw: str) -> str:
    """'제74조의2' / '74' / '제74조' → '74' (가지번호는 '74-2')."""
    if not raw:
        return ""
    text = raw.strip()
    m = re.search(r"(\d+)\s*조(?:\s*의\s*(\d+))?", text)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}" if m.group(2) else str(int(m.group(1)))
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", text)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}" if m.group(2) else str(int(m.group(1)))
    return text


def build_source_url(law_name: str, mst: Optional[str] = None, article_no: Optional[str] = None) -> str:
    """국가법령정보센터 원문 주소 (인용 4요소의 source_url)."""
    if mst:
        url = f"https://www.law.go.kr/DRF/lawService.do?target=law&type=HTML&MST={mst}"
        if article_no:
            norm = _normalize_article_no(article_no)
            if norm:
                # JO는 6자리: 조번호 4자리 + 가지번호 2자리 (제18조의2 → 001802)
                main, _, sub = norm.partition("-")
                if main.isdigit():
                    url += f"&JO={int(main):04d}{int(sub or 0):02d}"
        return url
    return "https://www.law.go.kr/법령/" + urllib.parse.quote(law_name or "")


class LawApiError(RuntimeError):
    pass


class LawApiAuthError(LawApiError):
    """OC 키 미등록 / 호출 IP 미등록 — 무대에서 조용히 빈 결과로 보이면 안 되므로 별도 예외."""


class LawApiPermanentError(LawApiError):
    """재시도해도 소용없는 응답 (4xx, 429 제외). 재시도 대상에서 제외한다."""


def _raise_if_error(root: ET.Element, xml_text: str) -> None:
    """법제처는 인증 실패 시에도 HTTP 200 + <Response><result>...를 준다.

    이걸 잡지 않으면 '결과 0건'과 '인증 실패'가 구분되지 않는다.
    """
    if root.tag == "Response":
        result = (root.findtext("result") or "").strip()
        msg = (root.findtext("msg") or "").strip()
        raise LawApiAuthError(f"{result} {msg}".strip() or xml_text[:200])
    code = (root.findtext("resultCode") or "").strip()
    if code and code != "00":
        raise LawApiError(f"resultCode={code} {(root.findtext('resultMsg') or '').strip()}")


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

        def _send() -> str:
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read()
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return data.decode(charset, errors="replace")
            except urllib.error.HTTPError as exc:
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise LawApiPermanentError(f"HTTP {exc.code}") from exc
                raise LawApiError(f"HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise LawApiError(f"Network error: {exc}") from exc

        # 재시도는 2회까지만 — LiveLawEnricher의 총 예산(기본 12초)을 넘기면 안 된다.
        # (호출당 5초 × 2회 + 백오프 0.2초 ≈ 10.2초.) 법제처가 연속으로 죽으면 회로를
        # 열어, 15개 법령을 각각 5초씩 기다리는 대신 즉시 시드로 떨어진다.
        return resilient_call(
            "law_api",
            _send,
            max_attempts=2,
            retry_on=(LawApiError,),
            no_retry_on=(LawApiPermanentError,),
        )

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

        _raise_if_error(root, xml_text)

        # 다양한 응답 형식 대응 — <law> 또는 <Law> 요소
        for el in root.iter():
            tag = el.tag.lower()
            if tag in {"law"}:
                # 법령일련번호(MST)가 lawService의 MST 파라미터. 법령ID는 별개 식별자다.
                mst = (el.findtext("법령일련번호") or "").strip() or None
                law_name = (el.findtext("법령명한글") or el.findtext("법령명") or el.findtext("LawName") or "").strip()
                detail = (el.findtext("법령상세링크") or "").strip()
                if detail.startswith("/"):
                    detail = "https://www.law.go.kr" + detail
                results.append(LawApiSearchResult(
                    law_name=law_name,
                    law_id=(el.findtext("법령ID") or el.findtext("LawID") or "").strip() or None,
                    law_mst=mst,
                    promulgation_date=(el.findtext("공포일자") or el.findtext("PromulgationDate") or "").strip() or None,
                    effective_date=(el.findtext("시행일자") or el.findtext("EffectiveDate") or "").strip() or None,
                    department=(el.findtext("소관부처명") or el.findtext("DeptName") or "").strip() or None,
                    law_category=(el.findtext("법령구분명") or "").strip() or None,
                    detail_url=detail or build_source_url(law_name, mst),
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

        _raise_if_error(root, xml_text)

        # 법령명/시행일자는 <기본정보> 하위에 있어 root.findtext()로는 안 잡힌다 (.// 필요).
        doc_effective = (root.findtext(".//시행일자") or "").strip() or None
        doc_name = (root.findtext(".//법령명_한글") or root.findtext(".//법령명한글") or law_name or "").strip()
        mst_found = (root.findtext(".//법령일련번호") or mst or "").strip() or None

        articles: list[dict[str, str]] = []
        for art in root.iter("조문단위"):
            # 조문여부='전문'은 장/절 제목("제3장의2 일·가정의 양립 지원")이라 조문이 아니다.
            # 이걸 걸러내지 않으면 장 번호가 조문번호로 잡혀 엉뚱한 본문이 인용된다.
            if (art.findtext("조문여부") or "").strip() not in ("", "조문"):
                continue
            # 조문내용은 제목줄("제74조(임산부의 보호)")만 담고, 실제 본문은 항/항내용에 있다.
            head = (art.findtext("조문내용") or "").strip()
            paragraphs = [(p.findtext("항내용") or "").strip() for p in art.iter("항")]
            body = "\n".join([head] + [p for p in paragraphs if p]).strip()
            article_no = (art.findtext("조문번호") or "").strip()
            sub_no = (art.findtext("조문가지번호") or "").strip()
            if sub_no:
                article_no = f"{article_no}-{sub_no}"
            articles.append({
                "article": article_no,
                "title": (art.findtext("조문제목") or "").strip(),
                "text": body,
                "effective_date": (art.findtext("조문시행일자") or "").strip() or (doc_effective or ""),
            })

        return LawApiArticle(
            law_name=doc_name,
            law_id=mst_found,
            effective_date=doc_effective,
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
