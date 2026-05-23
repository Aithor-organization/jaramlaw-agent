import os

from jaramlaw_agent.config import Config, _parse_dotenv_file, redact_secret


def test_redact_secret_short():
    assert redact_secret(None) == "<unset>"
    assert redact_secret("") == "<unset>"
    assert redact_secret("abc") == "***"


def test_redact_secret_normal():
    out = redact_secret("sk-proj-1234567890abcdef")
    assert out.startswith("sk-pro")
    assert out.endswith("cdef")
    assert "..." in out


def test_parse_dotenv_basic(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "OPENAI_API_KEY=sk-test-key\n"
        "OPENAI_MODEL=gpt-4o-mini\n"
        "QUOTED=\"value-with-spaces\"\n"
        "EMPTY=\n",
        encoding="utf-8",
    )
    parsed = _parse_dotenv_file(env_file)
    assert parsed["OPENAI_API_KEY"] == "sk-test-key"
    assert parsed["OPENAI_MODEL"] == "gpt-4o-mini"
    assert parsed["QUOTED"] == "value-with-spaces"
    assert parsed["EMPTY"] == ""


def test_config_summary_no_leak():
    """summary는 마스킹 — 평문 키 노출 X."""
    cfg = Config(openai_api_key="sk-proj-secret-1234567890", law_api_key="dummy-law-key-for-test")
    s = cfg.summary()
    assert "sk-proj-secret-1234567890" not in str(s)
    assert "dummy-law-key-for-test" not in str(s)
