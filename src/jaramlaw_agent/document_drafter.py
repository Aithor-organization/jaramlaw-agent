"""document_drafter — 신청서·신고서·환불요청서 초안 markdown 생성기.

(F4 분쟁 자가진단 + 신고 워크플로우의 산출물)

Constitution 원칙 1: 모든 초안 상단 disclaimer 자동 삽입
Constitution 원칙 4: 자동 발사 금지 — "초안" 라벨 명시
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from . import DISCLAIMER
from .family_context import _parse_iso_date
from .law_retrieval import load_all_laws
from .models import DraftDocument, FamilyProfile, LawArticle, LegalBasis


def _law_to_basis(law: LawArticle) -> LegalBasis:
    return LegalBasis(
        law=law.law_name, article=law.article,
        effective_date=law.effective_date, source_url=law.source_url,
    )


def _find_law_by_id(law_id: str, laws: list[LawArticle]) -> Optional[LawArticle]:
    for law in laws:
        if law.law_id == law_id:
            return law
    return None


# === 1. 학원 환불 요청서 ===


def compute_academy_refund(
    total_paid_krw: int,
    days_used: int,
    total_days: int,
) -> dict[str, Any]:
    """학원법 시행령 제18조 별표4 — 일할 계산.

    교습 기간 1개월 초과:
      refund = paid * (remaining_days / total_days)
    교습 기간 1개월 이내:
      refund = paid * (remaining_days / total_days) — 동일 적용
    """
    if total_days <= 0:
        raise ValueError("total_days must be > 0")
    remaining_days = max(0, total_days - days_used)
    refund_raw = total_paid_krw * remaining_days / total_days
    # 정수 원 단위 반올림
    refund = round(refund_raw)
    return {
        "total_paid_krw": total_paid_krw,
        "days_used": days_used,
        "total_days": total_days,
        "remaining_days": remaining_days,
        "refund_raw": refund_raw,
        "refund_krw": refund,
        "formula": "refund = paid * (remaining_days / total_days)",
    }


def _missing_refund_facts(paid: int, total_days: int) -> list[str]:
    """환불 계산에 필요한데 사용자가 주지 않은 항목."""
    missing = []
    if paid <= 0:
        missing.append("total_paid_krw")
    if total_days <= 0:
        missing.append("total_days")
    return missing


def draft_academy_refund_request(
    profile: FamilyProfile,
    scenario_data: dict[str, Any],
    laws: Optional[list[LawArticle]] = None,
) -> DraftDocument:
    laws = laws or load_all_laws()
    base_law = _find_law_by_id("academy-decree-18", laws)
    if not base_law:
        raise ValueError("필수 시드 누락: academy-decree-18")

    paid = int(scenario_data.get("total_paid_krw", 0))
    days_used = int(scenario_data.get("days_used", 0))
    total_days = int(scenario_data.get("total_days", 0))

    # 결제금액·교습일수를 사용자가 주지 않았으면 환불액을 계산하지 않는다.
    # 예시값으로 채워 넣으면 그럴듯하지만 사실이 아닌 금액이 문서에 박힌다.
    facts_supplied = paid > 0 and total_days > 0
    calc: dict[str, Any] = (
        compute_academy_refund(paid, days_used, total_days)
        if facts_supplied
        else {"status": "insufficient_facts", "missing": _missing_refund_facts(paid, total_days)}
    )

    if facts_supplied:
        amount_section = f"""- 환불 산식: `{calc['formula']}`
- 잔여 교습일수: {calc['remaining_days']}일
- **환불 청구금액: {calc['refund_krw']:,}원**
  (= {paid:,} × {calc['remaining_days']} / {total_days})"""
        facts_section = f"""- 결제금액: **{paid:,}원** ({scenario_data.get('months_paid', '')}개월분)
- 사용 일수: **{days_used}일** (총 {total_days}일 중)"""
    else:
        amount_section = """> ⚠️ **환불 금액을 계산하지 않았습니다.**
> 결제금액과 교습 총일수가 입력되지 않아, 임의의 값을 넣는 대신 비워 두었습니다.
> 아래 사실관계를 채우면 학원법 시행령 제18조 별표4 기준으로 자동 계산됩니다.
>
> - 결제금액(원): ______
> - 교습 총일수: ______
> - 사용 일수: ______
>
> 산식: `환불액 = 결제금액 × (총일수 − 사용일수) / 총일수`"""
        facts_section = """- 결제금액: ______원 (미입력)
- 사용 일수: ______일 (총 ______일 중) (미입력)"""

    today = date.today().isoformat()
    body = f"""# 학원 수강료 환불 요청서 (초안)

> {DISCLAIMER}
> ⚠️ 본 문서는 초안입니다. 사실관계를 본인이 검토·수정 후 발송하세요.

---

## 수신
**{scenario_data.get('academy_name', '○○학원')} 귀하**

## 발신
- 보호자 성명: (서명 또는 인)
- 학생: 자녀 {profile.children[0].name_masked if profile.children else 'C1'}
- 연락처: ___
- 작성일: {today}

## 1. 사실관계
- 결제일: {scenario_data.get('payment_date', '')}
- 교습 시작일: {scenario_data.get('use_start_date', '')}
{facts_section}
- 환불 요청일: {scenario_data.get('cancellation_request_date', today)}
- 학원 답변: "{scenario_data.get('refusal_text', '환불 불가')}"

## 2. 청구 근거

**{base_law.law_name} {base_law.article}** ({base_law.title})
> {base_law.text_summary.strip()}

본 조문 별표4의 환불 기준에 따라 사용일수를 일할 계산하여 환불을 청구합니다.

## 3. 환불 금액 계산

{amount_section}

## 4. 회신 기한

본 요청서 도달일로부터 **7일 이내** 환불 처리를 요청드립니다.
미회신 또는 거부 시 다음 조치를 진행할 예정임을 알려드립니다.

## 5. 미회신 시 후속 조치

1. 1372 소비자상담센터 (한국소비자원) 분쟁조정 신청
2. 관할 시·도 교육청 학원민원 접수 ({base_law.report_channels[0] if base_law.report_channels else '관할 교육지원청'})
3. 한국소비자원 분쟁조정
4. 소액사건심판 (140만원 이하)

---

> 본 초안의 법적 효력은 발신인 서명·발송으로 발생합니다. 송달 증빙(내용증명·등기우편)을 권장합니다.

출처: {base_law.source_url}
"""
    return DraftDocument(
        doc_id=f"academy-refund-{date.today().isoformat()}",
        title=f"학원 수강료 환불 요청서 — {scenario_data.get('academy_name', '○○학원')}",
        kind="refund_request",
        body_markdown=body,
        legal_basis=[_law_to_basis(base_law)],
        next_actions=[
            "내용증명 또는 등기우편으로 발송 (송달 증빙 확보)",
            "회신 기한(7일) 후 미회신 시 1372 소비자상담",
            "필요 시 시도교육청 학원민원 접수",
        ],
        signature_required=True,
        attachment_required=[
            "결제 영수증 사본",
            "수강 등록서 사본",
            "환불 거부 통보 사본 (있는 경우)",
        ],
        calculation_breakdown=calc,
    )


# === 2. 어린이집 사고 경위서 요구서 ===


def draft_daycare_accident_report_demand(
    profile: FamilyProfile,
    scenario_data: dict[str, Any],
    laws: Optional[list[LawArticle]] = None,
) -> DraftDocument:
    laws = laws or load_all_laws()
    safety_law = _find_law_by_id("childcare-33-3", laws)
    if not safety_law:
        raise ValueError("필수 시드 누락: childcare-33-3")

    child = profile.children[0] if profile.children else None
    cname = child.name_masked if child else "C1"
    today = date.today().isoformat()

    body = f"""# 어린이집 안전사고 경위서 제공 요청서 (초안)

> {DISCLAIMER}

## 수신
**(어린이집명) 원장 귀하**

## 발신
- 보호자: 자녀 {cname}의 부 / 모
- 작성일: {today}

## 1. 사고 개요
- 어린이집 알림: "{scenario_data.get('notification_text', '')}"
- 부모 관찰: "{scenario_data.get('parent_observation', '')}"

## 2. 요청 근거

**{safety_law.law_name} {safety_law.article}** ({safety_law.title})
> {safety_law.text_summary.strip()}

본 조문에 따라 어린이집 운영자는 안전사고 발생 시 사고 경위·결과를 기록하여 보호자에게 알리고 지자체에 보고할 의무가 있습니다.

## 3. 요청 사항
1. **사고 경위서** 서면 제공 (사고 일시·장소·경위·응급조치·후속 조치 포함)
2. 어린이집의 **지자체 보고서 사본** 제공
3. **CCTV 영상 열람** 협조 (별도 신청서 첨부 가능, 영유아보육법 제15조의5)

## 4. 회신 기한

본 요청서 도달일로부터 **7일 이내** 사고 경위서 제공을 요청합니다.

## 5. 미회신 시 후속 조치
1. 거주지 시·군·구 보육과 신고 (영유아보육법 위반)
2. 어린이집안전공제회 사고 신고 및 보상 신청
3. 의심 정황 시 아이지킴이 콜 **1577-1391** 또는 112 신고

---

> {safety_law.violation_penalty.get('penalty', '')}

출처: {safety_law.source_url}
"""
    legal_bases = [_law_to_basis(safety_law)]
    cctv_law = _find_law_by_id("childcare-15-5", laws)
    if cctv_law:
        legal_bases.append(_law_to_basis(cctv_law))

    return DraftDocument(
        doc_id=f"daycare-accident-demand-{today}",
        title=f"어린이집 안전사고 경위서 제공 요청서 — 자녀 {cname}",
        kind="accident_report_demand",
        body_markdown=body,
        legal_basis=legal_bases,
        next_actions=[
            "어린이집 원장에게 직접 전달 또는 등기 발송",
            "7일 내 미회신 시 거주지 시·군·구 보육과 신고",
            "학대 의심 시 1577-1391",
        ],
        signature_required=True,
        attachment_required=["진단서 (병원 진료 후)", "사고 발생 시 받은 알림 메시지 사본"],
    )


# === 3. CCTV 열람 신청서 ===


def draft_cctv_access_request(
    profile: FamilyProfile,
    scenario_data: dict[str, Any],
    laws: Optional[list[LawArticle]] = None,
) -> DraftDocument:
    laws = laws or load_all_laws()
    base_law = _find_law_by_id("childcare-15-5", laws)
    if not base_law:
        raise ValueError("필수 시드 누락: childcare-15-5")

    child = profile.children[0] if profile.children else None
    cname = child.name_masked if child else "C1"
    today = date.today().isoformat()

    body = f"""# 어린이집 CCTV 영상정보 열람 신청서 (초안)

> {DISCLAIMER}

## 수신
**(어린이집명) 원장 귀하**

## 발신
- 보호자: 자녀 {cname}의 부 / 모
- 작성일: {today}

## 1. 신청 근거

**{base_law.law_name} {base_law.article}** ({base_law.title})
> {base_law.text_summary.strip()}

본 조문에 따라 보호자는 보육 중 안전사고 또는 아동학대가 의심되는 경우 등에 영상정보 열람을 요청할 권리가 있으며, 어린이집 운영자는 정당한 사유 없이 거부할 수 없습니다.

## 2. 열람 요청 영상
- 자녀: {cname}
- 사고 일시: (시각 명시)
- 보육실 위치: ___
- 사유: "{scenario_data.get('parent_observation', '안전사고 의심')}"

## 3. 열람 방식
- [x] 어린이집 내 방문 열람
- [ ] 정보주체 동의를 받은 사본 제공 (다른 영유아 모자이크 처리 후)

## 4. 회신 기한
본 신청서 도달일로부터 **3일 이내** 열람 일정 안내를 요청합니다.

## 5. 거부 시 조치
정당한 사유 없는 거부는 영유아보육법 위반이며, 거주지 시·군·구 보육과에 민원을 제기할 예정입니다.

---

> 본 신청서는 영유아보육법 제15조의5에 근거합니다.

출처: {base_law.source_url}
"""
    return DraftDocument(
        doc_id=f"cctv-access-{today}",
        title=f"CCTV 영상 열람 신청서 — 자녀 {cname}",
        kind="cctv_access",
        body_markdown=body,
        legal_basis=[_law_to_basis(base_law)],
        next_actions=[
            "어린이집 원장에 직접 제출",
            "거부 시 거주지 시·군·구 보육과 신고",
        ],
        signature_required=True,
        attachment_required=["보호자 신분증 사본"],
    )


# === 4. 육아휴직 신청서 ===


def draft_parental_leave_application(
    profile: FamilyProfile,
    scenario_data: dict[str, Any],
    laws: Optional[list[LawArticle]] = None,
) -> DraftDocument:
    laws = laws or load_all_laws()
    base_law = _find_law_by_id("equal-employment-19", laws)
    if not base_law:
        raise ValueError("필수 시드 누락: equal-employment-19")
    penalty_law = _find_law_by_id("equal-employment-37", laws)

    today = date.today().isoformat()
    body = f"""# 육아휴직 신청서 (초안)

> {DISCLAIMER}

## 수신
**(소속 회사 인사담당자) 귀하**

## 발신
- 성명: ___ (서명 또는 인)
- 부서·직급: ___
- 작성일: {today}

## 1. 신청 근거

**{base_law.law_name} {base_law.article}** ({base_law.title})
> {base_law.text_summary.strip()}

본 조문에 따라 만 8세 이하 또는 초2 이하 자녀를 양육하는 근로자(성별 무관)는 육아휴직을 신청할 권리가 있으며, 사업주는 이를 허용해야 합니다.

## 2. 신청 내역
- 자녀: ___ (생년월일)
- 휴직 시작 희망일: ___
- 휴직 기간: ___ (최대 1년 6개월, 3회 분할 사용 가능)

## 3. 거부 시 후속 조치
- 1차: 사업주 서면 답변 요구
- 2차: **고용노동부 1350 진정** (벌금 500만원 이하 — {penalty_law.article if penalty_law else '남녀고용평등법 제37조'})
- 3차: 노동위원회 부당해고·부당전직 구제신청

---

> 본 초안은 법률 자문이 아닙니다. 회사 사규와 함께 검토 후 사용하세요.

출처: {base_law.source_url}
"""
    bases = [_law_to_basis(base_law)]
    if penalty_law:
        bases.append(_law_to_basis(penalty_law))

    return DraftDocument(
        doc_id=f"parental-leave-{today}",
        title="육아휴직 신청서",
        kind="parental_leave_application",
        body_markdown=body,
        legal_basis=bases,
        next_actions=[
            "사업주에게 서면 제출 (사본 보관)",
            "거부 시 고용노동부 1350 진정",
        ],
        signature_required=True,
        attachment_required=["가족관계증명서", "주민등록등본"],
    )


# === 5. 학교폭력 신고서 (skeleton — MVP 후속) ===


def draft_school_violence_report(
    profile: FamilyProfile,
    scenario_data: dict[str, Any],
    laws: Optional[list[LawArticle]] = None,
) -> DraftDocument:
    laws = laws or load_all_laws()
    base_law = _find_law_by_id("school-violence-12-17", laws)
    if not base_law:
        raise ValueError("필수 시드 누락: school-violence-12-17")
    today = date.today().isoformat()

    body = f"""# 학교폭력 신고서 (초안 skeleton)

> {DISCLAIMER}

## 수신
**(학교명) 학교장 귀하 / 교육지원청 학교폭력 신고센터**

## 발신
- 보호자: ___
- 학생: ___ (학년·반)
- 작성일: {today}

## 1. 신고 근거

**{base_law.law_name} {base_law.article}** ({base_law.title})
> {base_law.text_summary.strip()}

## 2. 사안 개요
- 사건 일시·장소: ___
- 가해 추정 학생: ___
- 피해 내용: ___
- 증거자료 첨부 여부: ___

## 3. 요청 사항
1. 사안조사 즉시 착수
2. 학교장 자체해결 또는 학폭위 심의 진행
3. 피해 학생 보호 조치

---

출처: {base_law.source_url}
"""
    return DraftDocument(
        doc_id=f"school-violence-{today}",
        title="학교폭력 신고서 (초안)",
        kind="school_violence_report",
        body_markdown=body,
        legal_basis=[_law_to_basis(base_law)],
        next_actions=[
            "학교 또는 학교폭력 신고 117",
            "필요 시 전문 변호사 상담",
        ],
        signature_required=True,
        attachment_required=["증거자료 (사진·녹음·문자 등)"],
    )


# === 라우터 ===


DRAFTER_REGISTRY = {
    "academy_refund": draft_academy_refund_request,
    "daycare_accident_report_demand": draft_daycare_accident_report_demand,
    "cctv_access": draft_cctv_access_request,
    "parental_leave": draft_parental_leave_application,
    "school_violence": draft_school_violence_report,
}


def draft_documents_for_scenario(
    scenario_type: str,
    profile: FamilyProfile,
    scenario_data: dict[str, Any],
    laws: Optional[list[LawArticle]] = None,
) -> list[DraftDocument]:
    """시나리오 타입 → 적절한 초안 묶음 생성."""
    docs: list[DraftDocument] = []
    if scenario_type == "academy_refund":
        docs.append(draft_academy_refund_request(profile, scenario_data, laws))
    elif scenario_type == "daycare_accident":
        docs.append(draft_daycare_accident_report_demand(profile, scenario_data, laws))
        if scenario_data.get("cctv_access_denied"):
            docs.append(draft_cctv_access_request(profile, scenario_data, laws))
    elif scenario_type == "parental_leave_denied":
        docs.append(draft_parental_leave_application(profile, scenario_data, laws))
    elif scenario_type == "school_violence":
        docs.append(draft_school_violence_report(profile, scenario_data, laws))
    return docs
