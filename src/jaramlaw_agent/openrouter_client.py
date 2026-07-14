"""OpenRouter 클라이언트 — 독립 비평가용 (stdlib urllib만).

답변을 쓰는 모델(OpenAI)과 **다른 회사의 모델**을 부르기 위해 존재한다.
같은 모델에게 자기 답변을 검토시키면 같은 착각을 두 번 한다.

기본 비평가는 `x-ai/grok-4.5`, 그가 죽으면 `anthropic/claude-sonnet-5`로 넘어간다.
둘 다 답변 생성자(OpenAI)와 다른 계열이라 교차 검증의 의미가 유지된다.

## 실패는 상담을 죽이지 않는다

비평가는 **부가 게이트**다. OpenRouter가 느리거나 죽었다고 부모의 상담이 실패하면
안 된다. 모든 실패는 여기서 잡아 `CritiqueUnavailable`로 바꾸고, 호출자는
"검증 못 함"을 사용자에게 정직하게 알리며 진행한다 (fail-open, 단 침묵 금지).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional


ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# 비평가 모델. 1차가 실패하면 순서대로 내려간다.
# 실존 확인 2026-07-14 (OpenRouter /models):
#   x-ai/grok-4.5           ctx 500k  · in $2/M  out $6/M
#   anthropic/claude-sonnet-5  ctx 1M · in $2/M  out $10/M
DEFAULT_CRITIC = os.environ.get("JARAMLAW_CRITIC_MODEL", "x-ai/grok-4.5")
FALLBACK_CRITIC = os.environ.get("JARAMLAW_CRITIC_FALLBACK", "anthropic/claude-sonnet-5")


class OpenRouterError(RuntimeError):
    pass


@dataclass
class CritiqueResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""
    fallback_used: bool = False
    error: Optional[str] = None
    attempts: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.error is None and bool(self.text.strip())


class OpenRouterClient:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 25.0) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.timeout = timeout

    def enabled(self) -> bool:
        return bool(self.api_key)

    def _post(self, model: str, messages: list[dict[str, str]], max_tokens: int) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.0,   # 비평은 창작이 아니다 — 같은 입력엔 같은 판단이 나와야 한다.
            # grok-4.5는 추론 모델이다. 추론을 끄면(`enabled: false`) 400이 나고,
            # 그대로 두면 입력이 커질수록 추론 토큰이 폭증해 39초까지 걸렸다 —
            # UI 예산(45초) 안에서 동기 게이트로 쓸 수 없는 속도다.
            # effort를 낮추면 4~10초로 떨어지고, 환각·승소단정 판정 정확도는 유지된다(실측).
            "reasoning": {"effort": "low"},
        }
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                # OpenRouter가 요구하는 식별 헤더 (없어도 동작하나 rate limit 우대).
                "HTTP-Referer": "https://github.com/jaramlaw",
                "X-Title": "JaramLaw independent critic",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OpenRouterError(f"HTTP {exc.code}: {body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise OpenRouterError(f"Network error: {exc}") from exc
        except (TimeoutError, OSError) as exc:
            raise OpenRouterError(f"Timeout/IO: {exc}") from exc

    def critique(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: Optional[str] = None,
        fallback: Optional[str] = None,
        max_tokens: int = 1200,
    ) -> CritiqueResponse:
        """비평가를 부른다. 1차 실패 시 폴백 모델로 한 번 더.

        어떤 예외도 밖으로 던지지 않는다 — 상담이 비평가 때문에 죽으면 안 된다.
        """
        primary = model or DEFAULT_CRITIC
        secondary = fallback if fallback is not None else FALLBACK_CRITIC

        if not self.enabled():
            return CritiqueResponse(text="", model=primary, error="no_api_key")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        attempts: list[str] = []
        last_error = ""
        candidates = [m for m in (primary, secondary) if m]
        for index, candidate in enumerate(candidates):
            attempts.append(candidate)
            try:
                data = self._post(candidate, messages, max_tokens)
            except OpenRouterError as exc:
                last_error = str(exc)
                continue

            choices = data.get("choices") or []
            if not choices:
                last_error = "empty_choices"
                continue
            text = (choices[0].get("message", {}) or {}).get("content") or ""
            if not text.strip():
                last_error = "empty_content"
                continue

            usage = data.get("usage") or {}
            return CritiqueResponse(
                text=text,
                model=data.get("model") or candidate,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                finish_reason=choices[0].get("finish_reason", ""),
                fallback_used=index > 0,
                attempts=attempts,
            )

        return CritiqueResponse(
            text="", model=primary, error=last_error or "unavailable", attempts=attempts
        )
