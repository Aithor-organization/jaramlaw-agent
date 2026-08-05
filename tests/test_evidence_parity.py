"""답변자와 비평가는 **같은 근거**를 봐야 한다 — 회귀 방지.

2026-08-06 라이브 실측: 프로덕션 상담 3건(학원 환불 2 · 임신 지원 1)이 **전부**
`withheld_by_critic`으로 막혔다. 부모 화면에 AI 답변이 한 번도 뜨지 않았다.

원인은 비평가의 오작동이 아니라 **시야 비대칭**이었다.

    답변 LLM   : 조문 원문 900자 + 별표 전사본 1400자
    비평가     : (official_text or text_summary) 400자, 별표 전사본은 아예 못 봄

비평가의 판정 규칙은 "이 목록에 없는 인용 = 환각"이다. 그러니 답변자만 본 별표4
반환기준으로 641,667원을 계산하면, 비평가는 자기 시야에서 근거를 못 찾고 정확히
이렇게 차단한다 — "제공된 법령 목록에 별표4 반환기준 원문이 없다". 비평가는 옳았고,
구조가 틀렸다.

여기 테스트는 그 비대칭이 다시 생기지 않게 못박는다. 네트워크는 쓰지 않는다.
"""

from __future__ import annotations

from jaramlaw_agent.adversarial_critic import _law_context
from jaramlaw_agent.config import Config
from jaramlaw_agent.models import (
    BYEOLPYO_LIMIT,
    OFFICIAL_TEXT_LIMIT,
    LawArticle,
)
from jaramlaw_agent.openai_client import OpenAiClient

BYEOLPYO_MARKER = "반환액 = 291,667 + 350,000 = 641,667원"


def _answerer() -> OpenAiClient:
    return OpenAiClient(Config(openai_api_key="sk-test", openai_model="gpt-test"), timeout=1.0)


def _byeolpyo_law() -> LawArticle:
    """학원법 시행령 별표4 — 환불액 계산의 유일한 근거."""
    return LawArticle(
        law_id="academy-decree-18",
        law_name="학원의 설립·운영 및 과외교습에 관한 법률 시행령",
        article="제18조 별표4",
        title="학원 수강료 등의 반환기준",
        effective_date="2024-01-01",
        # 별표는 법제처 Open API가 텍스트로 주지 않는다 → 시드 전사본이 사실상 원문.
        text_summary=f"[별표 4] 교습비등 반환기준\n{BYEOLPYO_MARKER}",
        official_text="제18조(교습비등의 반환) ③ 반환사유·금액은 별표 4와 같다.",
        source_url="https://www.law.go.kr/DRF/lawService.do",
        source_mode="live",
    )


def test_별표_전사본이_비평가에게도_전달된다():
    """이 테스트가 깨지면 라이브 답변이 전부 차단된다 (2026-08-06 실사건)."""
    law = _byeolpyo_law()
    critic_view = _law_context([law])
    answer_view = _answerer()._build_context_block([law])

    assert BYEOLPYO_MARKER in answer_view, "답변자가 별표를 못 본다 — 계산 근거 소실"
    assert BYEOLPYO_MARKER in critic_view, (
        "비평가가 별표를 못 본다 — 답변자만 본 계산을 '환각'으로 차단한다"
    )


def test_조문_원문_잘림_기준이_양쪽_동일하다():
    """한쪽만 더 짧게 자르면, 잘린 뒤의 항을 인용한 정상 답변이 환각 판정된다."""
    law = _byeolpyo_law()
    law.article = "제74조"  # 별표가 아닌 일반 조문
    law.text_summary = "요약"
    long_text = "가" * (OFFICIAL_TEXT_LIMIT + 500)
    law.official_text = long_text

    critic_view = _law_context([law])
    answer_view = _answerer()._build_context_block([law])

    kept = "가" * OFFICIAL_TEXT_LIMIT
    overrun = "가" * (OFFICIAL_TEXT_LIMIT + 1)
    for view, who in ((answer_view, "답변자"), (critic_view, "비평가")):
        assert kept in view, f"{who}가 상한보다 짧게 자른다 — 잘린 뒤 항이 환각 판정된다"
        assert overrun not in view, f"{who}가 상한보다 길게 준다"
        assert "이하 생략" in view, f"{who}에게 잘림 표시가 없다 — 끊긴 걸 모른 채 판정한다"


def test_비평가가_보는_법령_수가_답변자보다_적지_않다():
    """비평가 목록이 짧으면, 뒤쪽 법령을 인용한 답변이 근거 없이 차단된다."""
    laws = []
    for i in range(8):
        law = _byeolpyo_law()
        law.article = f"제{i + 1}조"
        law.text_summary = f"본문{i}"
        law.official_text = f"제{i + 1}조 조문원문{i}"
        laws.append(law)

    critic_view = _law_context(laws)
    answer_view = _answerer()._build_context_block(laws)

    for i in range(8):
        assert f"조문원문{i}" in answer_view
        assert f"조문원문{i}" in critic_view, f"{i + 1}번째 법령이 비평가 시야 밖이다"


def test_원문이_없으면_요약을_근거등급과_함께_준다():
    law = _byeolpyo_law()
    law.article = "제5조"
    law.official_text = ""
    law.text_summary = "한부모가족 지원 대상과 범위"

    for view in (_law_context([law]), _answerer()._build_context_block([law])):
        assert "한부모가족 지원 대상과 범위" in view
        assert "원문 아님" in view, "요약을 원문처럼 제시하면 단정 위험이 생긴다"


def test_별표_상한은_전사본을_통째로_담는다():
    """실제 시드 별표(676자)가 잘리면 계산 예시가 사라져 근거가 무너진다."""
    import yaml
    from pathlib import Path

    seed = Path(__file__).resolve().parents[1] / "data/seed/laws/academy-decree-18.yaml"
    summary = yaml.safe_load(seed.read_text(encoding="utf-8"))["text_summary"]
    assert len(summary) <= BYEOLPYO_LIMIT, "별표 전사본이 상한을 넘어 계산 예시가 잘린다"
    assert "641,667원" in summary
