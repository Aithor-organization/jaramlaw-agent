"""openai_client — OpenAI Chat Completions API (stdlib).

Constitution 5원칙 강제:
  - 원칙 1: system prompt에 disclaimer + 법률 자문 거부 명시
  - 원칙 2: citation-required — retrieve된 법령 컨텍스트만 인용 허용
  - 원칙 4: 외부 발사 동작 X — read-only LLM 호출만

stdlib urllib만 사용 — openai-python 의존 X.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from . import DISCLAIMER
from .agentshield_bridge import resilient_call
from .config import Config, redact_secret
from .model_routing import select_model
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


# 답변 토큰 상한.
#
# 800이었는데, 학교폭력·CCTV 열람처럼 절차가 긴 질문에서 상한에 걸려
# 본문이 통째로 비어 돌아왔다 (finish_reason=length, content=""). 실측:
#   800  → finish_reason=length, 본문 없음, 인용 0건
#   2000 → finish_reason=stop,   1,125토큰 완결, 인용 4건
# 출력 토큰은 캐시가 안 되는 유일한 비용이라 무한정 올릴 수는 없지만,
# 답변이 아예 안 나오는 것보다는 비싼 게 낫다.
DEFAULT_ANSWER_MAX_TOKENS = 2000


@dataclass
class LlmAnswer:
    """LLM 응답 + 메타데이터."""

    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # OpenAI가 자동 재사용한 입력 토큰. 같은 법령 컨텍스트가 반복되면 여기에 잡힌다.
    # (실측: 같은 프롬프트 2회차부터 3,850/3,853 = 100% 히트)
    cached_tokens: int = 0
    finish_reason: str = ""
    truncated: bool = False
    error: Optional[str] = None
    citations: list[str] = field(default_factory=list)
    safety_flag: bool = False


class OpenAiError(RuntimeError):
    pass


class OpenAiPermanentError(OpenAiError):
    """재시도해도 같은 답이 오는 오류 (4xx, 429 제외).

    `_post_with_param_fallback`이 일부러 만들어내는 400(파라미터 불일치)이 여기 속한다.
    이걸 일반 오류와 구분하지 않으면 (1) 400을 3번씩 재시도해 폴백이 3배 느려지고,
    (2) 회로 차단기가 그 400들을 장애로 세어 OpenAI 호출 전체를 끊어버린다.
    """


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

        def _send() -> dict[str, Any]:
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read()
                    return json.loads(data)
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                msg = f"HTTP {exc.code}: {err_body[:500]}"
                # 4xx는 같은 요청을 다시 보내도 같은 답이 온다 (429 = 잠시 후 재시도는 의미 있음).
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise OpenAiPermanentError(msg) from exc
                raise OpenAiError(msg) from exc
            except urllib.error.URLError as exc:
                raise OpenAiError(f"Network error: {exc}") from exc

        # 일시적 네트워크 단절·5xx·429는 지수 백오프로 재시도한다. 이전에는 한 번 삐끗하면
        # 상담이 그대로 "LLM 호출 실패"로 끝났다. 연속 실패가 쌓이면 회로를 열어
        # 죽은 API를 매번 30초씩 기다리지 않는다.
        return resilient_call(
            "openai",
            _send,
            max_attempts=3,
            retry_on=(OpenAiError,),
            no_retry_on=(OpenAiPermanentError,),
        )

    # 모델별로 거부하는 파라미터가 다르다 (gpt-5.x: temperature 고정, max_tokens 불가).
    # 400 응답이 지목한 파라미터를 떼고 재시도한다 — 모델 목록을 하드코딩하지 않기 위함.
    _PARAM_ALIASES = {"max_tokens": "max_completion_tokens", "max_completion_tokens": "max_tokens"}

    def _post_with_param_fallback(self, payload: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        attempt = dict(payload)
        last: Optional[OpenAiError] = None
        for _ in range(max_retries):
            try:
                return self._http_post_json(attempt)
            except OpenAiError as exc:
                last = exc
                msg = str(exc)
                if "HTTP 400" not in msg:
                    raise
                bad = re.search(r"'([a-z_]+)' is not supported|Unsupported (?:parameter|value): '([a-z_]+)'", msg)
                param = None
                if bad:
                    param = bad.group(1) or bad.group(2)
                elif "temperature" in msg:
                    param = "temperature"
                if not param or param not in attempt:
                    raise
                alias = self._PARAM_ALIASES.get(param)
                value = attempt.pop(param)
                if alias and alias not in attempt:
                    attempt[alias] = value
        raise last or OpenAiError("param fallback exhausted")

    _SOURCE_LABELS = {
        "live": "법제처 실시간 조회 (현행 조문 원문)",
        "cache": "법제처 캐시 (현행 조문 원문)",
        "local": "법령 코퍼스 (조문 원문)",
        "seed": "내장 시드 요약 — 원문 미확인, 최신성 보장 불가",
    }

    def _build_context_block(self, matched_laws: list[LawArticle]) -> str:
        """retrieve된 법령을 LLM context로 직렬화. citation 강제용.

        법제처에서 받아온 현행 조문 원문(official_text)이 있으면 시드 요약보다 우선한다.
        원문이 없는 항목은 근거 등급을 명시해 LLM이 단정하지 않도록 한다.
        """
        if not matched_laws:
            return "(컨텍스트 법령 없음 — 법령 인용 시 '확실하지 않음' 응답 의무)"
        lines = ["## 적용 가능 법령 (컨텍스트 — 이 목록 외 인용 금지)\n"]
        for i, law in enumerate(matched_laws[:8], 1):
            lines.append(f"### {i}. {law.law_name} {law.article} ({law.title})")
            lines.append(f"- 시행일자: {law.effective_date}")
            lines.append(f"- 출처: {law.source_url}")
            lines.append(f"- 근거 등급: {self._SOURCE_LABELS.get(law.source_mode, law.source_mode)}")
            official = (law.official_text or "").strip()
            is_byeolpyo = "별표" in law.article
            if official:
                lines.append(f"- 조문 원문: {official[:900]}")
            if is_byeolpyo and law.text_summary.strip():
                # 별표(계산표 등)는 법제처 Open API가 텍스트로 제공하지 않아(HWP/PDF/이미지·JS 렌더)
                # 조문 원문 API 응답에 포함되지 않는다. 따라서 시드에 전사된 별표 표가 사실상의 원문이며,
                # LLM이 '컨텍스트에 없다'고 회피하지 않도록 권위 있는 근거로 제시한다 (출처 재확인 권장).
                lines.append(f"- 별표 표 원문(법제처 API 미제공 → 전사본, 계산 시 이 표를 근거로 사용): {law.text_summary.strip()[:1400]}")
            elif not official:
                lines.append(f"- 요약(원문 아님): {law.text_summary.strip()[:300]}")
            if law.violation_penalty:
                lines.append(f"- 위반 시: {law.violation_penalty.get('penalty', '')} / 신고처: {law.violation_penalty.get('report_channel', '')}")
            lines.append("")
        lines.append(
            "근거 사용 규칙:\n"
            "- '조문 원문'이 제공된 항목은 그 원문을 그대로 근거로 삼아 답하라.\n"
            "- '요약(원문 아님)'만 있는 항목도 근거로 쓸 수 있다. 다만 단정하지 말고 "
            "'요약 기반이므로 조문 원문 확인이 필요하다'고 밝혀라.\n"
            "- 위 목록에 법령이 하나라도 있으면 '관련 법령이 없다'고 말하지 마라. "
            "있는 조문을 근거 등급과 함께 제시하라."
        )
        return "\n".join(lines)

    def classify(self, instruction: str, text: str, model: Optional[str] = None, max_tokens: int = 200) -> Optional[str]:
        """라벨 하나만 받아오는 초저비용 호출.

        분류는 네 모델 모두 정확도가 같았으므로(model_routing 상단 실측표),
        가장 싸고 빠른 모델을 쓴다. 실패하면 None — 호출자는 결정론 경로로 되돌아가야 한다.
        """
        if not self.enabled():
            return None
        payload: dict[str, Any] = {
            "model": model or select_model("safety_classify"),
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": text[:2000]},
            ],
            "max_completion_tokens": max_tokens,
        }
        try:
            resp = self._post_with_param_fallback(payload)
        except OpenAiError:
            return None
        choices = resp.get("choices", [])
        if not choices:
            return None
        return (choices[0].get("message", {}).get("content") or "").strip()

    def ask(
        self,
        user_question: str,
        matched_laws: Optional[list[LawArticle]] = None,
        family_context_summary: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = DEFAULT_ANSWER_MAX_TOKENS,
        model: Optional[str] = None,
    ) -> LlmAnswer:
        """사용자 질문 + 매칭 법령 컨텍스트 → LLM 답변.

        Constitution 원칙 2 강제: matched_laws 컨텍스트 외 법령 인용 금지.
        `model`은 호출자가 국면에 맞게 고른다 (model_routing.select_model).
        """
        chosen = model or self.model
        if not self.enabled():
            return LlmAnswer(text="(LLM disabled — OPENAI_API_KEY 미설정)", model=chosen, error="not_configured")

        context_block = self._build_context_block(matched_laws or [])
        family_block = f"\n## 가족 정보 (요약, PII 마스킹됨)\n{family_context_summary}\n" if family_context_summary else ""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"{context_block}\n{family_block}\n## 사용자 질문\n{user_question}\n\n위 컨텍스트만 인용하여 답하라. 컨텍스트 외 법령은 '확실하지 않음' 답."
            },
        ]
        # gpt-5.x 계열은 max_tokens/temperature를 거부한다 (max_completion_tokens 사용).
        payload: dict[str, Any] = {
            "model": chosen,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        try:
            resp = self._post_with_param_fallback(payload)
        except OpenAiError as exc:
            return LlmAnswer(text="(LLM 호출 실패)", model=chosen, error=str(exc))

        choices = resp.get("choices", [])
        if not choices:
            return LlmAnswer(text="(empty choices)", model=chosen, error="empty_response")

        text = choices[0].get("message", {}).get("content") or ""
        finish_reason = choices[0].get("finish_reason", "")
        usage = resp.get("usage", {})
        cached = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

        # 토큰 상한에 걸려 잘린 답변은 답변이 아니다.
        #
        # 이전 구현은 finish_reason을 아예 보지 않았다. 상한(800)에 걸리면 본문이 빈 문자열로
        # 돌아오는데, 아래 disclaimer 보강이 그 빈 문자열에 면책 문구를 붙여서
        # "면책 문구만 있는 답변"을 정상 응답인 것처럼 내보냈다. 부모 화면에는
        # 법령 안내 대신 "법률 자문이 아닙니다" 한 줄만 떴다.
        truncated = finish_reason == "length"
        if truncated and not text.strip():
            return LlmAnswer(
                text="",
                model=chosen,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cached_tokens=cached,
                finish_reason=finish_reason,
                error="truncated_empty",
            )

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
            model=chosen,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cached_tokens=cached,
            finish_reason=finish_reason,
            truncated=truncated,
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
