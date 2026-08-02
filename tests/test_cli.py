"""cli.py 커버리지 — 진입점 서브커맨드 전 분기.

seeded 모드(API 키 없음)로 main(argv=...)을 호출해 외부 호출 없이 전 경로를 탄다.
demo A/B/C는 orchestrator.run_workflow 전체를 돌리므로 E2E 커버까지 겸한다.
"""

from __future__ import annotations

import json

import pytest

from jaramlaw_agent import cli


@pytest.fixture(autouse=True)
def _seeded_env(monkeypatch):
    """모든 CLI 테스트를 seeded 모드로 고정 — 외부 API 키 제거."""
    for var in (
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "LAW_API_KEY",
        "LEGALIZE_KR_PATH",
        "JARAMLAW_CRITIC_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


# === doctor ===


def test_doctor_seeded_passes(capsys):
    rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "자람법 doctor" in out
    assert "laws seeded" in out
    # 시드가 갖춰져 있으면 0, 부족하면 1 — 둘 다 정상 경로
    assert rc in (0, 1)


def test_doctor_deep_without_keys(capsys):
    """--deep 이지만 키가 없으면 API 호출 분기를 건너뛴다 (예외 없이)."""
    rc = cli.main(["doctor", "--deep"])
    out = capsys.readouterr().out
    assert "외부 통합" in out
    assert rc in (0, 1)


# === demo (전체 워크플로우 E2E) ===


@pytest.mark.parametrize("scenario", ["A", "B", "C"])
def test_demo_runs_full_workflow(scenario, capsys):
    rc = cli.main(["demo", "--scenario", scenario])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"시나리오 {scenario}" in out
    assert "매칭 법령" in out
    assert "권리 카드" in out


def test_demo_writes_output_file(tmp_path, capsys):
    out_file = tmp_path / "report.json"
    rc = cli.main(["demo", "--scenario", "A", "--output", str(out_file)])
    assert rc == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "family_profile" in data


def test_demo_print_first_card(capsys):
    rc = cli.main(["demo", "--scenario", "B", "--print-first-card"])
    out = capsys.readouterr().out
    assert rc == 0
    # 권리카드가 있으면 markdown 구분선이 찍힌다
    assert "=" * 60 in out or "권리 카드: 0장" in out


def test_demo_unknown_scenario_raises():
    with pytest.raises(SystemExit):
        cli._load_scenario("Z")


# === validate-workflow ===


def test_validate_workflow_ok(capsys):
    rc = cli.main(["validate-workflow"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "workflow OK" in out
    assert "nodes" in out


# === search-law ===


def test_search_law_seed_only(capsys):
    rc = cli.main(["search-law", "육아휴직"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "검색어: 육아휴직" in out
    assert "시드 매칭" in out


def test_search_law_remote_without_key(capsys):
    """--remote 이지만 LAW_API_KEY 없으면 경고 분기."""
    rc = cli.main(["search-law", "환불", "--remote"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "LAW_API_KEY 미설정" in out


# === fetch-article ===


def test_fetch_article_without_legalize(capsys):
    """legalize-kr 저장소가 없으면 안내 후 1 반환."""
    rc = cli.main(["fetch-article", "labor-standards-74"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "legalize-kr" in out


# === ask ===


def test_ask_without_openai_key(capsys):
    """OPENAI_API_KEY 없으면 컨텍스트 법령만 출력하고 LLM 스킵."""
    rc = cli.main(["ask", "육아휴직은 어떻게 신청하나요?"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "질문:" in out
    assert "OPENAI_API_KEY 미설정" in out


def test_ask_with_persona(capsys):
    rc = cli.main(["ask", "환불 받을 수 있나요?", "--persona", "P2"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "컨텍스트 법령" in out


# === main / argparse ===


def test_version_flag_exits_zero():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0


def test_no_subcommand_errors():
    """서브커맨드 없이 호출하면 argparse가 SystemExit(2)."""
    with pytest.raises(SystemExit):
        cli.main([])
