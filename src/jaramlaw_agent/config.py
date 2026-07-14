"""config — 환경변수 + .env 파일 로드.

stdlib만 사용 (python-dotenv 불필요). .env 파싱은 단순 line-by-line.

보안 원칙 (Constitution 원칙 5 확장):
- API key는 메모리 내 보유, 로그/audit log에 노출 X
- redacted_key() 메서드로 마스킹 처리
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _parse_dotenv_file(path: Path) -> dict[str, str]:
    """단순 .env 파싱 — KEY=VALUE 행만. 따옴표 제거."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip()
        # 따옴표 제거 ("..." 또는 '...')
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        out[k] = v
    return out


def load_dotenv(env_file: Optional[Path] = None, override: bool = False) -> dict[str, str]:
    """.env 파일을 os.environ에 로드."""
    env_file = env_file or (PROJECT_ROOT / ".env")
    parsed = _parse_dotenv_file(env_file)
    for k, v in parsed.items():
        if override or k not in os.environ:
            os.environ[k] = v
    return parsed


DEFAULT_LAW_API_BASE_URL = "https://www.law.go.kr"


def enforce_https(url: str, *, default: str = DEFAULT_LAW_API_BASE_URL) -> str:
    """법제처 base URL을 https로 강제한다.

    법제처 호출은 OC 키를 **쿼리스트링**에 실어 보낸다(law_api_client.search_laws).
    base URL이 http이면 그 키가 평문으로 네트워크를 지나간다 — 중간자·프록시 로그에
    그대로 남는다. 기본값이 http였고 .env.example도 http를 안내하고 있었다.

    운영자가 http를 넣어도 조용히 승격한다. 키를 지키는 쪽이 설정을 존중하는 쪽보다 낫다.
    """
    url = (url or "").strip() or default
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    if not url.startswith("https://"):
        return default
    return url


def redact_secret(s: Optional[str], keep_head: int = 6, keep_tail: int = 4) -> str:
    """API key 마스킹 — 보안 로깅용."""
    if not s:
        return "<unset>"
    if len(s) <= keep_head + keep_tail:
        return "***"
    return f"{s[:keep_head]}...{s[-keep_tail:]}"


@dataclass
class Config:
    """런타임 설정 — .env에서 로드된 값을 dataclass로 정리."""

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openrouter_api_key: Optional[str] = None
    law_api_key: Optional[str] = None
    law_api_base_url: str = DEFAULT_LAW_API_BASE_URL
    legalize_kr_path: Path = field(default_factory=lambda: PROJECT_ROOT / "external" / "legalize-kr")

    @classmethod
    def from_env(cls, load_file: bool = True) -> "Config":
        """env → Config. load_file=True면 .env 먼저 로드."""
        if load_file:
            load_dotenv()
        legalize_path_str = os.environ.get("LEGALIZE_KR_PATH", "./external/legalize-kr")
        legalize_path = Path(legalize_path_str)
        if not legalize_path.is_absolute():
            legalize_path = (PROJECT_ROOT / legalize_path).resolve()
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY") or None,
            law_api_key=os.environ.get("LAW_API_KEY") or None,
            law_api_base_url=enforce_https(os.environ.get("LAW_API_BASE_URL", DEFAULT_LAW_API_BASE_URL)),
            legalize_kr_path=legalize_path,
        )

    def summary(self) -> dict[str, str]:
        """마스킹된 설정 요약 (audit 안전)."""
        return {
            "openai_api_key": redact_secret(self.openai_api_key),
            "openai_model": self.openai_model,
            "openrouter_api_key": redact_secret(self.openrouter_api_key),
            "law_api_key": redact_secret(self.law_api_key, keep_head=4, keep_tail=2),
            "law_api_base_url": self.law_api_base_url,
            "legalize_kr_path": str(self.legalize_kr_path),
            "legalize_kr_exists": "yes" if self.legalize_kr_path.exists() else "no",
        }

    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    def has_law_api(self) -> bool:
        return bool(self.law_api_key)

    def has_legalize_kr(self) -> bool:
        return self.legalize_kr_path.exists() and (self.legalize_kr_path / "kr").exists()
