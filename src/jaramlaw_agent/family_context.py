"""family_context — 라이프스테이지 분류 + 특수상황 태그 부여.

(F1 가족 프로필 매니저 핵심 모듈)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from .models import Child, FamilyProfile, LifeEvent, LifeStage, Parent


def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def compute_age_months(birth_date: Optional[str], reference_date: date) -> Optional[int]:
    """birth_date 기준 reference_date 시점의 만 나이(개월). None이면 미산정."""
    bd = _parse_iso_date(birth_date)
    if not bd:
        return None
    years = reference_date.year - bd.year
    months = reference_date.month - bd.month
    if reference_date.day < bd.day:
        months -= 1
    total = years * 12 + months
    return max(0, total)


def classify_life_stage(child: Child, reference_date: date) -> LifeStage:
    """단일 child의 라이프스테이지 분류."""
    # 임신 단계
    if child.expected_birth_date and not child.birth_date:
        return LifeStage.PREGNANCY

    months = compute_age_months(child.birth_date, reference_date)
    if months is None:
        return LifeStage.UNKNOWN

    if months <= 11:
        return LifeStage.INFANT
    if months <= 35:
        return LifeStage.TODDLER
    if months <= 71:
        return LifeStage.PRESCHOOL
    if months <= 143:  # 만 12세 미만 = 143개월 이하
        return LifeStage.ELEMENTARY
    if months <= 179:  # 만 15세 미만
        return LifeStage.MIDDLE
    if months <= 215:  # 만 18세 미만
        return LifeStage.HIGH
    return LifeStage.ADULT_CHILD


def derive_family_flags(
    parents: list[Parent],
    children: list[Child],
    events: list[LifeEvent],
    income_decile: Optional[int],
    life_stages: list[LifeStage],
) -> list[str]:
    """가족 특수상황 태그 부여."""
    flags: list[str] = []

    # 자녀 수
    if len(children) >= 2:
        flags.append("multiple_children")

    # 한부모
    if len(parents) == 1:
        flags.append("single_parent")

    # 둘째 임신 (기존 자녀 + pregnancy 동시)
    has_pregnancy = any(s == LifeStage.PREGNANCY for s in life_stages)
    has_existing_child = any(s not in (LifeStage.PREGNANCY, LifeStage.UNKNOWN) for s in life_stages)
    if has_pregnancy and has_existing_child:
        flags.append("second_child_pregnancy")
        flags.append("second_child")
    elif has_existing_child and len(children) >= 2:
        # 첫째 외에도 자녀 존재
        if "second_child" not in flags:
            flags.append("second_child")

    # 맞벌이 — parents 모두 employment 있음
    if parents:
        employed = sum(1 for p in parents if p.employment and p.employment.lower() not in {"none", "전업주부", "무직"})
        if employed == len(parents) and employed >= 2:
            flags.append("dual_income")
        elif employed == 1 and len(parents) >= 2:
            flags.append("single_income")

    # 워킹맘 — mother + 고용
    for p in parents:
        if p.role == "mother" and p.employment and p.employment.lower() not in {"none", "전업주부", "무직"}:
            flags.append("working_mom")
            break

    # 저소득 (income_decile ≤ 4)
    if income_decile is not None and income_decile <= 4:
        flags.append("low_income")

    # 장애아동
    if any(c.disability for c in children):
        flags.append("disabled_child")

    # 중복 제거 후 정렬 (deterministic)
    return sorted(set(flags))


def build_family_profile(raw_input: dict[str, Any]) -> FamilyProfile:
    """raw_input dict → FamilyProfile 객체 (life_stages + flags 자동 계산)."""
    ref_date_str = raw_input.get("reference_date")
    ref_date = _parse_iso_date(ref_date_str) or date.today()

    parents = [Parent(**p) for p in raw_input.get("parents", [])]
    children = [Child(**c) for c in raw_input.get("children", [])]
    events = [LifeEvent(**e) for e in raw_input.get("events", [])]
    income_decile = raw_input.get("income_decile")
    initial_flags = list(raw_input.get("flags", []))

    life_stages = [classify_life_stage(c, ref_date) for c in children]
    flags = derive_family_flags(parents, children, events, income_decile, life_stages)

    # 입력 flags + 파생 flags 병합
    final_flags = sorted(set(initial_flags) | set(flags))

    return FamilyProfile(
        parents=parents,
        children=children,
        events=events,
        flags=final_flags,
        life_stages=[s.value for s in life_stages],
        income_decile=income_decile,
        reference_date=ref_date.isoformat(),
    )
