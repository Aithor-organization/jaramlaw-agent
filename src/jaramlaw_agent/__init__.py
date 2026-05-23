"""자람법(JaramLaw) — 가족 라이프스테이지 법령·정책 AI 동반자.

AITHOR-Agent-Framework 패턴 기반. Domain pack = `family-legal`.
Constitution 5원칙 (변호사법 회피 / Citation / Safety routing / 자동 발사 금지 / PII 마스킹) 강제.
"""

__version__ = "0.1.0"

DISCLAIMER = (
    "※ 본 서비스는 양육 정보 보조 도구이며, "
    "구체 사안에 대한 법률 자문이 아닙니다."
)

EMERGENCY_CONTACTS = {
    "child_abuse_suspected": ("1577-1391", "아이지킴이 콜 (아동보호전문기관)"),
    "medical_emergency": ("119", "응급의료"),
    "self_harm_signal": ("1393", "자살예방상담전화"),
    "domestic_violence": ("1366", "여성긴급전화"),
}
