"""legalize_kr_client — legalize-kr 저장소 (한국 법령 Git 저장소) 통합.

저장소: https://github.com/legalize-kr/legalize-kr
구조: kr/{법령명(공백 제거)}/법률.md, 시행령.md, 시행규칙.md

자람법 시드의 law_id → legalize-kr 경로 매핑 + frontmatter 파싱 + 본문 검색.
read-only 참조 (legalize-kr 자체 git 관리).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .config import Config


# === 자람법 law_id → legalize-kr 경로 매핑 ===
# 시드의 law_id가 legalize-kr 디렉토리/파일과 매칭되는 표

LAW_ID_TO_LEGALIZE_PATH: dict[str, tuple[str, str]] = {
    "labor-standards-74": ("근로기준법", "법률.md"),
    "labor-standards-74-2": ("근로기준법", "법률.md"),
    # 남녀고용평등법은 ㆍ(중점) 포함
    "equal-employment-18-2": ("남녀고용평등과일ㆍ가정양립지원에관한법률", "법률.md"),
    "equal-employment-19": ("남녀고용평등과일ㆍ가정양립지원에관한법률", "법률.md"),
    "equal-employment-22-2": ("남녀고용평등과일ㆍ가정양립지원에관한법률", "법률.md"),
    "equal-employment-37": ("남녀고용평등과일ㆍ가정양립지원에관한법률", "법률.md"),
    "childcare-33-3": ("영유아보육법", "법률.md"),
    "childcare-15-5": ("영유아보육법", "법률.md"),
    "childcare-34": ("영유아보육법", "법률.md"),
    "academy-decree-18": ("학원의설립ㆍ운영및과외교습에관한법률", "시행령.md"),
    "school-violence-12-17": ("학교폭력예방및대책에관한법률", "법률.md"),
    "child-welfare-3": ("아동복지법", "법률.md"),
    "child-abuse-10": ("아동학대범죄의처벌등에관한특례법", "법률.md"),
    "itnet-31": ("정보통신망이용촉진및정보보호등에관한법률", "법률.md"),
    "child-support-enforcement": ("양육비이행확보및지원에관한법률", "법률.md"),
    "single-parent": ("한부모가족지원법", "법률.md"),
    "child-allowance-4": ("아동수당법", "법률.md"),
    "maternal-health": ("모자보건법", "법률.md"),
    "infectious-disease-24": ("감염병의예방및관리에관한법률", "법률.md"),
    "low-birth-rate-act": ("저출산ㆍ고령사회기본법", "법률.md"),
    "civil-law-custody": ("민법", "법률.md"),
    "employment-insurance-parental-benefit": ("고용보험법", "법률.md"),
    "youth-protection": ("청소년보호법", "법률.md"),
    "elementary-secondary-education": ("초ㆍ중등교육법", "법률.md"),
}


@dataclass
class LegalizeKrArticle:
    """legalize-kr에서 로드한 법령 + 프론트매터."""

    law_name: str
    file_path: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body_full: str = ""
    article_excerpt: Optional[str] = None  # 특정 조문 일부만 추출한 경우

    @property
    def effective_date_iso(self) -> str:
        d = self.frontmatter.get("시행일자") or self.frontmatter.get("공포일자")
        return str(d) if d else ""

    @property
    def source_url(self) -> str:
        u = self.frontmatter.get("출처")
        return u if u else ""

    @property
    def title(self) -> str:
        return self.frontmatter.get("제목") or self.law_name


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """YAML frontmatter 파싱 — `---\\n...\\n---\\n<body>`."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    body = m.group(2)
    return fm, body


class LegalizeKrClient:
    """legalize-kr 저장소 클라이언트."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self.root = self.config.legalize_kr_path
        self.kr_dir = self.root / "kr"

    def available(self) -> bool:
        return self.kr_dir.exists()

    def _pick_current_law_file(self, dir_path: Path, base_name: str) -> Optional[Path]:
        """충돌 해소 파일 `법률(법률).md` 가 있으면 우선, 없으면 base.

        legalize-kr는 동일 경로에 여러 `법령ID`가 매핑되면 `법률(법률).md` 같은 형식을 쓰며,
        대개 disambiguated 파일이 현행 (newer 시행일자). 두 파일이 모두 있으면 시행일자 비교.
        """
        candidates = []
        stem, ext = base_name.rsplit(".", 1)
        # 기본 파일
        base = dir_path / base_name
        if base.exists():
            candidates.append(base)
        # 충돌 해소 파일 (예: 법률(법률).md, 법률(대통령령).md 등)
        for p in dir_path.glob(f"{stem}(*).{ext}"):
            candidates.append(p)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        # 시행일자 최신 우선
        def _enforce_date(p: Path) -> str:
            try:
                fm, _ = _parse_frontmatter(p.read_text(encoding="utf-8"))
                return str(fm.get("시행일자", ""))
            except Exception:
                return ""
        candidates.sort(key=_enforce_date, reverse=True)
        return candidates[0]

    def get_article(self, law_id: str) -> Optional[LegalizeKrArticle]:
        """자람법 law_id → legalize-kr 본문 로드 (현행본 자동 선택)."""
        mapping = LAW_ID_TO_LEGALIZE_PATH.get(law_id)
        if not mapping:
            return None
        dir_name, file_name = mapping
        dir_path = self.kr_dir / dir_name
        if not dir_path.exists():
            return None
        chosen = self._pick_current_law_file(dir_path, file_name)
        if not chosen or not chosen.exists():
            return None
        text = chosen.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text)
        return LegalizeKrArticle(
            law_name=dir_name,
            file_path=str(chosen.relative_to(self.root)),
            frontmatter=fm,
            body_full=body,
        )

    def extract_article_section(self, law_id: str, article_no: str) -> Optional[LegalizeKrArticle]:
        """특정 조문 추출. article_no 예: '제74조', '제74조의2', '제33조의3'."""
        full = self.get_article(law_id)
        if not full:
            return None
        # legalize-kr 마크다운은 `##### 제N조` 또는 `##### 제N조의M` 패턴
        # 다음 같은 레벨 헤더까지 추출
        pattern = re.compile(
            rf"^#{{1,6}}\s*{re.escape(article_no)}(\b|[^조])(.*?)(?=^#{{1,6}}\s*제\d+조|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(full.body_full)
        if not m:
            return full  # 조문 못 찾으면 전체 body 반환
        excerpt = m.group(0).strip()
        full.article_excerpt = excerpt
        return full

    def search_full_text(self, keyword: str, max_results: int = 10) -> list[LegalizeKrArticle]:
        """전 법령 본문 keyword 검색. grep 패턴.

        주의: 5673 파일 grep은 느릴 수 있음. 우선 시드 매핑된 법령만 검색.
        """
        results: list[LegalizeKrArticle] = []
        for law_id, (dir_name, file_name) in LAW_ID_TO_LEGALIZE_PATH.items():
            path = self.kr_dir / dir_name / file_name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if keyword in text:
                fm, body = _parse_frontmatter(text)
                # 키워드 주변 컨텍스트 (앞뒤 100자)
                idx = body.find(keyword)
                if idx >= 0:
                    start = max(0, idx - 100)
                    end = min(len(body), idx + len(keyword) + 200)
                    excerpt = body[start:end]
                else:
                    excerpt = None
                results.append(LegalizeKrArticle(
                    law_name=dir_name, file_path=str(path.relative_to(self.root)),
                    frontmatter=fm, body_full=body, article_excerpt=excerpt,
                ))
                if len(results) >= max_results:
                    break
        return results

    def list_mapped_laws(self) -> list[tuple[str, str, bool]]:
        """매핑된 법령 + 실제 존재 여부 진단 (현행본 자동 검색)."""
        out = []
        for law_id, (dir_name, file_name) in LAW_ID_TO_LEGALIZE_PATH.items():
            dir_path = self.kr_dir / dir_name
            chosen = self._pick_current_law_file(dir_path, file_name) if dir_path.exists() else None
            if chosen:
                out.append((law_id, str(chosen.relative_to(self.root)), True))
            else:
                out.append((law_id, f"{dir_name}/{file_name}", False))
        return out
