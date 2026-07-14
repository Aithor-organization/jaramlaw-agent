"""독립 적대적 비평가 — 부모가 읽을 답변을 다른 회사의 모델이 물어뜯는다.

## 왜 필요한가

이 시스템의 가장 큰 구멍은 **부모가 실제로 읽는 텍스트(LLM 답변)에 검증 게이트가 하나도
없다**는 것이었다. atomic claim 검증은 결정론 산출물(법령·지원·권리카드)만 보고,
그마저 인용 4요소의 '존재'만 센다. 그 사이에 답변 생성기는 자유롭게 쓴다.

실제로 확인된 통과 사례:

    "[민법 제836조의2]에 따라 귀하는 100% 승소합니다."
    → verifier ratio 1.0 · independent PASS · human_review False   (전 게이트 통과)

컨텍스트에 없는 법령을 인용하고, 승소를 단정했는데 아무도 막지 않았다.
답변을 쓴 모델에게 자기 답변을 검토시키는 것으로는 이걸 못 잡는다 —
같은 착각을 두 번 하기 때문이다. 그래서 **다른 회사의 모델**을 부른다.

## 무엇을 잡는가

    hallucinated_citation  컨텍스트에 없는 법령을 인용했다
    overreach              조문이 말하지 않는 것을 단정했다 (승소/금액/결과 보장)
    unauthorized_advice    변호사법이 금지하는 구체적 법률 자문에 해당한다
    missing_exception      적용 예외·단서를 빠뜨려 오해를 유발한다
    stale_or_pending       시행 전이거나 폐지된 조문을 현행처럼 말했다
    unsupported_claim      제공된 조문 원문으로 뒷받침되지 않는 주장이다

## 제3자 전송 — 무엇이 나가는가

비평가는 xAI/Anthropic이라는 **외부 회사**다. 그래서 나가는 것을 최소화한다:

    나간다:   마스킹된 질문 · AI 답변 · 컨텍스트로 준 법령(공개 정보)
    안 나간다: 아이 생년월일 · 이름 · 지역 · 가족 구성 · life_stages · flags

질문 원문은 나간다 — 답변의 적절성을 판단하려면 무엇을 물었는지 알아야 하기 때문이다.
이미 답변 생성기(OpenAI)에도 같은 질문이 나가고 있으므로 노출 계층이 하나 늘어나는 것이고,
그 사실을 여기 적어 둔다. 원치 않으면 `JARAMLAW_ENABLE_CRITIC=0`으로 끈다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import LawArticle
from .openrouter_client import OpenRouterClient, CritiqueResponse


SYSTEM_PROMPT = (
    "당신은 한국 가족법령 AI 상담 서비스의 **독립 적대적 검증자**다. "
    "당신의 임무는 칭찬이 아니라 결함을 찾는 것이다. 문제를 찾지 못했다면 그때만 PASS다.\n\n"
    "부모가 읽게 될 AI 답변과, 그 답변에 근거로 제공된 법령 목록을 받는다. "
    "답변이 제공된 법령의 범위를 넘어서지 않았는지 적대적으로 검증하라.\n\n"
    "찾아야 할 결함:\n"
    "1. hallucinated_citation — 제공된 법령 목록에 **없는** 법령·조문을 인용했다. (가장 심각)\n"
    "2. overreach — 조문이 말하지 않는 것을 단정했다. 승소 가능성·구체적 금액 보장·결과 확언.\n"
    "3. unauthorized_advice — 변호사법이 금지하는 구체적 사건의 법률 자문·소송 전략에 해당한다.\n"
    "4. missing_exception — 적용 예외나 단서를 빠뜨려 부모가 오해할 수 있다.\n"
    "5. stale_or_pending — 시행 전이거나 이미 바뀐 조문을 현행처럼 서술했다.\n"
    "6. unsupported_claim — 제공된 조문 원문으로 뒷받침되지 않는 사실 주장이다.\n\n"
    "판정 기준:\n"
    "- BLOCK: hallucinated_citation 또는 overreach 또는 unauthorized_advice가 하나라도 있다. "
    "이 답변을 그대로 부모에게 보여주면 안 된다.\n"
    "- WARN: 나머지 결함만 있다. 보여주되 경고를 붙여야 한다.\n"
    "- PASS: 결함을 찾지 못했다.\n\n"
    "반드시 아래 JSON만 출력하라. 설명·마크다운·코드펜스 금지.\n"
    '{"verdict":"PASS|WARN|BLOCK","findings":[{"code":"...","severity":"block|warn",'
    '"quote":"답변에서 문제가 된 부분 그대로","reason":"왜 문제인지 한 문장"}],'
    '"summary":"한 문장 총평"}'
)

BLOCKING_CODES = {"hallucinated_citation", "overreach", "unauthorized_advice"}


@dataclass
class CriticVerdict:
    """비평가의 판정. `enforced`가 False면 이 판정은 아무것도 막지 않았다는 뜻이다."""

    available: bool
    verdict: str                       # PASS | WARN | BLOCK | UNAVAILABLE
    findings: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    model: str = ""
    fallback_used: bool = False
    error: Optional[str] = None
    tokens: int = 0
    sent_fields: list[str] = field(default_factory=list)   # 제3자에게 무엇을 보냈는지 기록

    def to_dict(self) -> dict[str, Any]:
        return {
            "critic_version": "jaramlaw-adversarial-critic/v1",
            "available": self.available,
            "verdict": self.verdict,
            "findings": self.findings,
            "summary": self.summary,
            "model": self.model,
            "fallback_used": self.fallback_used,
            "error": self.error,
            "tokens": self.tokens,
            "sent_to_third_party": self.sent_fields,
        }


def _law_context(laws: list[LawArticle], limit: int = 6) -> str:
    lines = []
    for i, law in enumerate(laws[:limit], 1):
        body = (law.official_text or law.text_summary or "").strip()[:400]
        lines.append(
            f"{i}. {law.law_name} {law.article} (시행 {law.effective_date}, 근거등급 {law.source_mode})\n"
            f"   {body}"
        )
    return "\n".join(lines) if lines else "(제공된 법령 없음 — 어떤 법령 인용도 환각이다)"


def _parse(text: str) -> Optional[dict[str, Any]]:
    """모델이 JSON만 뱉으라 해도 코드펜스를 두른다. 첫 JSON 객체를 건져낸다."""
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", stripped, re.DOTALL)
        if brace:
            stripped = brace.group()
    try:
        data = json.loads(stripped)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def critique_answer(
    *,
    question: str,
    answer: str,
    laws: list[LawArticle],
    client: Optional[OpenRouterClient] = None,
    enabled: bool = True,
) -> CriticVerdict:
    """부모가 읽을 답변을 독립 모델에게 적대적으로 검증시킨다.

    비평가가 없거나 죽으면 UNAVAILABLE을 돌려준다 — 상담을 막지 않되, 검증되지
    않았다는 사실을 숨기지도 않는다.
    """
    if not enabled:
        return CriticVerdict(available=False, verdict="UNAVAILABLE", error="disabled")
    if not (answer or "").strip():
        return CriticVerdict(available=False, verdict="UNAVAILABLE", error="no_answer")

    client = client or OpenRouterClient()
    if not client.enabled():
        return CriticVerdict(available=False, verdict="UNAVAILABLE", error="no_api_key")

    user_prompt = (
        f"## 부모의 질문\n{question.strip()[:1500]}\n\n"
        f"## 답변에 근거로 제공된 법령 (이 목록 밖의 인용은 전부 환각이다)\n{_law_context(laws)}\n\n"
        f"## 검증 대상 — 부모가 읽게 될 AI 답변\n{answer.strip()[:4000]}\n\n"
        "위 답변을 적대적으로 검증하고 지정된 JSON만 출력하라."
    )

    response: CritiqueResponse = client.critique(SYSTEM_PROMPT, user_prompt)
    # 무엇이 제3자에게 나갔는지 기록해 둔다 — 가족 프로필은 여기 없다.
    sent = ["question(masked)", "ai_answer", "law_context"]

    if not response.available:
        return CriticVerdict(
            available=False, verdict="UNAVAILABLE", error=response.error,
            model=response.model, sent_fields=sent,
        )

    data = _parse(response.text)
    if not data:
        return CriticVerdict(
            available=False, verdict="UNAVAILABLE", error="unparseable_response",
            model=response.model, fallback_used=response.fallback_used,
            tokens=response.total_tokens, sent_fields=sent,
        )

    findings = [f for f in (data.get("findings") or []) if isinstance(f, dict)]

    # 판정을 모델의 자기 신고에 맡기지 않는다. 치명 코드가 있으면 그가 뭐라 했든 BLOCK이다.
    # (모델이 "BLOCK" 대신 "WARN"이라 적어 놓고 hallucinated_citation을 나열하는 일이 실제로 있다.)
    codes = {str(f.get("code") or "").strip() for f in findings}
    if codes & BLOCKING_CODES:
        verdict = "BLOCK"
    else:
        claimed = str(data.get("verdict") or "").upper()
        verdict = claimed if claimed in ("PASS", "WARN", "BLOCK") else ("WARN" if findings else "PASS")
        if verdict == "BLOCK" and not findings:
            # 근거 없는 BLOCK은 받지 않는다 — 상담을 막으려면 이유를 대야 한다.
            verdict = "WARN"

    return CriticVerdict(
        available=True,
        verdict=verdict,
        findings=findings,
        summary=str(data.get("summary") or "").strip(),
        model=response.model,
        fallback_used=response.fallback_used,
        tokens=response.total_tokens,
        sent_fields=sent,
    )
