"""독립 적대적 비평가 회귀 방지.

이 비평가가 존재하는 이유는 하나다: 부모가 읽을 답변을 검증하는 게이트가 **하나도**
없었기 때문이다. 감사에서 아래 문장이 전 게이트를 통과하는 것이 확인됐다.

    "[민법 제836조의2]에 따라 귀하는 100% 승소합니다."
    → verifier ratio 1.0 · independent PASS · human_review False

그리고 더 중요한 것: **판정이 실제로 무언가를 막아야 한다.** 이전 구현의 BLOCK은
리포트에 기록만 되고 소비하는 코드가 없어 PASS와 운영상 동일했다. 기록은 게이트가 아니다.
여기 테스트는 그 두 가지를 못박는다. 네트워크는 쓰지 않는다.
"""

import pytest

from jaramlaw_agent.adversarial_critic import BLOCKING_CODES, critique_answer
from jaramlaw_agent.models import LawArticle
from jaramlaw_agent.openrouter_client import OpenRouterClient, OpenRouterError


def _laws():
    return [
        LawArticle(
            law_id="labor-74",
            law_name="근로기준법",
            article="제74조",
            title="임산부 보호",
            effective_date="2025-10-23",
            text_summary="출산전후휴가",
            official_text="사용자는 임신 중의 여성에게 90일의 출산전후휴가를 주어야 한다.",
            source_url="https://law.go.kr",
            source_mode="cache",
        )
    ]


def _client_returning(payload_text: str) -> OpenRouterClient:
    client = OpenRouterClient(api_key="sk-test")
    client._post = lambda *a, **k: {  # type: ignore[method-assign]
        "choices": [{"message": {"content": payload_text}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 100},
        "model": "x-ai/grok-4.5",
    }
    return client


# --- 비평가가 결함을 잡는가 -----------------------------------------------


def test_hallucinated_citation_is_blocking():
    """컨텍스트에 없는 법령 인용은 무조건 차단이다."""
    client = _client_returning(
        '{"verdict":"WARN","findings":[{"code":"hallucinated_citation","severity":"block",'
        '"quote":"민법 제836조의2","reason":"제공된 목록에 없다"}],"summary":"환각"}'
    )
    verdict = critique_answer(
        question="양육비 문의",
        answer="[민법 제836조의2]에 따라 100% 승소합니다.",
        laws=_laws(),
        client=client,
    )
    # 모델이 스스로 WARN이라 적었어도 치명 코드가 있으면 BLOCK이다.
    # 판정을 모델의 자기 신고에 맡기면, 결함을 나열해 놓고 통과시키는 일이 생긴다.
    assert verdict.verdict == "BLOCK"
    assert verdict.available is True


def test_model_cannot_block_without_reasons():
    """근거 없는 BLOCK은 받지 않는다 — 상담을 막으려면 이유를 대야 한다."""
    client = _client_returning('{"verdict":"BLOCK","findings":[],"summary":"뭔가 이상함"}')
    verdict = critique_answer(question="q", answer="답변", laws=_laws(), client=client)
    assert verdict.verdict == "WARN"


def test_clean_answer_passes():
    client = _client_returning('{"verdict":"PASS","findings":[],"summary":"문제 없음"}')
    verdict = critique_answer(question="q", answer="근로기준법 제74조에 따르면 90일입니다.", laws=_laws(), client=client)
    assert verdict.verdict == "PASS"
    assert verdict.findings == []


def test_blocking_codes_are_the_dangerous_three():
    """차단 사유는 '사람이 다치는' 세 가지로 한정한다 — 나머지는 경고."""
    assert BLOCKING_CODES == {"hallucinated_citation", "overreach", "unauthorized_advice"}


def test_json_inside_code_fence_is_parsed():
    """JSON만 내라고 해도 모델은 코드펜스를 두른다."""
    client = _client_returning('```json\n{"verdict":"PASS","findings":[],"summary":"ok"}\n```')
    assert critique_answer(question="q", answer="a", laws=_laws(), client=client).verdict == "PASS"


# --- 비평가가 죽어도 상담은 살아야 한다 (fail-open) -----------------------


def test_network_failure_does_not_kill_the_consultation():
    client = OpenRouterClient(api_key="sk-test")

    def boom(*a, **k):
        raise OpenRouterError("Network error: unreachable")

    client._post = boom  # type: ignore[method-assign]
    verdict = critique_answer(question="q", answer="답변", laws=_laws(), client=client)
    assert verdict.verdict == "UNAVAILABLE"
    assert verdict.available is False


def test_unparseable_response_is_not_disguised_as_pass():
    """판정을 못 했으면 못 했다고 해야 한다. PASS로 위장하면 검증된 것처럼 보인다."""
    client = _client_returning("음... 잘 모르겠네요")
    verdict = critique_answer(question="q", answer="답변", laws=_laws(), client=client)
    assert verdict.verdict == "UNAVAILABLE"
    assert verdict.error == "unparseable_response"


def test_missing_key_is_unavailable_not_pass(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    verdict = critique_answer(question="q", answer="답변", laws=_laws(), client=OpenRouterClient())
    assert verdict.verdict == "UNAVAILABLE"
    assert verdict.error == "no_api_key"


def test_disabled_critic_is_explicit():
    verdict = critique_answer(question="q", answer="답변", laws=_laws(), enabled=False)
    assert verdict.verdict == "UNAVAILABLE"
    assert verdict.error == "disabled"


# --- 제3자에게 가족 정보를 보내지 않는다 ----------------------------------


def test_family_profile_is_never_sent_to_third_party():
    """비평가는 외부 회사(xAI/Anthropic)다. 아이 생년월일이 나가면 안 된다."""
    captured = {}

    client = OpenRouterClient(api_key="sk-test")

    def capture(model, messages, max_tokens):
        captured["payload"] = " ".join(m["content"] for m in messages)
        return {
            "choices": [{"message": {"content": '{"verdict":"PASS","findings":[],"summary":""}'}, "finish_reason": "stop"}],
            "usage": {},
            "model": model,
        }

    client._post = capture  # type: ignore[method-assign]
    verdict = critique_answer(
        question="학원비 환불 문의", answer="답변입니다", laws=_laws(), client=client
    )

    payload = captured["payload"]
    # 가족 프로필은 비평가 프롬프트에 애초에 들어가지 않는다 (구조적으로 전달 안 함).
    for leak in ("2019-08-10", "birth_date", "life_stages", "region_code", "dual_income"):
        assert leak not in payload

    # 무엇을 보냈는지 리포트에 남긴다 — 감사 가능해야 한다.
    assert verdict.sent_fields == ["question(masked)", "ai_answer", "law_context"]


# --- 판정이 실제로 무언가를 막는가 (핵심) ---------------------------------


def test_block_verdict_is_enforced_by_independent_validation():
    """BLOCK을 기록만 하면 그건 게이트가 아니라 장식이다."""
    from jaramlaw_agent.cross_model_verifier import run_independent_validation
    from jaramlaw_agent.models import FamilyProfile, FinalReport

    report = FinalReport(family_profile=FamilyProfile())
    result = run_independent_validation(
        report,
        model_routing={},
        budget_guard={"allowed": True},
        critic_verdict={"verdict": "BLOCK", "summary": "환각 인용", "findings": [], "model": "x-ai/grok-4.5"},
    )
    assert result["status"] == "BLOCK"
    assert any(f["code"] == "adversarial_critic_block" for f in result["findings"])


def test_unavailable_critic_is_surfaced_not_hidden():
    """검증을 못 했다는 사실을 숨기면, 검증된 것처럼 보여서 더 위험하다."""
    from jaramlaw_agent.cross_model_verifier import run_independent_validation
    from jaramlaw_agent.models import FamilyProfile, FinalReport

    result = run_independent_validation(
        FinalReport(family_profile=FamilyProfile()),
        model_routing={},
        budget_guard={"allowed": True},
        critic_verdict={"verdict": "UNAVAILABLE", "error": "timeout", "findings": []},
    )
    assert any(f["code"] == "adversarial_critic_unavailable" for f in result["findings"])
