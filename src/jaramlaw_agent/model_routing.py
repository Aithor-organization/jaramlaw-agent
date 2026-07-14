"""모델 라우팅 — 작업 성격에 맞는 LLM을 고르고, 역할 격리를 검증한다.

라우팅 근거는 추측이 아니라 2026-07-14 실측이다. 동일 프롬프트로 4개 모델을
비교했다 (한국어 법령 질의 + 아동 안전 신호 분류 5케이스):

    모델             안전분류   법률정답   지연      추론토큰
    gpt-5.4-nano     5/5       ✅        0.97s     0        ← 최저비용·최속
    gpt-5.6-luna     5/5       ✅        1.08s     0        ← 빠르고 정확
    gpt-5.6-terra    5/5       ✅        1.24s     0        ← 가장 간결한 출력
    gpt-5.6-sol      5/5       ✅        2.55s     54       ← 유일한 추론 모델

읽는 법:
- 분류(라벨 하나 고르기)는 네 모델 모두 만점이었다. 그러면 가장 싸고 빠른
  nano를 쓰는 것이 옳다 — 품질을 잃지 않고 비용만 줄어든다.
- 반면 자유 서술형 법률 답변에서 nano는 조문 세부를 한 번 틀렸다
  (출산전후휴가 90일의 산전/산후 배분). 그래서 nano는 **분류 전용**이고
  부모가 읽을 법률 문장은 절대 쓰지 않는다.
- sol만 추론 토큰을 쓴다. 느리고 비싸지만 깊다 — 안전 신호가 걸렸거나
  전문가 검토가 필요한 국면처럼 틀리면 사람이 다치는 곳에만 배치한다.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Optional

from .models import SafetyRouting


# 작업 성격 → 모델. 환경변수로 개별 교체 가능(모델이 바뀌어도 코드 수정 불필요).
MODEL_TIERS: dict[str, str] = {
    # 라벨 하나 고르기. 정확도 동률이라 최저가로 간다.
    "classify": os.getenv("JARAMLAW_MODEL_CLASSIFY", "gpt-5.4-nano"),
    # 부모가 읽을 일반 상담 답변. 정확 + 빠름 + 추론토큰 0.
    "answer": os.getenv("JARAMLAW_MODEL_ANSWER", "gpt-5.6-luna"),
    # 짧은 정제/요약. 출력 토큰이 가장 적었다.
    "draft": os.getenv("JARAMLAW_MODEL_DRAFT", "gpt-5.6-terra"),
    # 고위험 국면(학교폭력·양육비·어린이집 사고)도 answer와 같은 모델을 쓴다.
    #
    # 처음엔 유일한 추론 모델인 gpt-5.6-sol을 여기 뒀다. 그럴듯했지만 근거가 없었고,
    # 실제로 재보니 값을 못 했다 (고위험 질의 3건, 독립 심판 블라인드 비교):
    #     luna  5.9~9.7초 · 출력 833~1252 · 인용 2~4건 · 1승
    #     sol  11.4~28.8초 · 출력 544~1031 · 인용 1~3건 · 1승
    # 품질은 무승부인데 2~3배 느리다. 게다가 28.8초는 orchestrator 예산(25초)을 넘겨
    # 워크플로우를 통째로 터뜨렸다. 부모를 30초 기다리게 해서 얻는 게 없다.
    # sol이 필요하면 JARAMLAW_MODEL_CRITICAL=gpt-5.6-sol 로 되돌릴 수 있다.
    "critical": os.getenv("JARAMLAW_MODEL_CRITICAL", "gpt-5.6-luna"),
}

# 추론 토큰을 쓰는(= 느리고 비싼) 모델. 예산·지연 추정에 쓴다.
REASONING_MODELS = {"gpt-5.6-sol"}

# 2026-07-14 계정 조회로 확인한 실존 모델. 오타는 런타임 404로만 드러나므로 여기서 먼저 잡는다.
# (실제로 .env에 `gpt-5.6-sola`라는 존재하지 않는 모델이 들어가 있었다 — 올바른 이름은 gpt-5.6-sol.)
KNOWN_MODELS = {
    "gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.4", "gpt-5.4-pro",
    "gpt-5.5", "gpt-5.5-pro",
    "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra",
}


def validate_configured_models() -> list[str]:
    """설정된 모델 중 실존이 확인되지 않은 것을 돌려준다. 빈 리스트면 정상."""
    configured = set(MODEL_TIERS.values())
    pin = os.getenv("JARAMLAW_MODEL_PIN")
    if pin:
        configured.add(pin)
    return sorted(m for m in configured if m not in KNOWN_MODELS)

# criticality가 이 중 하나면 답변을 critical tier로 승격한다.
_ESCALATED = {"critical", "deep"}


def select_model(task: str, criticality: str = "standard") -> str:
    """작업(task)과 국면(criticality)으로 실제 모델 ID를 고른다.

    task:
      - "safety_classify" / "scenario_classify" → 분류 tier (nano)
      - "answer"  → 평시 answer tier(luna), 안전/심층 국면이면 critical tier(sol)
      - "draft"   → draft tier (terra)

    전역 고정은 JARAMLAW_MODEL_PIN 하나뿐이며, 명시적으로 설정할 때만 동작한다.
    (레거시 OPENAI_MODEL은 라우팅을 덮어쓰지 않는다 — 그렇게 두면 분류까지 비싼 모델로
    올라가 라우팅이 있으나 마나가 된다. 실제로 .env에 남아 있던 값 때문에 그런 일이 있었다.)
    """
    pin = os.getenv("JARAMLAW_MODEL_PIN")
    if pin:
        return pin

    if task in ("safety_classify", "scenario_classify", "classify"):
        return MODEL_TIERS["classify"]
    if task == "draft":
        return MODEL_TIERS["draft"]
    if task == "answer":
        if criticality in _ESCALATED:
            return MODEL_TIERS["critical"]
        return MODEL_TIERS["answer"]
    return MODEL_TIERS["answer"]


HIGH_RISK_SCENARIOS = {
    "daycare_accident",
    "school_violence",
    "cyber_bullying",
    "child_support_unpaid",
    "divorce_custody",
}

STANDARD_SCENARIOS = {
    "academy_refund",
    "parental_leave",
}


@dataclass(frozen=True)
class RoleAssignment:
    role: str
    tier: str
    model_family: str
    isolation_group: str
    reason: str
    max_input_chars: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_criticality(
    redacted_input: dict[str, Any],
    safety_routing: Optional[SafetyRouting] = None,
) -> str:
    """Classify the workflow depth without looking at domain-specific outcome."""
    scenario = redacted_input.get("scenario") if isinstance(redacted_input, dict) else {}
    scenario = scenario if isinstance(scenario, dict) else {}
    scenario_type = str(scenario.get("type") or "general")
    query = str(scenario.get("query") or "")

    if safety_routing and safety_routing.triggered:
        return "critical"
    if scenario_type in HIGH_RISK_SCENARIOS:
        return "critical"
    if len(query) > 1800:
        return "deep"
    if scenario_type in STANDARD_SCENARIOS:
        return "standard"
    return "shallow"


def build_role_assignments(criticality: str) -> list[RoleAssignment]:
    """Return a stable routing plan with writer/verifier isolation."""
    base = [
        RoleAssignment(
            role="router",
            tier="shallow",
            model_family="deterministic-router",
            isolation_group="route",
            reason="input classification and workflow selection",
            max_input_chars=3000,
        ),
        RoleAssignment(
            role="law_retrieval_agent",
            tier="standard",
            model_family="deterministic-retrieval",
            isolation_group="retrieval",
            reason="retrieve seed legal anchors",
            max_input_chars=6000,
        ),
        RoleAssignment(
            role="document_drafter_agent",
            tier="standard",
            model_family="deterministic-drafter",
            isolation_group="writer",
            reason="produce structured draft documents",
            max_input_chars=8000,
        ),
        RoleAssignment(
            role="contrarian_verifier",
            tier="deep",
            model_family="deterministic-verifier",
            isolation_group="verifier",
            reason="challenge overreach, missing exceptions, and citation gaps",
            max_input_chars=8000,
        ),
        RoleAssignment(
            role="atomic_claim_verifier",
            tier="deep",
            model_family="deterministic-verifier",
            isolation_group="verifier",
            reason="verify citation completeness for every atomic claim",
            max_input_chars=8000,
        ),
        RoleAssignment(
            role="independent_validator",
            tier="critical",
            model_family="deterministic-independent-review",
            isolation_group="independent-validation",
            reason="validate final report after writer/verifier loop",
            max_input_chars=12000,
        ),
    ]

    if criticality == "shallow":
        return base[:4]
    if criticality == "standard":
        return base[:5]
    return base


def validate_model_assignments(assignments: list[RoleAssignment]) -> dict[str, Any]:
    """Enforce role isolation before the workflow proceeds."""
    by_role = {item.role: item for item in assignments}
    findings: list[dict[str, str]] = []

    writer = by_role.get("document_drafter_agent")
    verifier = by_role.get("atomic_claim_verifier") or by_role.get("contrarian_verifier")
    independent = by_role.get("independent_validator")

    if writer and verifier and writer.isolation_group == verifier.isolation_group:
        findings.append({
            "severity": "block",
            "code": "writer_verifier_not_isolated",
            "message": "writer and verifier share an isolation group",
        })

    if independent and verifier and independent.isolation_group == verifier.isolation_group:
        findings.append({
            "severity": "block",
            "code": "validator_not_independent",
            "message": "independent validator must not share verifier isolation",
        })

    return {
        "status": "BLOCK" if any(item["severity"] == "block" for item in findings) else "PASS",
        "findings": findings,
    }


def plan_model_routing(
    redacted_input: dict[str, Any],
    safety_routing: Optional[SafetyRouting] = None,
    llm_enabled: bool = False,
) -> dict[str, Any]:
    """이번 실행에서 어떤 모델을 어디에 쓸지 결정하고, 그 사실을 그대로 기록한다.

    `llm_enabled`는 호출자(orchestrator)가 실제 LLM 사용 가능 여부를 넘긴다.
    이전 구현은 이 값을 항상 False로 기록했는데, 그 사이 OpenAI를 호출하고 있었다.
    감사 로그가 사실과 어긋나면 감사 로그가 아니다.
    """
    criticality = classify_criticality(redacted_input, safety_routing)
    assignments = build_role_assignments(criticality)
    guard = validate_model_assignments(assignments)

    answer_model = select_model("answer", criticality)
    selection = {
        "safety_classifier": select_model("safety_classify"),
        "answer": answer_model,
        "draft": select_model("draft"),
    }
    return {
        "routing_version": "jaramlaw-model-routing/v2",
        "criticality": criticality,
        "execution_mode": "llm-routed" if llm_enabled else "deterministic-local",
        "external_model_calls": bool(llm_enabled),
        "selected_models": selection,
        "answer_model": answer_model,
        "answer_uses_reasoning": answer_model in REASONING_MODELS,
        "escalated": criticality in _ESCALATED,
        "assignments": [item.to_dict() for item in assignments],
        "model_guard": guard,
    }
