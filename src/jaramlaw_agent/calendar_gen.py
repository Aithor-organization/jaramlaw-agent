"""calendar_gen — 아이 생년월일 기반 영유아 건강검진·예방접종·학사·지원 캘린더.

(F3 법령 캘린더). iCal 직렬화 포함.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from .family_context import _parse_iso_date, compute_age_months
from .models import (
    CalendarEvent,
    CalendarOutput,
    Child,
    FamilyProfile,
    LegalBasis,
)


# 영유아 건강검진 표준 일정 (개월 기준 — 모자보건법)
HEALTH_CHECKUP_MONTHS = [
    (1, 1, "1차 영유아 건강검진"),  # 생후 14-35일
    (5, 5, "2차 영유아 건강검진 (4-6개월)"),
    (10, 10, "3차 영유아 건강검진 (9-12개월)"),
    (20, 20, "4차 영유아 건강검진 (18-24개월)"),
    (33, 33, "5차 영유아 건강검진 (30-36개월)"),
    (45, 45, "6차 영유아 건강검진 (42-48개월)"),
    (57, 57, "7차 영유아 건강검진 (54-60개월)"),
    (69, 69, "8차 영유아 건강검진 (66-71개월)"),
]

# 필수 예방접종 표준 일정 (개월 기준 — 감염병예방법 제24조)
VACCINATION_SCHEDULE = [
    (1, "BCG (결핵)"),
    (1, "B형간염 1차"),
    (2, "B형간염 2차"),
    (2, "DTaP-IPV-Hib 1차"),
    (2, "폐렴구균 1차"),
    (2, "로타바이러스 1차"),
    (4, "DTaP-IPV-Hib 2차"),
    (4, "폐렴구균 2차"),
    (4, "로타바이러스 2차"),
    (6, "B형간염 3차"),
    (6, "DTaP-IPV-Hib 3차"),
    (6, "폐렴구균 3차"),
    (12, "MMR 1차 (홍역·이하선염·풍진)"),
    (12, "수두"),
    (12, "A형간염 1차"),
    (15, "DTaP-IPV-Hib 추가"),
    (15, "폐렴구균 추가"),
    (12, "일본뇌염 1차"),
    (60, "MMR 2차"),
    (60, "DTaP 추가 (만 4-6세)"),
]


def _build_event_for_age(child: Child, target_month: int, title: str, kind: str, basis: Optional[LegalBasis]) -> Optional[CalendarEvent]:
    bd = _parse_iso_date(child.birth_date)
    if not bd:
        return None
    scheduled = bd + timedelta(days=target_month * 30)  # 어림 (정확 월 추가는 calendar lib 필요)
    return CalendarEvent(
        kind=kind,
        title=f"{title} (자녀 {child.name_masked})",
        legal_basis=basis,
        scheduled_date=scheduled.isoformat(),
        target_age_months=target_month,
        notes=f"자녀 {child.name_masked} 출생일 {bd.isoformat()} 기준",
    )


def generate_calendar(profile: FamilyProfile) -> CalendarOutput:
    ref_date = _parse_iso_date(profile.reference_date) or date.today()

    health_basis = LegalBasis(
        law="모자보건법", article="제10조", effective_date="2024-01-01",
        source_url="https://www.law.go.kr/lsInfoP.do?lsId=001750",
    )
    vaccine_basis = LegalBasis(
        law="감염병예방법", article="제24조", effective_date="2024-01-01",
        source_url="https://www.law.go.kr/lsInfoP.do?lsId=001738",
    )
    childbenefit_basis = LegalBasis(
        law="저출산고령사회기본법 / 아동수당법", article="시행령", effective_date="2024-01-01",
        source_url="https://www.law.go.kr/lsInfoP.do?lsId=001640",
    )
    school_basis = LegalBasis(
        law="초·중등교육법", article="제13조", effective_date="2024-01-01",
        source_url="https://www.law.go.kr/lsInfoP.do?lsId=001717",
    )

    events: list[CalendarEvent] = []
    for child in profile.children:
        bd = _parse_iso_date(child.birth_date)
        ebd = _parse_iso_date(child.expected_birth_date)

        # 임신 단계 — 출산 D-day + 출생신고 D+60 + 부모급여 신청 D+60
        if ebd and not bd:
            events.append(CalendarEvent(
                kind="birth_due",
                title=f"출산 예정일 ({child.name_masked})",
                scheduled_date=ebd.isoformat(),
                notes="출산휴가 신청 권장 D-30",
            ))
            events.append(CalendarEvent(
                kind="birth_registration",
                title=f"출생신고 기한 ({child.name_masked})",
                legal_basis=LegalBasis(
                    law="가족관계의 등록 등에 관한 법률", article="제44조", effective_date="2024-01-01",
                    source_url="https://www.law.go.kr/lsInfoP.do?lsId=001752",
                ),
                scheduled_date=(ebd + timedelta(days=30)).isoformat(),
                notes="출생 후 1개월 이내",
            ))
            events.append(CalendarEvent(
                kind="support_transition",
                title=f"부모급여·첫만남이용권 신청 기한 ({child.name_masked})",
                legal_basis=childbenefit_basis,
                scheduled_date=(ebd + timedelta(days=60)).isoformat(),
                notes="출생 후 60일 이내 신청 권장",
            ))
            continue

        if not bd:
            continue

        age_months = compute_age_months(child.birth_date, ref_date) or 0

        # 건강검진 — 아직 안 한 다음 차수만 (개월 기준)
        for target_min, target_max, title in HEALTH_CHECKUP_MONTHS:
            if target_min >= age_months:
                ev = _build_event_for_age(child, target_min, title, "health_checkup", health_basis)
                if ev:
                    events.append(ev)

        # 예방접종 — 아직 안 한 다음 차수만
        for target_month, title in VACCINATION_SCHEDULE:
            if target_month >= age_months:
                ev = _build_event_for_age(child, target_month, title, "vaccination", vaccine_basis)
                if ev:
                    events.append(ev)

        # 부모급여 전환 (만 1세) — 12개월 시점
        if age_months < 12:
            events.append(CalendarEvent(
                kind="support_transition",
                title=f"부모급여 만 1세 전환 (100만원 → 50만원) - {child.name_masked}",
                legal_basis=childbenefit_basis,
                scheduled_date=(bd + timedelta(days=365)).isoformat(),
                target_age_months=12,
            ))
        # 부모급여 종료 (만 2세)
        if age_months < 24:
            events.append(CalendarEvent(
                kind="support_transition",
                title=f"부모급여 종료 (만 2세 도달) - {child.name_masked}",
                legal_basis=childbenefit_basis,
                scheduled_date=(bd + timedelta(days=730)).isoformat(),
                target_age_months=24,
            ))
        # 아동수당 종료 (만 8세)
        if age_months < 96:
            events.append(CalendarEvent(
                kind="support_transition",
                title=f"아동수당 종료 (만 8세 도달) - {child.name_masked}",
                legal_basis=LegalBasis(
                    law="아동수당법", article="제4조", effective_date="2022-04-01",
                    source_url="https://www.law.go.kr/lsInfoP.do?lsId=011635",
                ),
                scheduled_date=(bd + timedelta(days=365 * 8)).isoformat(),
                target_age_months=96,
            ))
        # 초등 입학 (만 6세 다음해 3월)
        if age_months < 72:
            entry_year = bd.year + 7  # 만 6세 +1년
            entry_date = date(entry_year, 3, 2)
            events.append(CalendarEvent(
                kind="school_entry",
                title=f"초등학교 입학 ({child.name_masked})",
                legal_basis=school_basis,
                scheduled_date=entry_date.isoformat(),
                target_age_years=7,
            ))

    # scheduled_date ASC 정렬
    events.sort(key=lambda e: e.scheduled_date or "9999-12-31")

    return CalendarOutput(events=events, ical_export=_render_ical(events))


def _render_ical(events: list[CalendarEvent]) -> str:
    """RFC 5545 ICalendar 직렬화 (간이)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//JaramLaw//jaramlaw-agent//KO",
        "CALSCALE:GREGORIAN",
    ]
    for i, ev in enumerate(events):
        if not ev.scheduled_date:
            continue
        dtstart = ev.scheduled_date.replace("-", "")
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:jaramlaw-{i}-{dtstart}@jaramlaw",
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"SUMMARY:{ev.title}",
            f"CATEGORIES:{ev.kind}",
        ])
        if ev.notes:
            lines.append(f"DESCRIPTION:{ev.notes}")
        if ev.legal_basis:
            lines.append(f"COMMENT:근거 {ev.legal_basis.law} {ev.legal_basis.article}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
