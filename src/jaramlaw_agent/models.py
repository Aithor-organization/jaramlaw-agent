"""자람법 도메인 모델 — 데이터클래스 정의.

모든 출력은 JSON 직렬화 가능. PII는 입력 단계에서 이미 마스킹된 상태.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


class LifeStage(str, Enum):
    PREGNANCY = "pregnancy"
    INFANT = "infant"          # 만 0세
    TODDLER = "toddler"        # 만 1-2세
    PRESCHOOL = "preschool"    # 만 3-5세
    ELEMENTARY = "elementary"  # 만 6-11세
    MIDDLE = "middle"          # 만 12-14세
    HIGH = "high"              # 만 15-17세
    ADULT_CHILD = "adult_child"  # 만 18세+
    UNKNOWN = "unknown"


@dataclass
class Parent:
    role: str  # mother | father | guardian
    age: int
    employment: Optional[str] = None
    region_code: Optional[str] = None  # 행정구역 코드 (KOSIS)


@dataclass
class Child:
    name_masked: str  # "C1", "C2" — 절대 실명 보유 X
    birth_date: Optional[str] = None  # ISO date string
    expected_birth_date: Optional[str] = None
    pregnancy_week: Optional[int] = None
    sex: Optional[str] = None  # M | F | unknown
    facility: Optional[str] = None
    disability: bool = False


@dataclass
class LifeEvent:
    type: str  # pregnancy | birth | divorce | school_entry | ...
    date: str  # ISO date string


@dataclass
class FamilyProfile:
    parents: list[Parent] = field(default_factory=list)
    children: list[Child] = field(default_factory=list)
    events: list[LifeEvent] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    life_stages: list[str] = field(default_factory=list)  # child별 stage
    income_decile: Optional[int] = None  # 1-10 (10이 최상위)
    reference_date: Optional[str] = None  # 기준일 (기본 today)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LegalBasis:
    law: str
    article: str
    effective_date: str
    source_url: str = ""

    def is_complete(self) -> bool:
        return bool(self.law and self.article and self.effective_date)


@dataclass
class LawArticle:
    law_id: str
    law_name: str
    article: str
    title: str
    effective_date: str
    text_summary: str
    source_url: str = ""
    applies_to_personas: list[str] = field(default_factory=list)
    applies_to_life_stages: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    related_rights_cards: list[str] = field(default_factory=list)
    related_supports: list[str] = field(default_factory=list)
    related_documents: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    violation_penalty: dict[str, Any] = field(default_factory=dict)
    report_channel: Optional[str] = None
    contact: Optional[str] = None
    emergency_contact: Optional[str] = None
    calendar_template: Optional[str] = None
    notes: Optional[str] = None
    calculation: dict[str, Any] = field(default_factory=dict)
    report_channels: list[str] = field(default_factory=list)
    # 매칭 점수 (retrieval 단계에서 부여)
    relevance_score: float = 0.0
    applies_reason: list[str] = field(default_factory=list)

    def to_legal_basis(self) -> LegalBasis:
        return LegalBasis(
            law=self.law_name,
            article=self.article,
            effective_date=self.effective_date,
            source_url=self.source_url,
        )


@dataclass
class SupportMatch:
    support_id: str
    name: str
    amount_krw: int
    amount_description: str
    condition_summary: str
    legal_basis: LegalBasis
    application_channel: str
    deadline_days_left: Optional[int] = None
    deadline_kind: Optional[str] = None
    eligibility_evidence: list[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class RightsCard:
    card_id: str
    title: str
    holder: str
    legal_basis: LegalBasis
    denial: dict[str, Any] = field(default_factory=dict)
    example_denial: Optional[str] = None
    qr_link_optional: Optional[str] = None
    disclaimer: str = (
        "본 카드는 법률 자문이 아닙니다. 권리 행사 시 전문가 상담을 권장합니다."
    )


@dataclass
class CalendarEvent:
    kind: str  # health_checkup | vaccination | school_entry | support_transition
    title: str
    legal_basis: Optional[LegalBasis] = None
    scheduled_date: Optional[str] = None  # ISO date string
    target_age_months: Optional[int] = None
    target_age_years: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class CalendarOutput:
    events: list[CalendarEvent] = field(default_factory=list)
    ical_export: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [asdict(e) for e in self.events],
            "ical_export": self.ical_export,
        }


@dataclass
class DraftDocument:
    doc_id: str
    title: str
    kind: str  # refund_request | accident_report_demand | parental_leave_application | cctv_access | school_violence_report
    body_markdown: str
    legal_basis: list[LegalBasis] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    signature_required: bool = True
    attachment_required: list[str] = field(default_factory=list)
    calculation_breakdown: dict[str, Any] = field(default_factory=dict)


@dataclass
class AtomicClaim:
    claim_id: str
    statement: str
    source_node: str  # board_opinions | draft_documents | support_matches | rights_cards
    citation: Optional[LegalBasis] = None
    status: str = "unverifiable"  # verified | partial | unverifiable
    reasoning: str = ""


@dataclass
class VerifierResults:
    atomic_claims: list[AtomicClaim] = field(default_factory=list)
    verified_count: int = 0
    partial_count: int = 0
    unverifiable_count: int = 0
    verified_ratio: float = 0.0

    def summarize(self) -> dict[str, Any]:
        total = len(self.atomic_claims)
        return {
            "total": total,
            "verified": self.verified_count,
            "partial": self.partial_count,
            "unverifiable": self.unverifiable_count,
            "verified_ratio": self.verified_ratio,
        }


@dataclass
class SafetyRouting:
    triggered: bool = False
    category: Optional[str] = None  # child_abuse_suspected | medical_emergency | ...
    contact: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class HumanReviewSection:
    needed: bool = False
    reason: Optional[str] = None
    recommended_experts: list[dict[str, str]] = field(default_factory=list)
    disclaimer: str = (
        "본 서비스는 양육 정보 보조 도구이며, 구체 사안에 대한 법률 자문이 아닙니다. "
        "위 안내는 전문 상담을 받을 채널을 제안할 뿐입니다."
    )


@dataclass
class FinalReport:
    """워크플로우 최종 출력. JSON 직렬화 가능."""

    family_profile: FamilyProfile
    life_stages: list[str] = field(default_factory=list)
    matched_laws: list[LawArticle] = field(default_factory=list)
    support_matches: list[SupportMatch] = field(default_factory=list)
    rights_cards: list[RightsCard] = field(default_factory=list)
    calendar: Optional[CalendarOutput] = None
    draft_documents: list[DraftDocument] = field(default_factory=list)
    verifier_results: Optional[VerifierResults] = None
    safety_routing: Optional[SafetyRouting] = None
    human_review: Optional[HumanReviewSection] = None
    audit_log_id: Optional[str] = None
    disclaimer: str = (
        "※ 본 서비스는 양육 정보 보조 도구이며, "
        "구체 사안에 대한 법률 자문이 아닙니다."
    )
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    scenario_id: Optional[str] = None
    workflow_version: str = "family-legal-jaramlaw/v1"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
