"""law_live — 시드로 매칭된 법령을 법제처 Open API 현행 데이터로 보강한다.

발표덱 시연 1의 근거: 상담 흐름에서 실제로 법제처를 호출해
조문 원문 / 시행일 / 출처주소를 확보하고, 그 인용만 화면에 내보낸다.

3단 폴백 (무대에서 절대 멈추면 안 되므로):
    live  — 법제처 Open API 실시간 호출
    cache — 과거 호출로 받아둔 실제 법제처 응답 (네트워크 없어도 '진짜 법령')
    local — legalize-kr 로컬 코퍼스 (현행 본문)
    seed  — 시드 YAML (최후)

시간 예산을 초과하면 남은 법령은 손대지 않고 그대로 둔다. 상담 응답 지연이
법령 보강보다 우선한다.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import Config
from .law_api_client import (
    LawApiArticle,
    LawApiAuthError,
    LawApiClient,
    LawApiError,
    build_source_url,
)
from .models import LawArticle

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "law_api"


def _iso_date(yyyymmdd: Optional[str]) -> str:
    """'20251023' → '2025-10-23'. 이미 ISO면 그대로."""
    if not yyyymmdd:
        return ""
    s = str(yyyymmdd).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


@dataclass
class LawSourceStatus:
    """이번 상담에서 법령 근거를 어디서 가져왔는지 — 화면에 그대로 노출된다."""

    mode: str = "seed"  # live | cache | local | seed
    live_count: int = 0
    cache_count: int = 0
    local_count: int = 0
    seed_count: int = 0
    checked_at: str = ""
    elapsed_ms: int = 0
    errors: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def degraded(self) -> bool:
        """라이브 호출이 하나도 성공하지 못한 상태 = 재현 모드."""
        return self.live_count == 0


class LiveLawEnricher:
    """매칭된 LawArticle 목록에 현행 조문/시행일/출처주소를 채워 넣는다."""

    def __init__(
        self,
        config: Optional[Config] = None,
        per_call_timeout: float = 5.0,
        total_budget_s: float = 12.0,
        max_laws: int = 8,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True,
    ) -> None:
        self.config = config or Config.from_env()
        self.client = LawApiClient(config=self.config, timeout=per_call_timeout)
        self.total_budget_s = total_budget_s
        self.max_laws = max_laws
        self.cache_dir = cache_dir or CACHE_DIR
        self.use_cache = use_cache
        self._legalize = None  # lazy — 로컬 코퍼스는 필요할 때만

    # ---------- 캐시 ----------

    def _cache_path(self, law_name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in law_name)[:120]
        return self.cache_dir / f"{safe}.json"

    def _read_cache(self, law_name: str) -> Optional[dict[str, Any]]:
        if not self.use_cache:
            return None
        p = self._cache_path(law_name)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, law_name: str, payload: dict[str, Any]) -> None:
        if not self.use_cache:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(law_name).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass  # 캐시 실패가 상담을 막아서는 안 된다

    # ---------- 원격 조회 ----------

    def _fetch_live(self, law_name: str) -> dict[str, Any]:
        """법제처에서 법령 1건의 전체 조문을 받아 캐시 가능한 dict로 변환."""
        hits = self.client.search_laws(law_name, display=5, search_mode=1)
        if not hits:
            raise LawApiError(f"법령명 검색 0건: {law_name}")
        exact = next((h for h in hits if h.law_name == law_name), hits[0])
        if not exact.law_mst:
            raise LawApiError(f"MST 없음: {exact.law_name}")
        doc: LawApiArticle = self.client.get_law_article(mst=exact.law_mst)
        return {
            "law_name": doc.law_name or exact.law_name,
            "mst": exact.law_mst,
            "effective_date": _iso_date(doc.effective_date or exact.effective_date),
            "department": exact.department,
            "articles": doc.articles,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def _legalize_client(self):
        if self._legalize is None:
            from .legalize_kr_client import LegalizeKrClient

            self._legalize = LegalizeKrClient(config=self.config)
        return self._legalize

    # ---------- 적용 ----------

    @staticmethod
    def _apply(law: LawArticle, payload: dict[str, Any], mode: str) -> bool:
        """payload에서 law.article에 해당하는 조문을 찾아 LawArticle에 반영."""
        from .law_api_client import _normalize_article_no

        wanted = _normalize_article_no(law.article)
        match = None
        for art in payload.get("articles", []):
            if _normalize_article_no(art.get("article", "")) == wanted:
                match = art
                break

        eff = _iso_date(payload.get("effective_date"))
        mst = payload.get("mst")

        if match:
            law.official_text = (match.get("text") or "").strip()
            eff = _iso_date(match.get("effective_date")) or eff
        if eff:
            law.effective_date = eff
        law.source_url = build_source_url(payload.get("law_name") or law.law_name, mst, law.article)
        law.source_mode = mode
        law.live_checked_at = payload.get("fetched_at", "")
        return match is not None

    def enrich(self, laws: list[LawArticle]) -> LawSourceStatus:
        """laws를 제자리에서 보강하고 출처 상태를 돌려준다. 예외를 밖으로 던지지 않는다."""
        status = LawSourceStatus(checked_at=datetime.now(timezone.utc).isoformat())
        started = time.monotonic()

        if not laws:
            status.mode = "seed"
            return status

        if not self.client.enabled():
            status.errors.append("LAW_API_KEY 미설정 — 시드 모드")

        # 같은 법령(법령명)에 속한 조문들은 한 번의 호출로 함께 처리된다.
        by_name: dict[str, list[LawArticle]] = {}
        for law in laws[: self.max_laws]:
            by_name.setdefault(law.law_name, []).append(law)

        # 법령별 호출은 서로 독립이라 병렬로 — 무대 대기시간을 줄인다.
        fetched: dict[str, dict[str, Any]] = {}
        if self.client.enabled():
            with ThreadPoolExecutor(max_workers=min(4, len(by_name) or 1)) as pool:
                futures = {pool.submit(self._fetch_live, name): name for name in by_name}
                try:
                    for fut in as_completed(futures, timeout=self.total_budget_s):
                        name = futures[fut]
                        try:
                            fetched[name] = fut.result()
                        except LawApiAuthError as exc:
                            status.errors.append(f"인증 실패({name}): {exc}")
                        except Exception as exc:  # noqa: BLE001 — 네트워크/파싱 전부 흡수
                            status.errors.append(f"{name}: {type(exc).__name__}: {exc}")
                except FuturesTimeout:
                    # 예산 초과 — 도착한 것만 쓰고 나머지는 캐시/시드로 간다
                    pending = [n for f, n in futures.items() if not f.done()]
                    status.errors.append(
                        f"시간 예산 {self.total_budget_s}s 초과 — 미완료 {len(pending)}건은 캐시/시드 사용"
                    )

        for law_name, group in by_name.items():
            payload: Optional[dict[str, Any]] = fetched.get(law_name)
            mode = "seed"

            if payload is not None:
                mode = "live"
                self._write_cache(law_name, payload)

            if payload is None:
                cached = self._read_cache(law_name)
                if cached:
                    payload, mode = cached, "cache"

            if payload is None:
                local = self._try_local(group)
                if local:
                    payload, mode = local, "local"

            if payload is None:
                for law in group:
                    law.source_mode = "seed"
                status.seed_count += len(group)
                continue

            for law in group:
                hit = self._apply(law, payload, mode)
                status.details.append({
                    "law": law.law_name,
                    "article": law.article,
                    "mode": mode,
                    "article_matched": hit,
                    "effective_date": law.effective_date,
                })
            count = len(group)
            if mode == "live":
                status.live_count += count
            elif mode == "cache":
                status.cache_count += count
            elif mode == "local":
                status.local_count += count

        # 손대지 않은 나머지(max_laws 초과분)는 시드 그대로
        status.seed_count += max(0, len(laws) - self.max_laws)

        if status.live_count:
            status.mode = "live"
        elif status.cache_count:
            status.mode = "cache"
        elif status.local_count:
            status.mode = "local"
        else:
            status.mode = "seed"

        status.elapsed_ms = int((time.monotonic() - started) * 1000)
        return status

    def _try_local(self, group: list[LawArticle]) -> Optional[dict[str, Any]]:
        """legalize-kr 로컬 코퍼스 폴백 — 네트워크 없이도 현행 조문 원문을 얻는다.

        legalize-kr은 자람법 law_id → 파일 매핑이라 법령명이 아니라 law_id로 찾는다.
        """
        try:
            client = self._legalize_client()
            if not client.available():
                return None
        except Exception:
            return None

        articles: list[dict[str, str]] = []
        effective = ""
        for law in group:
            try:
                found = client.extract_article_section(law.law_id, law.article)
            except Exception:
                found = None
            if not found:
                continue
            effective = effective or found.effective_date_iso
            articles.append({
                "article": law.article,
                "title": found.title,
                "text": (found.article_excerpt or "").strip(),
                "effective_date": found.effective_date_iso,
            })

        if not articles:
            return None
        return {
            "law_name": group[0].law_name,
            "mst": None,
            "effective_date": effective,
            "articles": articles,
            "fetched_at": "",
        }
