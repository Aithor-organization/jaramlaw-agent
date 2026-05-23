"""law_retrieval — 법령 시드 yaml 로드 + Hybrid retrieval (tag + BM25-lite).

(F4 분쟁 자가진단 핵심 모듈). LAW.OS LawApiClient 인터페이스 stub 포함.
seeded mode가 기본 (API 키 없이 동작).
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import yaml

from .models import FamilyProfile, LawArticle


DEFAULT_SEED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seed" / "laws"


def load_all_laws(seed_dir: Optional[Path] = None) -> list[LawArticle]:
    """시드 yaml 디렉토리에서 LawArticle 전체 로드."""
    seed_dir = seed_dir or DEFAULT_SEED_DIR
    laws: list[LawArticle] = []
    if not seed_dir.exists():
        return laws
    for f in sorted(seed_dir.glob("*.yaml")):
        with f.open("r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
        # 알려진 필드만 추려서 LawArticle 생성 (안전한 deserialize)
        allowed = set(LawArticle.__dataclass_fields__.keys())
        clean = {k: v for k, v in data.items() if k in allowed}
        # 기본값 보강
        clean.setdefault("text_summary", "")
        clean.setdefault("title", "")
        laws.append(LawArticle(**clean))
    return laws


def _tokenize_korean(text: str) -> list[str]:
    """간이 한글 토크나이저 — 공백/조사/구두점 기준 분리."""
    if not text:
        return []
    # 한글/숫자/영문 단어 추출, 길이 1초과만
    tokens = re.findall(r"[가-힣]{2,}|[A-Za-z0-9]+", text.lower())
    return tokens


def _bm25_lite_score(query_tokens: list[str], doc_tokens: list[str], corpus_size: int = 24) -> float:
    """BM25 단순화 버전 — k1=1.5, b=0.75. corpus_size는 시드 법령 수 어림."""
    if not query_tokens or not doc_tokens:
        return 0.0
    k1, b = 1.5, 0.75
    doc_len = len(doc_tokens)
    avgdl = 50.0  # 시드 평균 문서 길이 어림
    term_freq: dict[str, int] = {}
    for t in doc_tokens:
        term_freq[t] = term_freq.get(t, 0) + 1
    score = 0.0
    for q in query_tokens:
        tf = term_freq.get(q, 0)
        if tf == 0:
            continue
        # n_q는 알 수 없으므로 IDF는 corpus_size 기반 어림 (모든 term이 흔하지 않다고 가정)
        idf = math.log((corpus_size + 0.5) / 1.5 + 1.0)
        num = tf * (k1 + 1)
        den = tf + k1 * (1 - b + b * doc_len / avgdl)
        score += idf * num / den
    return score


def retrieve_matched_laws(
    family_profile: FamilyProfile,
    scenario_query: str = "",
    persona_hint: Optional[str] = None,
    top_k: int = 10,
    seed_dir: Optional[Path] = None,
) -> list[LawArticle]:
    """Hybrid retrieval: tag matching + BM25-lite + RRF.

    1. tag matching: family_flags ∩ applies_to_personas + life_stages ∩ applies_to_life_stages
    2. BM25-lite: scenario_query vs text_summary
    3. RRF (Reciprocal Rank Fusion) — k=60
    """
    laws = load_all_laws(seed_dir)
    if not laws:
        return []

    # 페르소나 hint 자동 추론 (시나리오 fixture에서 persona 필드 사용)
    persona_tokens = set()
    if persona_hint:
        persona_tokens.add(persona_hint)
    # family_profile의 parent role을 페르소나 토큰화
    for p in family_profile.parents:
        persona_tokens.add(f"P{persona_hint.split('-')[0][-1] if persona_hint else '0'}-{p.role}")
    # 단순화: persona_hint 자체와 그 -mother/-father 변형도 추가
    if persona_hint:
        # "P1" -> ["P1", "P1-mother", "P1-father"]
        for role in ("mother", "father"):
            persona_tokens.add(f"{persona_hint}-{role}")

    query_tokens = _tokenize_korean(scenario_query)

    # 시나리오 키워드를 페르소나 hint에 통합 (예: "학원 환불" → 학원법 시드 매칭 강화)
    extra_tags_from_query = set()
    if "환불" in scenario_query or "학원" in scenario_query:
        extra_tags_from_query.add("academy")
    if "출산휴가" in scenario_query or "임신" in scenario_query or "둘째" in scenario_query:
        extra_tags_from_query.update(["maternity", "출산휴가", "pregnancy"])
    if "육아휴직" in scenario_query:
        extra_tags_from_query.update(["parental-leave", "육아휴직"])
    if "어린이집" in scenario_query and ("사고" in scenario_query or "다쳤" in scenario_query or "멍" in scenario_query):
        extra_tags_from_query.update(["daycare", "safety", "accident-report", "cctv"])
    if "학교폭력" in scenario_query or "학폭" in scenario_query:
        extra_tags_from_query.add("school-violence")
    if "양육비" in scenario_query:
        extra_tags_from_query.add("child-support")

    # tag scoring
    tag_scored: list[tuple[LawArticle, float, list[str]]] = []
    for law in laws:
        reasons: list[str] = []
        score = 0.0

        # persona 매칭
        if any(p in law.applies_to_personas for p in persona_tokens):
            score += 2.0
            reasons.append(f"persona match: {[p for p in persona_tokens if p in law.applies_to_personas]}")

        # life stage 매칭
        stage_overlap = set(family_profile.life_stages) & set(law.applies_to_life_stages)
        if stage_overlap or "all" in law.applies_to_life_stages:
            score += 1.5
            if stage_overlap:
                reasons.append(f"life stage match: {sorted(stage_overlap)}")
            else:
                reasons.append("applies to all stages")

        # tag 매칭 (시나리오 기반 추출)
        tag_overlap = set(law.tags) & extra_tags_from_query
        if tag_overlap:
            score += 1.5 * len(tag_overlap)
            reasons.append(f"scenario tag match: {sorted(tag_overlap)}")

        # family flag → tag 매핑
        if "single_parent" in family_profile.flags and "single-parent" in law.tags:
            score += 2.0
            reasons.append("single_parent match")
        if "second_child_pregnancy" in family_profile.flags and "pregnancy" in law.tags:
            score += 1.0
            reasons.append("second_child_pregnancy match")

        tag_scored.append((law, score, reasons))

    # BM25 scoring
    bm25_scored: list[tuple[LawArticle, float]] = []
    corpus_size = len(laws)
    for law in laws:
        doc_tokens = _tokenize_korean(
            law.text_summary + " " + law.title + " " + " ".join(law.tags)
        )
        score = _bm25_lite_score(query_tokens, doc_tokens, corpus_size)
        bm25_scored.append((law, score))

    # RRF — k=60
    rrf_k = 60
    tag_ranking = {id(t[0]): rank for rank, t in enumerate(sorted(tag_scored, key=lambda x: -x[1]), start=1)}
    bm25_ranking = {id(t[0]): rank for rank, t in enumerate(sorted(bm25_scored, key=lambda x: -x[1]), start=1)}

    rrf_scored = []
    for law, tag_score, reasons in tag_scored:
        tag_rank = tag_ranking[id(law)]
        bm25_rank = bm25_ranking[id(law)]
        rrf_score = 1.0 / (rrf_k + tag_rank) + 1.0 / (rrf_k + bm25_rank)
        # tag_score 자체도 가중치 추가 (페르소나 매칭은 강함)
        final = rrf_score * 1000 + tag_score
        # tag matching이 0이면 RRF만으로 부족 — 강하게 다운위트
        if tag_score == 0.0 and rrf_score > 0:
            final *= 0.1
        if tag_score > 0 or any(qt in (law.text_summary.lower() + " ".join(law.tags).lower()) for qt in query_tokens):
            law.relevance_score = round(final, 4)
            law.applies_reason = reasons
            rrf_scored.append((law, final))

    # 정렬 + top-K
    rrf_scored.sort(key=lambda x: -x[1])
    return [law for law, _ in rrf_scored[:top_k]]


# === LAW.OS LawApiClient 인터페이스 stub (외부 API) ===


class LawApiClient:
    """LAW.OS law.go.kr 인터페이스 stub.

    환경변수 LAW_API_KEY 설정 시 실제 API 호출 (MVP 미구현).
    미설정 시 seeded mode — 시드 파일만 사용.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("LAW_API_KEY", "")
        self.seeded = not bool(self.api_key)

    def search_current_laws(self, query: str, filters: Optional[dict] = None) -> list[LawArticle]:
        if self.seeded:
            # 시드에서 직접 조회
            laws = load_all_laws()
            q_tokens = _tokenize_korean(query)
            return [
                law for law in laws
                if any(t in (law.text_summary.lower() + " ".join(law.tags).lower()) for t in q_tokens)
            ]
        # MVP 미구현 — 실제 API 호출은 후속
        raise NotImplementedError("LawApiClient remote mode not implemented in MVP")

    def get_current_law_article(self, law_id: str, article_no: Optional[str] = None) -> Optional[LawArticle]:
        if self.seeded:
            for law in load_all_laws():
                if law.law_id == law_id:
                    return law
            return None
        raise NotImplementedError("LawApiClient remote mode not implemented in MVP")
