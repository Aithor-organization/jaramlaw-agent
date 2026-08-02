"""openai_client — OpenAI Chat Completions (urllib mock).

_http_post_json을 canned 응답으로 대체해 ask/classify/param-fallback/diagnose 커버.
"""

from __future__ import annotations

import urllib.error

import pytest

from jaramlaw_agent import agentshield_bridge as bridge
from jaramlaw_agent.config import Config
from jaramlaw_agent.models import LawArticle
from jaramlaw_agent.openai_client import (
    OpenAiClient,
    OpenAiError,
    OpenAiPermanentError,
)


def _client(key="sk-test"):
    cfg = Config(openai_api_key=key, openai_model="gpt-test")
    return OpenAiClient(cfg, timeout=1.0)


def _law():
    return LawArticle(
        law_id="labor-standards-74",
        law_name="근로기준법",
        article="제74조",
        title="임산부의 보호",
        text_summary="출산전후휴가 90일 보장",
        effective_date="20210701",
        source_url="https://law.go.kr/x",
        source_mode="seed",
    )


def _completion(text, finish="stop", usage=None):
    return {
        "choices": [{"message": {"content": text}, "finish_reason": finish}],
        "usage": usage or {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


# === enabled / disabled ===


def test_disabled_ask_returns_error():
    c = _client(key="")
    ans = c.ask("질문")
    assert ans.error == "not_configured"
    assert "disabled" in ans.text


def test_disabled_classify_returns_none():
    c = _client(key="")
    assert c.classify("분류", "텍스트") is None


# === ask ===


def test_ask_success_with_disclaimer_augment(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_post_json", lambda p: _completion("[근로기준법 제74조]에 따라 휴가 90일."))
    ans = c.ask("육아휴직?", matched_laws=[_law()], family_context_summary="flags=[pregnant]")
    assert "제74조" in ans.text
    assert "법률 자문" in ans.text  # disclaimer 자동 보강
    assert ans.citations == ["근로기준법 제74조"]
    assert ans.total_tokens == 150


def test_ask_safety_flag(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_post_json", lambda p: _completion("긴급 시 1393 자살예방상담. 법률 자문 아님."))
    ans = c.ask("힘들어요", matched_laws=[])
    assert ans.safety_flag is True


def test_ask_truncated_empty(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_post_json", lambda p: _completion("", finish="length"))
    ans = c.ask("긴 질문", matched_laws=[_law()])
    assert ans.error == "truncated_empty"
    assert ans.text == ""


def test_ask_empty_choices(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_post_json", lambda p: {"choices": [], "usage": {}})
    ans = c.ask("질문")
    assert ans.error == "empty_response"


def test_ask_http_error(monkeypatch):
    c = _client()
    def _boom(p):
        raise OpenAiError("HTTP 500: server down")
    monkeypatch.setattr(c, "_http_post_json", _boom)
    ans = c.ask("질문", matched_laws=[_law()])
    assert ans.error is not None
    assert "실패" in ans.text


# === _build_context_block ===


def test_build_context_block_empty():
    c = _client()
    block = c._build_context_block([])
    assert "컨텍스트 법령 없음" in block


def test_build_context_block_with_official_text():
    c = _client()
    law = _law()
    law.official_text = "제74조(임산부의 보호) 사용자는 출산 전후 휴가를 주어야 한다."
    law.source_mode = "live"
    block = c._build_context_block([law])
    assert "조문 원문" in block
    assert "근로기준법" in block


# === classify ===


def test_classify_success(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_post_with_param_fallback", lambda p: _completion("child_abuse"))
    assert c.classify("분류기", "아이가 맞았어요") == "child_abuse"


def test_classify_empty_choices(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_post_with_param_fallback", lambda p: {"choices": []})
    assert c.classify("분류기", "텍스트") is None


def test_classify_error_returns_none(monkeypatch):
    c = _client()
    def _boom(p):
        raise OpenAiError("boom")
    monkeypatch.setattr(c, "_post_with_param_fallback", _boom)
    assert c.classify("분류기", "텍스트") is None


# === _post_with_param_fallback (400 파라미터 폴백) ===


def test_param_fallback_drops_unsupported_param(monkeypatch):
    c = _client()
    calls = {"n": 0}

    def _fake_post(payload):
        calls["n"] += 1
        if "temperature" in payload:
            raise OpenAiError("HTTP 400: 'temperature' is not supported with this model")
        return _completion("ok")

    monkeypatch.setattr(c, "_http_post_json", _fake_post)
    resp = c._post_with_param_fallback({"model": "m", "temperature": 0.2, "messages": []})
    assert resp["choices"][0]["message"]["content"] == "ok"
    assert calls["n"] == 2  # 1차 400 → temperature 제거 후 2차 성공


def test_param_fallback_non400_reraises(monkeypatch):
    c = _client()
    def _boom(p):
        raise OpenAiError("HTTP 500: down")
    monkeypatch.setattr(c, "_http_post_json", _boom)
    with pytest.raises(OpenAiError):
        c._post_with_param_fallback({"model": "m", "messages": []})


# === _http_post_json (urlopen mock) ===


def test_http_post_success(monkeypatch):
    c = _client()
    bridge.reset_breakers()

    class _Resp:
        def read(self): return b'{"choices":[],"usage":{}}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _Resp())
    out = c._http_post_json({"model": "m", "messages": []})
    assert out == {"choices": [], "usage": {}}


def test_http_post_400_permanent(monkeypatch):
    c = _client()
    bridge.reset_breakers()

    class _Err(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("u", 400, "Bad", {}, None)
        def read(self): return b"bad param"

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: (_ for _ in ()).throw(_Err()))
    with pytest.raises(OpenAiPermanentError):
        c._http_post_json({"model": "m", "messages": []})


def test_http_post_disabled():
    c = _client(key="")
    with pytest.raises(OpenAiError):
        c._http_post_json({"model": "m", "messages": []})


# === diagnose ===


def test_diagnose_disabled():
    c = _client(key="")
    info = c.diagnose()
    assert info["enabled"] is False
    assert "disabled" in info["status"]


def test_diagnose_ok(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_http_post_json", lambda p: _completion("OK. 법률 자문 아님."))
    info = c.diagnose()
    assert info["status"] == "OK"
