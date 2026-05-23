"""human_review — 고위험·저신뢰 claim 발견 시 전문가 상담 라우팅.

Constitution 원칙 1 (변호사법 회피) 강제: 자람법이 직접 자문하지 않고 전문가에 라우팅.
"""

from __future__ import annotations

from typing import Any, Optional

from .models import (
    HumanReviewSection,
    SafetyRouting,
    VerifierResults,
)


EXPERT_CONTACTS = {
    "lawyer_family": {
        "kind": "변호사 (가정법률)",
        "contact_info": "대한법률구조공단 132 / 가정법률상담소 1577-2210",
        "cost_estimate": "초기 무료 상담 가능 (기준중위소득 125% 이하)",
    },
    "labor_consultant": {
        "kind": "노무사 / 고용노동부",
        "contact_info": "고용노동부 1350",
        "cost_estimate": "1350 무료 상담",
    },
    "child_protection": {
        "kind": "아동보호전문기관",
        "contact_info": "아이지킴이 콜 1577-1391 / 112",
        "cost_estimate": "무료",
    },
    "consumer_protection": {
        "kind": "소비자상담 / 한국소비자원",
        "contact_info": "1372 소비자상담센터",
        "cost_estimate": "무료",
    },
    "child_support_office": {
        "kind": "양육비이행관리원",
        "contact_info": "1644-6621",
        "cost_estimate": "무료 (소득기준 차등 법률구조)",
    },
    "school_violence_office": {
        "kind": "학교폭력 신고센터",
        "contact_info": "117 (24시간)",
        "cost_estimate": "무료",
    },
    "daycare_office": {
        "kind": "거주지 시·군·구 보육과 / 어린이집안전공제회",
        "contact_info": "거주지 행정복지센터",
        "cost_estimate": "무료",
    },
}


def determine_human_review(
    verifier_results: Optional[VerifierResults],
    safety_routing: Optional[SafetyRouting],
    scenario_type: Optional[str] = None,
) -> HumanReviewSection:
    """검증 결과 + safety 라우팅 + 시나리오 유형 → 전문가 추천 묶음."""
    reasons: list[str] = []
    experts: list[dict[str, str]] = []
    needed = False

    # 1) safety 라우팅 발동 → 카테고리별 전문가
    if safety_routing and safety_routing.triggered:
        needed = True
        if safety_routing.category == "child_abuse_suspected":
            experts.append(EXPERT_CONTACTS["child_protection"])
            reasons.append(f"safety 신호 '{safety_routing.category}'")
        elif safety_routing.category == "medical_emergency":
            experts.append({
                "kind": "응급의료",
                "contact_info": "119",
                "cost_estimate": "응급 — 즉시 호출",
            })
            reasons.append("의료 응급 신호")
        elif safety_routing.category == "self_harm_signal":
            experts.append({
                "kind": "자살예방상담",
                "contact_info": "1393",
                "cost_estimate": "무료 (24시간)",
            })
            reasons.append("자해 신호")
        elif safety_routing.category == "domestic_violence":
            experts.append({
                "kind": "여성긴급전화",
                "contact_info": "1366",
                "cost_estimate": "무료",
            })
            reasons.append("가정폭력 신호")

    # 2) 검증 부족 (unverifiable_count > 0)
    if verifier_results and verifier_results.unverifiable_count > 0:
        needed = True
        reasons.append(
            f"검증 부족 claim {verifier_results.unverifiable_count}건 — 전문가 상담 권장"
        )
        # 일반 변호사 추천
        if EXPERT_CONTACTS["lawyer_family"] not in experts:
            experts.append(EXPERT_CONTACTS["lawyer_family"])

    # 3) 시나리오별 추천
    if scenario_type:
        mapping = {
            "academy_refund": "consumer_protection",
            "school_violence": "school_violence_office",
            "daycare_accident": "daycare_office",
            "parental_leave_denied": "labor_consultant",
            "child_support_unpaid": "child_support_office",
            "divorce_custody": "lawyer_family",
            "cyber_bullying": "school_violence_office",
        }
        key = mapping.get(scenario_type)
        if key and EXPERT_CONTACTS[key] not in experts:
            experts.append(EXPERT_CONTACTS[key])
            if not needed:
                needed = True
                reasons.append(f"시나리오 유형 '{scenario_type}' — 관련 전문 채널 안내")

    return HumanReviewSection(
        needed=needed,
        reason="; ".join(reasons) if reasons else None,
        recommended_experts=experts,
    )
