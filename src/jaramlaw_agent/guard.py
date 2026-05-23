"""guard — AgentShield runtime guard.

(Constitution 원칙 3 Safety + 원칙 5 PII).

- PIIRedactor: 아이 이름·주민번호·정확 주소·휴대전화 마스킹
- PromptInjectionDetector: 메타 지시문 차단
- SafetySignalDetector: 학대/응급/자해/가정폭력 신호 감지
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .models import SafetyRouting


# === 1. PII Redactor ===


SSN_PATTERN = re.compile(r"\d{6}-\d{7}")
PHONE_PATTERN = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?(\d{4})")
ADDRESS_DETAIL_PATTERN = re.compile(
    r"([가-힣]+구|[가-힣]+동|[가-힣]+로)\s*\d+(?:-\d+)?(?:번지)?"
)


def mask_ssn(text: str) -> str:
    return SSN_PATTERN.sub("***-***", text)


def mask_phone(text: str) -> str:
    return PHONE_PATTERN.sub(r"01*-****-\1", text)


def mask_address_detail(text: str) -> str:
    # 구·동·로까지는 보존, 번지/번호는 마스킹
    return ADDRESS_DETAIL_PATTERN.sub(r"\1 ***", text)


def mask_child_names(raw: dict[str, Any]) -> dict[str, Any]:
    """children[].name (만약 마스킹 안 되어 들어왔다면) → C1, C2 ..."""
    out = deepcopy(raw)
    children = out.get("children", [])
    for i, c in enumerate(children, start=1):
        # name_masked가 이미 설정되어 있으면 보존
        if "name_masked" in c and c["name_masked"]:
            continue
        # name 또는 child_name 필드가 들어왔다면 마스킹
        if "name" in c:
            c["name_masked"] = f"C{i}"
            del c["name"]
        elif "child_name" in c:
            c["name_masked"] = f"C{i}"
            del c["child_name"]
        else:
            c.setdefault("name_masked", f"C{i}")
    out["children"] = children
    return out


def redact_pii_recursive(value: Any) -> Any:
    """재귀적으로 dict/list/str 내부의 PII 마스킹."""
    if isinstance(value, str):
        out = value
        out = mask_ssn(out)
        out = mask_phone(out)
        out = mask_address_detail(out)
        return out
    if isinstance(value, list):
        return [redact_pii_recursive(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_pii_recursive(v) for k, v in value.items()}
    return value


def apply_pii_redaction(raw_input: dict[str, Any]) -> dict[str, Any]:
    """원본 raw_input → PII 마스킹된 redacted_input."""
    redacted = mask_child_names(raw_input)
    redacted = redact_pii_recursive(redacted)
    return redacted


# === 2. Prompt Injection 방어 ===


INJECTION_PATTERNS = [
    r"이전\s*지시\s*무시",
    r"system\s*prompt",
    r"ignore\s+previous\s+instructions",
    r"reveal\s+your\s+instructions",
    r"<\s*\|.*\|\s*>",  # special tokens
    r"\[\s*system\s*\]",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def detect_prompt_injection(text: str) -> bool:
    if not isinstance(text, str):
        return False
    return bool(INJECTION_RE.search(text))


def scrub_prompt_injection(text: str) -> str:
    if not isinstance(text, str):
        return text
    return INJECTION_RE.sub("[METAINST_REMOVED]", text)


# === 3. Safety Signal Detector ===


SAFETY_KEYWORDS = {
    "child_abuse_suspected": [
        "멍이 크",
        "반복 사고",
        "골절",
        "학대 의심",
        "이상한 자국",
        "맞은 자국",
        "이상한 멍",
        "여러 군데 멍",
        "머리 옆까지 멍",
        "심한 멍",
        "아이가 무서워해",
    ],
    "medical_emergency": [
        "호흡곤란",
        "의식 없",
        "의식이 없",
        "고열 40",
        "경련",
        "의식저하",
        "기절",
    ],
    "self_harm_signal": [
        "자해",
        "죽고 싶",
        "자살",
        "스스로 다치",
    ],
    "domestic_violence": [
        "남편이 때",
        "맞았다",
        "맞고 있",
        "가정폭력",
        "구타",
        "남편이 협박",
    ],
}

EMERGENCY_CONTACTS = {
    "child_abuse_suspected": ("1577-1391", "아이지킴이 콜 (아동보호전문기관) 또는 112"),
    "medical_emergency": ("119", "응급의료"),
    "self_harm_signal": ("1393", "자살예방상담전화"),
    "domestic_violence": ("1366", "여성긴급전화"),
}


def detect_safety_signals(payload: Any) -> SafetyRouting:
    """payload(dict/list/str) 안의 모든 문자열을 검사하여 첫 매칭 신호 반환."""
    def collect_strings(v: Any) -> list[str]:
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            out = []
            for x in v:
                out.extend(collect_strings(x))
            return out
        if isinstance(v, dict):
            out = []
            for x in v.values():
                out.extend(collect_strings(x))
            return out
        return []

    blob = " ".join(collect_strings(payload))
    blob_low = blob.lower()

    for category, keywords in SAFETY_KEYWORDS.items():
        for kw in keywords:
            if kw in blob:
                contact, name = EMERGENCY_CONTACTS[category]
                return SafetyRouting(
                    triggered=True,
                    category=category,
                    contact=f"{contact} ({name})",
                    reason=f"키워드 매칭: '{kw}'",
                )
    return SafetyRouting(triggered=False)


# === 4. 통합 Guard 진입점 ===


@dataclass
class GuardResult:
    redacted_input: dict[str, Any]
    safety_routing: SafetyRouting
    injection_detected: bool
    notes: list[str]


def run_guard(raw_input: dict[str, Any]) -> GuardResult:
    notes: list[str] = []

    # 1) PII 마스킹
    redacted = apply_pii_redaction(raw_input)

    # 2) prompt injection 검사 (재귀적)
    def has_injection_in(v: Any) -> bool:
        if isinstance(v, str):
            return detect_prompt_injection(v)
        if isinstance(v, list):
            return any(has_injection_in(x) for x in v)
        if isinstance(v, dict):
            return any(has_injection_in(x) for x in v.values())
        return False

    injection = has_injection_in(redacted)
    if injection:
        notes.append("prompt injection 패턴 감지 — 메타지시문 제거됨")
        # scrub
        def scrub(v: Any) -> Any:
            if isinstance(v, str):
                return scrub_prompt_injection(v)
            if isinstance(v, list):
                return [scrub(x) for x in v]
            if isinstance(v, dict):
                return {k: scrub(x) for k, x in v.items()}
            return v
        redacted = scrub(redacted)

    # 3) safety signal 검사
    safety = detect_safety_signals(redacted)
    if safety.triggered:
        notes.append(f"Safety routing 발동: {safety.category} ({safety.reason})")

    return GuardResult(
        redacted_input=redacted,
        safety_routing=safety,
        injection_detected=injection,
        notes=notes,
    )
