"""rights_card — 매칭된 법령 → 권리 카드 자동 생성.

(F6 권리 카드)
"""

from __future__ import annotations

from typing import Optional

from .models import FamilyProfile, LawArticle, LegalBasis, RightsCard


# 시드 라이브러리 — 법령 → 권리카드 변환 규칙
RIGHTS_CARD_LIBRARY: dict[str, dict] = {
    "maternity-leave-90d": {
        "title": "출산휴가 90일 권리 (다태아 120일)",
        "holder": "임신 중인 여성근로자 (5인 미만 사업장 포함)",
        "law_id": "labor-standards-74",
        "report_channel": "고용노동부 1350",
        "example_denial": "회사가 '경영 사정상 또는 우리 규정상 안 된다'며 거부 — 위반",
    },
    "prenatal-checkup-leave": {
        "title": "임산부 정기 검진 휴가 권리",
        "holder": "임신 중인 여성근로자",
        "law_id": "labor-standards-74-2",
        "report_channel": "고용노동부 1350",
        "example_denial": "검진 시간 무급 처리 또는 거부 — 위반",
    },
    "spouse-birth-leave": {
        "title": "배우자 출산휴가 20일 권리",
        "holder": "출산 배우자가 있는 근로자 (성별 무관)",
        "law_id": "equal-employment-18-2",
        "report_channel": "고용노동부 1350",
        "example_denial": "회사가 '남자는 사용 안 한다'며 거부 — 위반",
    },
    "parental-leave-1y": {
        "title": "육아휴직 1년 6개월 권리 (3회 분할)",
        "holder": "만 8세 이하 또는 초2 이하 자녀 양육 근로자 (성별 무관)",
        "law_id": "equal-employment-19",
        "report_channel": "고용노동부 1350 / 노동위원회 구제신청",
        "example_denial": "회사가 '남자가 육아휴직? 안 된다' 또는 '5인 미만이라 안 된다' — 위반",
    },
    "family-care-leave": {
        "title": "가족돌봄휴가 연 10일 권리 (자녀 추가 10일)",
        "holder": "근로자 (조부모/부모/배우자/자녀 돌봄)",
        "law_id": "equal-employment-22-2",
        "report_channel": "고용노동부 1350",
        "example_denial": "회사가 '사적인 일'이라며 거부 — 위반",
    },
    "daycare-safety-report": {
        "title": "어린이집 안전사고 보고 받을 권리",
        "holder": "어린이집 영유아의 보호자",
        "law_id": "childcare-33-3",
        "report_channel": "거주지 시·군·구 보육과 / 어린이집안전공제회",
        "example_denial": "어린이집이 사고 경위서 작성·제공 거부 — 위반",
    },
    "daycare-cctv-access": {
        "title": "어린이집 CCTV 영상 열람 권리",
        "holder": "어린이집 영유아의 보호자",
        "law_id": "childcare-15-5",
        "report_channel": "거주지 시·군·구 보육과",
        "example_denial": "어린이집이 정당한 사유 없이 열람 거부 — 위반",
    },
    "abuse-report-obligation": {
        "title": "아동학대 신고 권리 / 의무 신고자 의무",
        "holder": "누구나 신고 가능 / 의료인·어린이집 종사자 등은 신고 의무",
        "law_id": "child-abuse-10",
        "report_channel": "아이지킴이 콜 1577-1391 / 112",
        "example_denial": "(신고자 비밀 보장 — 아동학대처벌법 제62조)",
    },
    "minor-consent-14": {
        "title": "만 14세 미만 자녀 개인정보 법정대리인 동의권",
        "holder": "만 14세 미만 자녀의 법정대리인",
        "law_id": "itnet-31",
        "report_channel": "개인정보보호위원회 / 한국인터넷진흥원 118",
        "example_denial": "정보통신서비스가 법정대리인 동의 없이 자녀 정보 수집 — 위반",
    },
    "child-support-enforcement": {
        "title": "양육비 이행확보 권리",
        "holder": "양육비채권자 (이혼 후 자녀 직접 양육 부모)",
        "law_id": "child-support-enforcement",
        "report_channel": "양육비이행관리원 1644-6621",
        "example_denial": "전 배우자가 양육비 미지급 → 직접지급명령·감치·운전면허정지 가능",
    },
    "school-violence-procedure": {
        "title": "학교폭력 신고·심의 절차 권리",
        "holder": "학생 본인 또는 보호자, 목격자 누구나",
        "law_id": "school-violence-12-17",
        "report_channel": "학교폭력 신고 117 / 학교장 / 교육지원청",
        "example_denial": "학교가 학폭위 미개최 또는 자체해결 강요 — 위반",
    },
}


def _find_law(law_id: str, matched_laws: list[LawArticle]) -> Optional[LawArticle]:
    for law in matched_laws:
        if law.law_id == law_id:
            return law
    return None


def generate_rights_cards(
    matched_laws: list[LawArticle],
    family_profile: FamilyProfile,
) -> list[RightsCard]:
    """매칭된 법령에서 connect된 권리카드를 모두 생성. citation 완전한 것만 포함."""
    cards: list[RightsCard] = []
    seen_ids: set[str] = set()

    for law in matched_laws:
        for card_id in law.related_rights_cards:
            if card_id in seen_ids:
                continue
            if card_id not in RIGHTS_CARD_LIBRARY:
                continue
            lib = RIGHTS_CARD_LIBRARY[card_id]
            base_law = _find_law(lib["law_id"], matched_laws)
            if not base_law:
                # base law이 retrieval에 없으면 카드 생성 안 함 (citation 강제)
                continue
            legal_basis = base_law.to_legal_basis()
            if not legal_basis.is_complete():
                continue

            penalty_data = base_law.violation_penalty or {}
            denial = {
                "violation": penalty_data.get("description", "관련 조문 위반"),
                "penalty_summary": penalty_data.get("penalty", ""),
                "report_channel": lib.get("report_channel") or penalty_data.get("report_channel", ""),
            }

            card = RightsCard(
                card_id=card_id,
                title=lib["title"],
                holder=lib["holder"],
                legal_basis=legal_basis,
                denial=denial,
                example_denial=lib.get("example_denial"),
                qr_link_optional=legal_basis.source_url,
            )
            cards.append(card)
            seen_ids.add(card_id)
    return cards


def render_card_markdown(card: RightsCard) -> str:
    """권리카드 → 1장짜리 markdown (인쇄/카톡 전송 가능)."""
    lb = card.legal_basis
    lines = [
        f"# 📋 {card.title}",
        "",
        f"**대상**: {card.holder}",
        "",
        "## 근거 법령",
        f"- **법령**: {lb.law}",
        f"- **조문**: {lb.article}",
        f"- **시행일**: {lb.effective_date}",
        f"- **출처**: {lb.source_url}" if lb.source_url else "",
        "",
        "## 위반 시 신고",
    ]
    denial = card.denial
    if denial.get("violation"):
        lines.append(f"- **위반 조항**: {denial['violation']}")
    if denial.get("penalty_summary"):
        lines.append(f"- **제재**: {denial['penalty_summary']}")
    if denial.get("report_channel"):
        lines.append(f"- **신고처**: {denial['report_channel']}")
    if card.example_denial:
        lines.extend(["", "## 거부 사례 예시", f"> {card.example_denial}"])
    lines.extend([
        "",
        "---",
        f"> {card.disclaimer}",
    ])
    return "\n".join(line for line in lines if line is not None)
