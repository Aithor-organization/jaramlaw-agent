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
from typing import Any, Callable, Optional

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


def collect_strings(v: Any) -> list[str]:
    """중첩 payload(dict/list/str)에서 문자열만 모은다."""
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        out: list[str] = []
        for x in v:
            out.extend(collect_strings(x))
        return out
    if isinstance(v, dict):
        out = []
        for x in v.values():
            out.extend(collect_strings(x))
        return out
    return []


# 배우자·동거인에 의한 성인 피해 가정폭력을 공기(共起)로 잡는다.
# SAFETY_KEYWORDS의 "남편이 때"는 부분문자열이라 한국어 SOV 어순에서 목적어가
# 끼면("남편이 저를 때려요") 끊겨 미탐지된다. 주체 토큰과 폭력 동사가 함께 나오면
# 어미·목적어·부사가 어떻게 끼어도 신호를 잡되, 대상이 아동인 문장은 child_abuse
# 경로에 양보한다(잘못 1366으로 새지 않도록).
_DV_ACTORS = ("남편", "아내", "배우자", "동거인", "파트너", "시아버지", "시어머니", "시댁")
_DV_VIOLENCE = (
    "때려", "때린", "때렸", "때리", "맞았", "맞고", "맞아", "맞는",
    "폭행", "구타", "협박", "밀쳐", "밀쳤", "흉기", "목을 조",
)
_DV_CHILD_OBJECT = ("아이를", "아기를", "자녀를", "애를", "아이한테", "아이가", "아기가")


def _detect_spousal_violence(blob: str) -> Optional[str]:
    """배우자 폭력 정황(성인 피해)을 주체+폭력동사 공기로 판정. 아동 대상이면 None."""
    if any(obj in blob for obj in _DV_CHILD_OBJECT):
        return None
    actor = next((a for a in _DV_ACTORS if a in blob), None)
    verb = next((v for v in _DV_VIOLENCE if v in blob), None)
    if actor and verb:
        return f"배우자 폭력 정황: '{actor}' + '{verb}'"
    return None


def detect_safety_signals(payload: Any) -> SafetyRouting:
    """payload(dict/list/str) 안의 모든 문자열을 검사하여 첫 매칭 신호 반환."""
    blob = " ".join(collect_strings(payload))

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

    dv_reason = _detect_spousal_violence(blob)
    if dv_reason is not None:
        contact, name = EMERGENCY_CONTACTS["domestic_violence"]
        return SafetyRouting(
            triggered=True,
            category="domestic_violence",
            contact=f"{contact} ({name})",
            reason=dv_reason,
        )
    return SafetyRouting(triggered=False)


# === 3-bis. 안전 신호 보강 (저비용 분류 모델) ===
#
# 위 키워드 매칭은 정확 부분문자열이라 실제 부모의 말투를 놓친다. 실측 결과:
#   "죽고싶어요"(키는 '죽고 싶')·"아이를 때렸어요"·"체온이 40도예요"(키는 '고열 40')
#   → 전부 미탐지. 아동학대와 자해 신호를 띄어쓰기 하나로 놓치는 셈이다.
#
# gpt-5.4-nano로 같은 5케이스를 분류했더니 5/5 정확했고, 평균 0.97초·최저비용이었다.
# 그래서 분류만 모델에 맡기되, 규칙은 하나다: **보강만 하고 강등하지 않는다.**
# 키워드가 이미 잡은 신호는 그대로 두고, 모델이 죽거나 느려도 키워드 결과가 살아남는다.

SAFETY_CLASSIFIER_INSTRUCTION = (
    "너는 한국 양육 상담의 안전 신호 분류기다. 지금 이 순간 긴급 개입이 필요한지만 판단한다.\n"
    "입력이 아래 중 하나면 그 라벨만, 아니면 none만 출력하라. 다른 말 금지.\n\n"
    "child_abuse — 보호자·성인이 아이를 때리거나 학대·방임하고 있다는 정황.\n"
    "  아이 몸에 원인이 설명되지 않는 멍·상처가 여러 개 있거나 반복된다는 진술도 여기에 포함한다\n"
    "  (아동학대의 전형적 지표다. 원인이 특정 사고로 설명되면 none).\n"
    "self_harm — 자해·자살 사고\n"
    "medical_emergency — 지금 119가 필요한 상태 (의식저하, 호흡곤란, 경련, 40도 고열 등)\n"
    "domestic_violence — 가정폭력\n"
    "none — 그 외 전부\n\n"
    "반드시 none으로 분류할 것 (긴급 개입이 아니라 법률·제도 상담이다):\n"
    "- 이미 지나간 사고에 대한 대응·보상·책임을 묻는 경우\n"
    "  (예: '어린이집에서 아이가 다쳤어요', '학원에서 사고가 났는데 어떻게 하나요')\n"
    "- 기관의 학대가 '의심'되어 절차를 묻는 경우가 아니라, 절차·서류·신고방법 자체를 묻는 경우\n"
    "- 법령·지원금·환불·휴가 등 제도 문의\n"
    "긴급 개입이 필요한 '현재진행형 위험'일 때만 라벨을 붙여라. 애매하면 none."
)

_LLM_LABEL_TO_CATEGORY = {
    "child_abuse": "child_abuse_suspected",
    "self_harm": "self_harm_signal",
    "medical_emergency": "medical_emergency",
    "domestic_violence": "domestic_violence",
}


def augment_safety_with_llm(
    payload: Any,
    deterministic: SafetyRouting,
    classifier: Optional[Callable[[str, str], Optional[str]]] = None,
) -> SafetyRouting:
    """키워드가 놓친 안전 신호를 분류 모델로 보강한다.

    classifier: (instruction, text) -> label 문자열 또는 None.
                None을 반환하거나 인자가 없으면 키워드 결과를 그대로 돌려준다.

    안전 장치:
      - 키워드가 이미 신호를 잡았으면 모델을 호출하지 않는다 (강등 불가 + 비용 0).
      - 모델이 실패/타임아웃/헛소리면 키워드 결과 유지 (fail-safe to deterministic).
    """
    if deterministic.triggered or classifier is None:
        return deterministic

    blob = " ".join(collect_strings(payload)).strip()
    if not blob:
        return deterministic

    try:
        label = classifier(SAFETY_CLASSIFIER_INSTRUCTION, blob)
    except Exception:
        return deterministic
    if not label:
        return deterministic

    key = label.strip().lower()
    category = next((c for lbl, c in _LLM_LABEL_TO_CATEGORY.items() if lbl in key), None)
    if not category:
        return deterministic

    contact, name = EMERGENCY_CONTACTS[category]
    return SafetyRouting(
        triggered=True,
        category=category,
        contact=f"{contact} ({name})",
        reason=f"분류 모델 감지: '{key}' (키워드 미매칭 — 보강 탐지)",
    )


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
