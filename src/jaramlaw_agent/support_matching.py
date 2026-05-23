"""support_matching — 가족 프로필 → 정부지원 자동 매칭 + D-day 계산.

(F2 지원 매칭 엔진)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml

from .family_context import _parse_iso_date, compute_age_months
from .models import FamilyProfile, LegalBasis, SupportMatch


DEFAULT_SEED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seed" / "supports"


def load_all_supports(seed_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    seed_dir = seed_dir or DEFAULT_SEED_DIR
    items: list[dict[str, Any]] = []
    if not seed_dir.exists():
        return items
    for f in sorted(seed_dir.glob("*.yaml")):
        with f.open("r", encoding="utf-8") as fp:
            items.append(yaml.safe_load(fp) or {})
    return items


def _evaluate_rule(rule: dict[str, Any], profile: FamilyProfile, ref_date: date) -> tuple[bool, str]:
    """eligibility_rules의 단일 규칙 평가. (passed, evidence) 반환."""
    kind = rule.get("kind")

    if kind == "child_age_months_between":
        lo, hi = rule.get("min", 0), rule.get("max", 99999)
        for c in profile.children:
            months = compute_age_months(c.birth_date, ref_date)
            if months is not None and lo <= months <= hi:
                return True, f"자녀 {c.name_masked} 만 {months}개월 ({lo}-{hi}개월 범위)"
        return False, ""

    if kind == "child_age_years_between":
        lo, hi = rule.get("min", 0), rule.get("max", 99)
        for c in profile.children:
            months = compute_age_months(c.birth_date, ref_date)
            if months is None:
                continue
            years = months // 12
            if lo <= years <= hi:
                return True, f"자녀 {c.name_masked} 만 {years}세 ({lo}-{hi}세 범위)"
        return False, ""

    if kind == "child_life_stage_in":
        target = set(rule.get("values", []))
        overlap = set(profile.life_stages) & target
        if overlap:
            return True, f"자녀 life stage {sorted(overlap)} 매칭"
        return False, ""

    if kind == "has_birth_within_days":
        threshold = rule.get("threshold", 60)
        for c in profile.children:
            bd = _parse_iso_date(c.birth_date)
            if bd and (ref_date - bd).days <= threshold:
                return True, f"자녀 {c.name_masked} 출생일 D-{threshold} 이내"
        return False, ""

    if kind == "birth_after":
        cutoff = _parse_iso_date(rule.get("date"))
        if not cutoff:
            return False, ""
        for c in profile.children:
            bd = _parse_iso_date(c.birth_date)
            if bd and bd >= cutoff:
                return True, f"자녀 {c.name_masked} 출생일 {cutoff.isoformat()} 이후"
        return False, ""

    if kind == "is_pregnant":
        has = any(c.expected_birth_date and not c.birth_date for c in profile.children) or \
              any(e.type == "pregnancy" for e in profile.events)
        return (has, "임신 중") if has else (False, "")

    if kind == "family_flag":
        target = rule.get("value")
        if target in profile.flags:
            return True, f"flag={target}"
        return False, ""

    if kind == "region_starts_with":
        prefix = rule.get("prefix", "")
        for p in profile.parents:
            if p.region_code and p.region_code.startswith(prefix):
                return True, f"region_code {p.region_code} starts with {prefix}"
        return False, ""

    if kind == "region_code_in":
        targets = set(rule.get("values", []))
        for p in profile.parents:
            if p.region_code in targets:
                return True, f"region_code {p.region_code} ∈ {sorted(targets)}"
        return False, ""

    if kind == "income_decile_max":
        max_v = rule.get("max", 10)
        if profile.income_decile is not None and profile.income_decile <= max_v:
            return True, f"소득분위 {profile.income_decile} ≤ {max_v}"
        # income 정보 없으면 보수적으로 PASS (정확한 검증은 정부24에서)
        if profile.income_decile is None:
            return True, "소득 미입력 — 보수적 매칭 (실제 자격은 정부24 확인)"
        return False, ""

    if kind == "parent_employed":
        insurance = rule.get("insurance", "")
        for p in profile.parents:
            if p.employment and p.employment.lower() not in {"none", "전업주부", "무직"}:
                # 보수적: 정확한 보험 가입 여부 미확인 — 통상 정규직 → 고용보험 가입 가정
                return True, f"부모 고용 ({p.role}: {p.employment})"
        return False, ""

    if kind == "parent_role":
        target = rule.get("value")
        if target == "pregnant_employee":
            for p in profile.parents:
                if p.role == "mother" and p.employment and "second_child_pregnancy" in profile.flags:
                    return True, f"임신 중인 여성근로자 ({p.role}: {p.employment})"
                # 단순 임신
                if p.role == "mother" and p.employment and any(c.expected_birth_date and not c.birth_date for c in profile.children):
                    return True, f"임신 중인 여성근로자 ({p.role}: {p.employment})"
            return False, ""
        if target == "spouse_of_birth_parent":
            # 배우자 출산휴가: 배우자가 임신 중이고 본인은 근로자
            has_pregnant_spouse = any(c.expected_birth_date and not c.birth_date for c in profile.children)
            for p in profile.parents:
                if p.role == "father" and p.employment and has_pregnant_spouse:
                    return True, f"배우자 출산 예정 + 본인 근로자 ({p.role})"
            return False, ""
        return False, ""

    if kind == "within_days_after_birth":
        days = rule.get("days", 120)
        for c in profile.children:
            bd = _parse_iso_date(c.birth_date)
            if bd and (ref_date - bd).days <= days:
                return True, f"자녀 {c.name_masked} 출생 후 {days}일 이내"
        # 미출생 시 PASS (출생 시점에 청구 가능)
        return False, ""

    if kind == "facility_in":
        targets = set(rule.get("values", []))
        for c in profile.children:
            if c.facility in targets:
                return True, f"자녀 {c.name_masked} 시설={c.facility}"
        return False, ""

    # 미지원 규칙 — 보수적 PASS (스킵)
    return True, f"unhandled rule kind: {kind}"


def _compute_deadline_days_left(support: dict[str, Any], profile: FamilyProfile, ref_date: date) -> Optional[int]:
    kind = support.get("deadline_kind")
    if kind == "after_birth":
        days = support.get("deadline_days_from_birth", 60)
        for c in profile.children:
            bd = _parse_iso_date(c.birth_date)
            if bd:
                deadline = bd + timedelta(days=days)
                left = (deadline - ref_date).days
                return max(0, left)
            ebd = _parse_iso_date(c.expected_birth_date)
            if ebd:
                deadline = ebd + timedelta(days=days)
                return (deadline - ref_date).days  # 음수 가능 (출생 전이라 D-day 미확정)
        return None
    if kind == "monthly":
        return 30  # 매월 — D-30 (다음 달 신청 가능)
    if kind == "yearly":
        return 365
    if kind == "ongoing":
        return None  # 상시
    if kind == "during_leave":
        return None
    if kind == "before_birth":
        for c in profile.children:
            ebd = _parse_iso_date(c.expected_birth_date)
            if ebd:
                return (ebd - ref_date).days
        return None
    if kind == "within_days_after_birth":
        days = support.get("deadline_days", 120)
        for c in profile.children:
            bd = _parse_iso_date(c.birth_date)
            if bd:
                deadline = bd + timedelta(days=days)
                return (deadline - ref_date).days
        return None
    return None


def match_supports(
    profile: FamilyProfile,
    seed_dir: Optional[Path] = None,
) -> list[SupportMatch]:
    """가족 프로필 → 적용 가능한 지원금 리스트 (deadline 임박순)."""
    ref_date = _parse_iso_date(profile.reference_date) or date.today()
    all_supports = load_all_supports(seed_dir)

    matched: list[SupportMatch] = []
    for sup in all_supports:
        rules = sup.get("eligibility_rules", [])
        evidence: list[str] = []
        all_passed = True
        for r in rules:
            passed, why = _evaluate_rule(r, profile, ref_date)
            if not passed:
                all_passed = False
                break
            if why:
                evidence.append(why)
        if not all_passed:
            continue

        lb_data = sup.get("legal_basis", {})
        legal_basis = LegalBasis(
            law=lb_data.get("law", ""),
            article=lb_data.get("article", ""),
            effective_date=lb_data.get("effective_date", ""),
            source_url=lb_data.get("source_url", ""),
        )
        # citation 완전성 확인 (Constitution 원칙 2)
        if not legal_basis.is_complete():
            # 시드 자체 불완전 — 스킵 (시드 작성 단계에서 검출되어야 함)
            continue

        days_left = _compute_deadline_days_left(sup, profile, ref_date)

        matched.append(SupportMatch(
            support_id=sup["support_id"],
            name=sup["name"],
            amount_krw=int(sup.get("amount_krw", 0)),
            amount_description=sup.get("amount_description", ""),
            condition_summary=sup.get("condition_summary", ""),
            legal_basis=legal_basis,
            application_channel=sup.get("application_channel", ""),
            deadline_days_left=days_left,
            deadline_kind=sup.get("deadline_kind"),
            eligibility_evidence=evidence,
            notes=sup.get("notes"),
        ))

    # 정렬 — deadline_days_left ASC (None은 뒤로)
    def sort_key(m: SupportMatch) -> tuple[int, int]:
        if m.deadline_days_left is None:
            return (1, 0)
        # 음수(이미 지남)는 우선순위 낮춤
        if m.deadline_days_left < 0:
            return (1, m.deadline_days_left)
        return (0, m.deadline_days_left)

    matched.sort(key=sort_key)
    return matched
