"""openai_client — OpenAI Chat Completions API (stdlib).

Constitution 5원칙 강제:
  - 원칙 1: system prompt에 disclaimer + 법률 자문 거부 명시
  - 원칙 2: citation-required — retrieve된 법령 컨텍스트만 인용 허용
  - 원칙 4: 외부 발사 동작 X — read-only LLM 호출만

stdlib urllib만 사용 — openai-python 의존 X.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from . import DISCLAIMER
from .config import Config, redact_secret
from .models import LawArticle


SYSTEM_PROMPT = (
    "당신은 '자람법(JaramLaw)' 가족 라이프스테이지 법령·정책 AI 동반자다. "
    "한국 가정의 부모를 위해 양육 관련 법령 정보와 정부 지원을 안내한다.\n\n"

    "절대 규칙 (위반 시 응답 거부):\n"
    "1. 변호사법 회피 — 구체 사건의 승소 가능성·소송 전략·법률문서 대리 작성을 답하지 않는다. "
    "본 응답은 법률 자문이 아니다.\n"
    "2. Citation Required — 응답에 인용하는 법령은 반드시 사용자에게 제공된 컨텍스트의 법령만 인용한다. "
    "컨텍스트에 없는 법령은 '확실하지 않음. 법제처(law.go.kr) 또는 전문가 상담 권장'으로 답한다.\n"
    "3. Safety-First — 학대/응급/자해/가정폭력 신호가 있으면 일반 답변 대신 긴급 연락처를 안내한다:\n"
    "   - 아동학대 의심: 1577-1391 / 112\n"
    "   - 의료 응급: 119\n"
    "   - 자해/자살: 1393\n"
    "   - 가정폭력: 1366\n"
    "4. 자동 신고 발사 금지 — 신고서·신청서는 '초안'임을 명시한다.\n"
    "5. 미성년 PII — 아이 실명·주민번호 노출 금지.\n\n"

    "응답 형식:\n"
    "- 한국어로 답한다.\n"
    "- 인용 시 [법령명 제○조] 형식 + 시행일자.\n"
    "- 가능한 한 부모가 즉시 행동 가능한 step을 제시한다.\n"
    "- 응답 끝에 반드시 다음 한 줄 포함: '※ 본 서비스는 양육 정보 보조 도구이며, 구체 사안에 대한 법률 자문이 아닙니다.'\n"
)


@dataclass
class LlmAnswer:
    """LLM 응답 + 메타데이터."""

    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: Optional[str] = None
    citations: list[str] = field(default_factory=list)
    safety_flag: bool = False


class OpenAiError(RuntimeError):
    pass


class OpenAiClient:
    """OpenAI Chat Completions 클라이언트 (stdlib)."""

    DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"

    def __init__(self, config: Optional[Config] = None, timeout: float = 30.0, endpoint: Optional[str] = None):
        self.config = config or Config.from_env()
        self.timeout = timeout
        self.endpoint = endpoint or self.DEFAULT_ENDPOINT
        self.model = self.config.openai_model

    def enabled(self) -> bool:
        return bool(self.config.openai_api_key)

    def _http_post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled():
            raise OpenAiError("OPENAI_API_KEY not set")
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.openai_api_key}",
                "User-Agent": "jaramlaw-agent/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise OpenAiError(f"HTTP {exc.code}: {err_body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise OpenAiError(f"Network error: {exc}") from exc

    def _build_context_block(self, matched_laws: list[LawArticle]) -> str:
        """retrieve된 법령을 LLM context로 직렬화. citation 강제용."""
        if not matched_laws:
            return "(컨텍스트 법령 없음 — 법령 인용 시 '확실하지 않음' 응답 의무)"
        lines = ["## 적용 가능 법령 (컨텍스트 — 이 목록 외 인용 금지)\n"]
        for i, law in enumerate(matched_laws[:8], 1):
            lines.append(f"### {i}. {law.law_name} {law.article} ({law.title})")
            lines.append(f"- 시행일자: {law.effective_date}")
            lines.append(f"- 출처: {law.source_url}")
            lines.append(f"- 요약: {law.text_summary.strip()[:300]}")
            if law.violation_penalty:
                lines.append(f"- 위반 시: {law.violation_penalty.get('penalty', '')} / 신고처: {law.violation_penalty.get('report_channel', '')}")
            lines.append("")
        return "\n".join(lines)

    def ask(
        self,
        user_question: str,
        matched_laws: Optional[list[LawArticle]] = None,
        family_context_summary: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LlmAnswer:
        """사용자 질문 + 매칭 법령 컨텍스트 → LLM 답변.

        Constitution 원칙 2 강제: matched_laws 컨텍스트 외 법령 인용 금지.
        """
        if not self.enabled():
            return LlmAnswer(text="(LLM disabled — OPENAI_API_KEY 미설정)", model=self.model, error="not_configured")

        context_block = self._build_context_block(matched_laws or [])
        family_block = f"\n## 가족 정보 (요약, PII 마스킹됨)\n{family_context_summary}\n" if family_context_summary else ""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"{context_block}\n{family_block}\n## 사용자 질문\n{user_question}\n\n위 컨텍스트만 인용하여 답하라. 컨텍스트 외 법령은 '확실하지 않음' 답."
            },
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = self._http_post_json(payload)
        except OpenAiError as exc:
            return LlmAnswer(text="(LLM 호출 실패)", model=self.model, error=str(exc))

        choices = resp.get("choices", [])
        if not choices:
            return LlmAnswer(text="(empty choices)", model=self.model, error="empty_response")
        text = choices[0].get("message", {}).get("content", "")
        usage = resp.get("usage", {})

        # disclaimer 자동 보강 (LLM이 누락한 경우)
        if "법률 자문" not in text:
            text = f"{text.rstrip()}\n\n{DISCLAIMER}"

        # citation 추출 (단순 패턴 — `[법령명 제○조]`)
        import re as _re
        citations = _re.findall(r"\[([^\]]+제\d+조[^\]]*)\]", text)

        # safety 키워드 감지 (응답 자체에 라우팅 안내가 있는지)
        safety_flag = any(c in text for c in ["1577-1391", "1393", "1366"])

        return LlmAnswer(
            text=text,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            citations=citations,
            safety_flag=safety_flag,
        )

    def diagnose(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "enabled": self.enabled(),
            "model": self.model,
            "api_key_masked": redact_secret(self.config.openai_api_key),
            "endpoint": self.endpoint,
        }
        if not self.enabled():
            info["status"] = "disabled (OPENAI_API_KEY unset)"
            return info
        # 짧은 ping
        try:
            test = self.ask(
                "한 단어로만: 정상이면 'OK' 출력",
                matched_laws=[],
                temperature=0.0,
                max_tokens=10,
            )
            if test.error:
                info["status"] = f"error: {test.error[:200]}"
            else:
                info["status"] = "OK"
                info["sample_response_head"] = test.text[:80]
                info["sample_tokens"] = test.total_tokens
        except Exception as exc:
            info["status"] = f"exception: {type(exc).__name__}: {exc}"
        return info
