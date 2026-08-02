"""cli.py — 외부 클라이언트가 있을 때의 분기 (mock 주입).

doctor --deep / search-law --remote / fetch-article / ask (with OpenAI) 경로를
가짜 클라이언트로 커버한다. cli는 함수 내부에서 lazy import 하므로 소스 모듈의
클래스를 monkeypatch 한다.
"""

from __future__ import annotations

import pytest

from jaramlaw_agent import cli
from jaramlaw_agent.config import Config


@pytest.fixture
def legalize_repo(tmp_path):
    kr = tmp_path / "kr" / "근로기준법"
    kr.mkdir(parents=True)
    (kr / "법률.md").write_text(
        "---\n제목: 근로기준법\n시행일자: 20210701\n출처: https://law.go.kr/x\n---\n"
        "##### 제74조(임산부의 보호)\n출산 전후 휴가 90일.\n",
        encoding="utf-8",
    )
    return tmp_path


class _FakeArticle:
    law_name = "근로기준법"
    title = "임산부의 보호"
    effective_date_iso = "20210701"
    source_url = "https://law.go.kr/x"
    file_path = "kr/근로기준법/법률.md"
    body_full = "제74조 본문"
    article_excerpt = "제74조(임산부의 보호) 출산 전후 휴가 90일."


class _FakeLegalize:
    def __init__(self, *a, **k): ...
    def available(self): return True
    def list_mapped_laws(self): return [("labor-standards-74", "kr/근로기준법/법률.md", True)]
    def search_full_text(self, kw, max_results=3): return [_FakeArticle()]
    def get_article(self, law_id): return _FakeArticle()
    def extract_article_section(self, law_id, article): return _FakeArticle()


class _FakeSearchResult:
    law_name = "근로기준법"
    promulgation_date = "20210101"
    effective_date = "20210701"
    department = "고용노동부"
    law_mst = "264617"


class _FakeLawApi:
    def __init__(self, *a, **k): ...
    def search_laws(self, kw, display=5, search_mode=1): return [_FakeSearchResult()]
    def diagnose(self): return {"status": "OK", "sample_law": "근로기준법"}


class _FakeAnswer:
    text = "[근로기준법 제74조]에 따라 휴가 90일. 법률 자문 아님."
    model = "gpt-test"
    total_tokens = 150
    prompt_tokens = 100
    completion_tokens = 50
    citations = ["근로기준법 제74조"]
    safety_flag = False
    error = None


class _FakeOpenAi:
    def __init__(self, *a, **k): ...
    def ask(self, **k): return _FakeAnswer()
    def diagnose(self): return {"status": "OK", "sample_tokens": 10}


@pytest.fixture
def _inject(monkeypatch, legalize_repo):
    """Config를 클라이언트 활성 상태로 + 가짜 클라이언트 주입."""
    def _cfg(*a, **k):
        return Config(
            openai_api_key="sk-test",
            law_api_key="lawkey",
            legalize_kr_path=legalize_repo,
        )
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls, *a, **k: _cfg()))
    monkeypatch.setattr("jaramlaw_agent.legalize_kr_client.LegalizeKrClient", _FakeLegalize)
    monkeypatch.setattr("jaramlaw_agent.law_api_client.LawApiClient", _FakeLawApi)
    monkeypatch.setattr("jaramlaw_agent.openai_client.OpenAiClient", _FakeOpenAi)


def test_doctor_deep_with_clients(_inject, capsys):
    rc = cli.main(["doctor", "--deep"])
    out = capsys.readouterr().out
    assert "legalize-kr 매핑" in out
    assert "법제처 API 호출 테스트" in out
    assert "OpenAI 호출 테스트" in out
    assert rc in (0, 1)


def test_search_law_remote_with_key(_inject, capsys):
    rc = cli.main(["search-law", "휴가", "--remote"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "법제처 Open API 검색" in out
    assert "근로기준법" in out
    assert "legalize-kr 본문 검색" in out


def test_fetch_article_with_legalize(_inject, capsys):
    rc = cli.main(["fetch-article", "labor-standards-74", "--article", "제74조"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "임산부의 보호" in out
    assert "20210701" in out


def test_fetch_article_full_flag(_inject, capsys):
    rc = cli.main(["fetch-article", "labor-standards-74", "--full"])
    out = capsys.readouterr().out
    assert rc == 0


def test_ask_with_openai(_inject, capsys):
    rc = cli.main(["ask", "육아휴직 신청 방법?"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "제74조" in out
    assert "tokens:" in out


def test_ask_with_legalize_enrichment(_inject, capsys):
    """--with-legalize 기본 활성 → legalize-kr 시행일 보강 분기."""
    rc = cli.main(["ask", "환불 규정?", "--persona", "P2"])
    out = capsys.readouterr().out
    assert rc == 0
