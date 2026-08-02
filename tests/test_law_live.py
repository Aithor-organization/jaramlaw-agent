"""law_live — LiveLawEnricher 3단 폴백 (live/cache/local/seed).

API 키 없이 cache_dir을 tmp로 잡고, live 경로는 _fetch_live/client mock으로 커버.
"""

from __future__ import annotations

import json

import pytest

from jaramlaw_agent.config import Config
from jaramlaw_agent.law_live import LiveLawEnricher, LawSourceStatus, _iso_date
from jaramlaw_agent.models import LawArticle


def _law(article="제74조", law_name="근로기준법", law_id="labor-standards-74"):
    return LawArticle(
        law_id=law_id,
        law_name=law_name,
        article=article,
        title="임산부의 보호",
        text_summary="출산전후휴가",
        effective_date="20210101",
        source_url="https://law.go.kr/seed",
        source_mode="seed",
    )


def _enricher(tmp_path, key=""):
    cfg = Config(law_api_key=key, legalize_kr_path=tmp_path / "nope")
    return LiveLawEnricher(config=cfg, cache_dir=tmp_path / "cache", total_budget_s=2.0)


# === _iso_date ===


@pytest.mark.parametrize("raw,expected", [
    ("20251023", "2025-10-23"),
    ("2025-10-23", "2025-10-23"),
    ("", ""),
    (None, ""),
])
def test_iso_date(raw, expected):
    assert _iso_date(raw) == expected


# === enrich: empty / seed ===


def test_enrich_empty(tmp_path):
    e = _enricher(tmp_path)
    status = e.enrich([])
    assert status.mode == "seed"
    assert status.degraded is True


def test_enrich_no_key_falls_to_seed(tmp_path):
    e = _enricher(tmp_path, key="")
    laws = [_law()]
    status = e.enrich(laws)
    assert status.mode == "seed"
    assert "LAW_API_KEY 미설정" in " ".join(status.errors)
    assert laws[0].source_mode == "seed"


# === enrich: live path (mock _fetch_live) ===


def test_enrich_live_path(tmp_path, monkeypatch):
    e = _enricher(tmp_path, key="testkey")
    monkeypatch.setattr(e.client, "enabled", lambda: True)

    payload = {
        "law_name": "근로기준법",
        "mst": "264617",
        "effective_date": "20210701",
        "department": "고용노동부",
        "articles": [{"article": "74", "title": "임산부의 보호", "text": "출산 전후 휴가 90일", "effective_date": "20210701"}],
        "fetched_at": "2026-01-01T00:00:00Z",
    }
    monkeypatch.setattr(e, "_fetch_live", lambda name: payload)

    laws = [_law()]
    status = e.enrich(laws)
    assert status.mode == "live"
    assert status.live_count == 1
    assert laws[0].source_mode == "live"
    assert "출산 전후 휴가" in laws[0].official_text
    assert laws[0].effective_date == "2021-07-01"
    # 캐시 파일도 기록됐는지
    assert (tmp_path / "cache" / "근로기준법.json").exists()


# === enrich: cache fallback ===


def test_enrich_cache_fallback(tmp_path):
    e = _enricher(tmp_path, key="")  # 키 없음 → live 스킵
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    payload = {
        "law_name": "근로기준법", "mst": "264617", "effective_date": "20210701",
        "articles": [{"article": "74", "title": "임산부의 보호", "text": "캐시 원문", "effective_date": "20210701"}],
        "fetched_at": "",
    }
    (cache_dir / "근로기준법.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    laws = [_law()]
    status = e.enrich(laws)
    assert status.mode == "cache"
    assert status.cache_count == 1
    assert laws[0].source_mode == "cache"
    assert "캐시 원문" in laws[0].official_text


# === enrich: local (legalize-kr) fallback ===


def test_enrich_local_fallback(tmp_path):
    """키·캐시 없고 legalize-kr 로컬 코퍼스만 있으면 local 모드."""
    # 가짜 legalize-kr 저장소
    kr = tmp_path / "legalize" / "kr" / "근로기준법"
    kr.mkdir(parents=True)
    (kr / "법률.md").write_text(
        "---\n시행일자: 20210701\n---\n"
        "##### 제74조(임산부의 보호)\n출산 전후 휴가 90일 로컬 원문.\n",
        encoding="utf-8",
    )
    cfg = Config(law_api_key="", legalize_kr_path=tmp_path / "legalize")
    e = LiveLawEnricher(config=cfg, cache_dir=tmp_path / "cache", total_budget_s=2.0)

    laws = [_law()]
    status = e.enrich(laws)
    assert status.mode == "local"
    assert status.local_count == 1
    assert laws[0].source_mode == "local"
    assert "로컬 원문" in laws[0].official_text


# === _apply (static) ===


def test_apply_matches_article():
    law = _law()
    payload = {
        "law_name": "근로기준법", "mst": "1",
        "effective_date": "20210701",
        "articles": [{"article": "74", "text": "본문", "effective_date": "20210701"}],
    }
    hit = LiveLawEnricher._apply(law, payload, "live")
    assert hit is True
    assert law.official_text == "본문"
    assert law.source_mode == "live"


def test_apply_no_match():
    law = _law(article="제99조")
    payload = {"law_name": "근로기준법", "mst": "1", "effective_date": "20210701", "articles": []}
    hit = LiveLawEnricher._apply(law, payload, "live")
    assert hit is False
    assert law.source_mode == "live"  # mode는 여전히 적용


# === 캐시 read/write ===


def test_cache_read_missing(tmp_path):
    e = _enricher(tmp_path)
    assert e._read_cache("없는법") is None


def test_cache_write_and_read(tmp_path):
    e = _enricher(tmp_path)
    e._write_cache("테스트법", {"x": 1})
    assert e._read_cache("테스트법") == {"x": 1}


def test_cache_disabled(tmp_path):
    cfg = Config(law_api_key="")
    e = LiveLawEnricher(config=cfg, cache_dir=tmp_path / "c", use_cache=False)
    e._write_cache("법", {"x": 1})
    assert e._read_cache("법") is None
