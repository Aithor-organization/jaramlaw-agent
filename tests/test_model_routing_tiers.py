"""모델 라우팅 회귀 방지.

과거에 두 번 조용히 깨졌다:
  1) .env의 OPENAI_MODEL이 모든 tier를 덮어써서, 분류까지 비싼 모델로 올라갔다.
     라우팅 코드는 멀쩡했지만 실제로는 한 모델만 쓰고 있었다.
  2) .env에 `gpt-5.6-sola`라는 존재하지 않는 모델이 들어가 있었다 (올바른 이름은 gpt-5.6-sol).
     뒤에 있던 다른 줄이 이겨서 404가 가려져 있었다.
둘 다 런타임에만 드러나는 종류라, 여기서 못 박아 둔다.
"""

import os

import pytest

from jaramlaw_agent.guard import augment_safety_with_llm, detect_safety_signals
from jaramlaw_agent.model_routing import (
    MODEL_TIERS,
    REASONING_MODELS,
    plan_model_routing,
    select_model,
    validate_configured_models,
)
from jaramlaw_agent.models import SafetyRouting


def test_configured_models_are_real():
    """설정된 모델 ID가 전부 실존해야 한다 (gpt-5.6-sola 같은 오타 차단)."""
    assert validate_configured_models() == []


def test_classification_uses_cheapest_tier():
    """분류는 네 모델 정확도가 같았으므로 가장 싼 모델을 쓴다."""
    assert select_model("safety_classify") == MODEL_TIERS["classify"]
    assert select_model("scenario_classify") == MODEL_TIERS["classify"]


def test_answer_tier_selection():
    """국면에 따라 tier가 갈리되, 어떤 tier를 고르든 그 선택은 실측에 근거해야 한다."""
    assert select_model("answer", "standard") == MODEL_TIERS["answer"]
    assert select_model("answer", "shallow") == MODEL_TIERS["answer"]
    assert select_model("answer", "critical") == MODEL_TIERS["critical"]
    assert select_model("answer", "deep") == MODEL_TIERS["critical"]


def test_answer_path_stays_within_latency_budget():
    """답변 경로에 추론 모델을 두지 않는다.

    gpt-5.6-sol을 고위험 tier에 뒀다가 실측에서 되돌렸다. 품질은 무승부(1승 1패)인데
    2~3배 느렸고, 최악 28.8초가 orchestrator 예산(25초)을 넘겨 워크플로우를 터뜨렸다.
    되돌리고 싶으면 JARAMLAW_MODEL_CRITICAL로 명시 opt-in 해야 한다 — 기본값이 되면 안 된다.
    """
    for tier in ("classify", "answer", "critical"):
        assert MODEL_TIERS[tier] not in REASONING_MODELS, (
            f"{tier} tier에 추론 모델({MODEL_TIERS[tier]})이 기본값으로 들어왔다 — "
            "지연 예산을 넘긴 전력이 있다"
        )


def test_legacy_openai_model_does_not_collapse_routing(monkeypatch):
    """레거시 OPENAI_MODEL이 라우팅을 통째로 덮어쓰면 안 된다 (실제로 그랬다)."""
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-terra")
    assert select_model("safety_classify") == MODEL_TIERS["classify"]
    assert select_model("answer", "standard") == MODEL_TIERS["answer"]


def test_explicit_pin_overrides_everything(monkeypatch):
    """비상 고정은 명시적 opt-in일 때만 동작한다."""
    monkeypatch.setenv("JARAMLAW_MODEL_PIN", "gpt-5.5")
    assert select_model("safety_classify") == "gpt-5.5"
    assert select_model("answer", "critical") == "gpt-5.5"


def test_plan_reports_llm_usage_truthfully():
    """감사 로그가 '외부 모델 호출 없음'이라 적으면서 호출하고 있으면 안 된다."""
    raw = {"scenario": {"type": "academy_refund", "query": "환불"}}
    off = plan_model_routing(raw, SafetyRouting(triggered=False), llm_enabled=False)
    on = plan_model_routing(raw, SafetyRouting(triggered=False), llm_enabled=True)
    assert off["external_model_calls"] is False
    assert on["external_model_calls"] is True
    assert on["selected_models"]["answer"] == MODEL_TIERS["answer"]


def test_safety_trigger_escalates_criticality():
    raw = {"scenario": {"type": "general", "query": "도와주세요"}}
    plan = plan_model_routing(raw, SafetyRouting(triggered=True, category="child_abuse_suspected"), llm_enabled=True)
    assert plan["criticality"] == "critical"
    assert plan["escalated"] is True
    assert plan["answer_model"] == MODEL_TIERS["critical"]


def test_answer_truncation_is_not_passed_off_as_an_answer():
    """토큰 상한에 걸려 본문이 빈 응답을 정상 답변으로 내보내면 안 된다.

    이전엔 finish_reason을 보지 않아서, 빈 본문에 면책 문구만 붙여 내보냈다.
    부모 화면에는 법령 안내 대신 '법률 자문이 아닙니다' 한 줄만 떴다.
    """
    from jaramlaw_agent.openai_client import DEFAULT_ANSWER_MAX_TOKENS, LlmAnswer, OpenAiClient

    # 상한이 답변을 끝까지 쓸 만큼 넉넉해야 한다 (800에서 빈 응답 재현됨).
    assert DEFAULT_ANSWER_MAX_TOKENS >= 1500

    client = OpenAiClient()
    client.config.openai_api_key = "sk-test"  # enabled() 통과용
    client._post_with_param_fallback = lambda payload: {  # type: ignore[method-assign]
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 3000, "completion_tokens": 800, "total_tokens": 3800},
    }
    answer: LlmAnswer = client.ask("학교폭력 신고 절차")
    assert answer.error == "truncated_empty"
    assert answer.text == ""
    assert "법률 자문" not in answer.text  # 면책 문구만 남은 가짜 답변이 아니다


def test_cached_tokens_are_recorded():
    """OpenAI가 자동 재사용한 입력 토큰을 기록해야 비용을 과대 계상하지 않는다."""
    from jaramlaw_agent.openai_client import OpenAiClient

    client = OpenAiClient()
    client.config.openai_api_key = "sk-test"
    client._post_with_param_fallback = lambda payload: {  # type: ignore[method-assign]
        "choices": [{"message": {"content": "답변입니다. [근로기준법 제74조]"}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 3853,
            "completion_tokens": 200,
            "total_tokens": 4053,
            "prompt_tokens_details": {"cached_tokens": 3850},
        },
    }
    answer = client.ask("질문")
    assert answer.cached_tokens == 3850
    assert answer.finish_reason == "stop"
    assert answer.truncated is False
    assert answer.citations == ["근로기준법 제74조"]


# === 안전 보강: 모델은 신호를 더할 수만 있고, 절대 지울 수 없다 ===


def _payload(text):
    return {"scenario": {"query": text}}


def test_llm_never_downgrades_keyword_signal():
    """키워드가 잡은 신호는 모델이 none이라 해도 살아남아야 한다."""
    payload = _payload("아이가 호흡곤란 증상을 보여요")
    deterministic = detect_safety_signals(payload)
    assert deterministic.triggered  # 키워드가 잡음

    called = []

    def liar(_instruction, _text):
        called.append(1)
        return "none"

    result = augment_safety_with_llm(payload, deterministic, classifier=liar)
    assert result.triggered is True
    assert result.category == deterministic.category
    assert called == []  # 이미 잡혔으면 호출조차 하지 않는다 (강등 불가 + 비용 0)


def test_llm_failure_falls_back_to_keyword():
    """모델이 죽어도 결정론 결과가 그대로 살아야 한다."""
    payload = _payload("학원비 환불 문의")
    deterministic = detect_safety_signals(payload)

    def boom(_i, _t):
        raise RuntimeError("network down")

    assert augment_safety_with_llm(payload, deterministic, classifier=boom).triggered is False
    assert augment_safety_with_llm(payload, deterministic, classifier=lambda i, t: None).triggered is False
    assert augment_safety_with_llm(payload, deterministic, classifier=None).triggered is False


def test_llm_adds_signal_keyword_missed():
    """키워드가 놓친 표현을 모델이 잡아 올린다 (실측: 키워드 0/8 → 보강 8/8)."""
    payload = _payload("죽고싶어요")  # 키워드는 '죽고 싶' — 띄어쓰기 하나로 놓친다
    deterministic = detect_safety_signals(payload)
    assert deterministic.triggered is False

    result = augment_safety_with_llm(payload, deterministic, classifier=lambda i, t: "self_harm")
    assert result.triggered is True
    assert result.category == "self_harm_signal"
    assert "1393" in (result.contact or "")


def test_unknown_label_is_ignored():
    """모델이 헛소리하면 무시하고 결정론 결과를 쓴다."""
    payload = _payload("학원비 환불 문의")
    deterministic = detect_safety_signals(payload)
    result = augment_safety_with_llm(payload, deterministic, classifier=lambda i, t: "바나나")
    assert result.triggered is False
