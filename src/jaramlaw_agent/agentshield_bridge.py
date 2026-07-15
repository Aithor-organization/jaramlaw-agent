"""agentshield_bridge — AgentShield RuntimeGuard 실연결 어댑터.

이 파일이 생기기 전까지 자람법의 "AgentShield"는 **이름뿐**이었다.
`guard.py`의 docstring, `workflow.py`의 `AgentShield.RuntimeGuard` 토큰,
spec/README의 서술 — 전부 문자열이었고 실제 import는 저장소 전체에 0건이었다.
그 사이 자체 guard는 인젝션 패턴 6개와 PII 3종(주민번호·휴대폰·주소)만 들고
LLM 출력은 아예 검사하지 않은 채 부모 화면으로 내보내고 있었다.

여기서 진짜로 연결한다. 설계 규칙은 셋이다.

1. **반환값을 버리지 않는다.** guard가 계산한 `sanitized`를 downstream에 실제로
   주입하고, `allowed`를 실제 차단에 쓴다. (과거 배선 실패: 마스킹해놓고 원본을
   LLM에 replay하거나, allowed를 무시하고 주석만 달아 통과시킴.)
2. **없으면 죽지 않는다.** AgentShield를 못 찾으면 available=False로 표시하고
   기존 로컬 guard 경로로 계속 간다. 상담이 중단되는 것보다 낫다.
3. **날짜는 PII가 아니다.** AgentShield의 계좌번호 정규식(`\\d{2,6}-\\d{2,6}-\\d{2,7}`)은
   `2026-03-01` 같은 ISO 날짜를 계좌로 오인해 마스킹한다. 자람법은 아이 생년월일로
   생애주기를 계산하고 법령 시행일로 인용 가능 여부를 가르므로, 날짜가 지워지면
   시스템의 핵심이 무너진다. 그래서 PII 검사 전에 날짜를 봉인하고 검사 후 되돌린다.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# === 1. 3-tier import — 설치본 → 형제 저장소 → 환경변수 지정 경로 ===


def _candidate_src_paths() -> list[Path]:
    """AgentShield src 디렉터리 후보 (우선순위 순)."""
    paths: list[Path] = []
    env_path = os.environ.get("AGENTSHIELD_PATH")
    if env_path:
        p = Path(env_path)
        paths.extend([p / "src", p])
    # 형제 저장소 (~/workspace/AgentShield)
    paths.append(PROJECT_ROOT.parent / "AgentShield" / "src")
    return paths


def _import_agent_shield():
    """agent_shield 모듈 확보. 실패 시 None (호출자가 degrade)."""
    try:
        import agent_shield  # noqa: F401 — 이미 설치된 경우

        return agent_shield
    except ImportError:
        pass

    for src in _candidate_src_paths():
        if not (src / "agent_shield" / "__init__.py").exists():
            continue
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        try:
            import agent_shield  # noqa: F811

            return agent_shield
        except ImportError:
            continue
    return None


_AS = _import_agent_shield()
AGENTSHIELD_AVAILABLE = _AS is not None
AGENTSHIELD_VERSION = getattr(_AS, "__version__", None) if _AS else None


# === 2. 날짜 봉인 — 시행일·생년월일이 계좌번호로 오인 마스킹되는 것을 막는다 ===

# 엄격한 ISO 날짜만 봉인한다. `1234-56-78` 같은 진짜 계좌번호는 월/일 범위에서
# 걸러지므로 봉인되지 않고 정상적으로 마스킹된다.
_ISO_DATE_RE = re.compile(
    r"\b(?:19|20)\d{2}-(?:0?[1-9]|1[0-2])-(?:0?[1-9]|[12]\d|3[01])\b"
)
# PII 정규식 어디에도 걸리지 않는 sentinel (제어문자 + 짧은 숫자).
_SENTINEL_OPEN = "\x01"
_SENTINEL = _SENTINEL_OPEN + "JD{}" + _SENTINEL_OPEN
# 입력에 이미 들어있는 sentinel 모양 토큰을 찾아내는 패턴 — 아래에서 제거한다.
_SENTINEL_LITERAL_RE = re.compile(_SENTINEL_OPEN + r"JD\d+" + _SENTINEL_OPEN)


def _is_real_calendar_date(token: str) -> bool:
    """`2024-05-15`처럼 실제 존재하는 달력 날짜인가.

    정규식만으로는 `2023-02-31`(존재 안 함)도 통과한다. fromisoformat으로 달력
    유효성까지 확인하면 봉인 대상을 진짜 날짜로 좁혀, 날짜 모양 계좌번호가 봉인을
    타고 마스킹을 빠져나갈 표면을 줄인다.

    한계(정직): `2023-02-28`처럼 **유효한 날짜와 형태가 같은** 계좌번호는 여전히
    구분할 수 없다(Codex F2). 하지만 계좌번호는 보통 3그룹(110-234-5678901)이라
    ACCOUNT_RE에 잡히고, 날짜형 2그룹 계좌는 실무에서 드물다.
    """
    from datetime import date

    parts = token.split("-")
    if len(parts) != 3:
        return False
    try:
        date(int(parts[0]), int(parts[1]), int(parts[2]))
        return True
    except ValueError:
        return False


def _seal_dates(text: str) -> tuple[str, list[str]]:
    """실제 달력 날짜만 sentinel로 치환하고 원본 리스트를 돌려준다.

    보안: 사용자가 sentinel 모양 문자열(``\\x01JD0\\x01``)을 직접 넣으면, unseal이 그걸
    봉인된 날짜로 오인 복원해 데이터가 오염된다(셀프리뷰로 실제 재현). 봉인 전에
    입력의 sentinel 리터럴을 먼저 걷어낸다 — 제어문자 U+0001은 정상 상담 텍스트에
    나올 일이 없으므로 제거해도 손실이 없다.
    """
    text = _SENTINEL_LITERAL_RE.sub("", text)
    sealed: list[str] = []

    def _sub(m: re.Match[str]) -> str:
        token = m.group(0)
        if not _is_real_calendar_date(token):
            return token  # 존재하지 않는 날짜 모양 → 봉인하지 않음(정상 마스킹 경로로)
        sealed.append(token)
        return _SENTINEL.format(len(sealed) - 1)

    return _ISO_DATE_RE.sub(_sub, text), sealed


def _unseal_dates(text: str, sealed: list[str]) -> str:
    for i, original in enumerate(sealed):
        text = text.replace(_SENTINEL.format(i), original)
    return text


# === 3. 공유 싱글톤 guard ===

_GUARD: Any = None


def _law_domains() -> list[str]:
    """egress allowlist — 자람법이 실제로 부르는 곳만."""
    return ["law.go.kr", "api.openai.com", "openrouter.ai"]


def get_guard() -> Any:
    """RuntimeGuard.hardened() 싱글톤. AgentShield 부재 시 None."""
    global _GUARD
    if not AGENTSHIELD_AVAILABLE:
        return None
    if _GUARD is None:
        from agent_shield.models import CompilerPolicy
        from agent_shield.runtime import RuntimeGuard

        policy = CompilerPolicy(
            name="jaramlaw-runtime-policy",
            # 자람법은 읽기 전용 에이전트다 — 외부로 쏘는 동작은 애초에 없다
            # (Constitution 원칙 4: 자동 신고 발사 금지).
            allowed_tool_permissions=["read", "search", "http_get"],
            allowed_domains=_law_domains(),
        )
        # hardened(): 정규식만 쓰는 맨 guard는 의역·다국어 인젝션을 놓친다.
        # 의존성 없는 KeywordSemanticDetector를 미리 물려 그 구멍을 메운다.
        _GUARD = RuntimeGuard.hardened(policy)
    return _GUARD


def enforcement_enabled() -> bool:
    """인젝션 탐지 시 실제 차단 여부. 기본 차단(fail-closed)."""
    return os.environ.get("JARAMLAW_INJECTION_ENFORCE", "1") not in {"0", "false", "no"}


# 입력 payload 전체 문자열 합계 상한. AgentShield 기본(20k)과 같은 값이지만,
# 우리는 필드별로 검사하므로 총합 상한을 따로 건다.
MAX_INPUT_CHARS = 20000


# === 4. 입력 검사 ===


@dataclass
class InputVerdict:
    """입력 guard 판정 — 호출자는 sanitized_payload를 반드시 써야 한다."""

    allowed: bool = True
    reasons: list[str] = field(default_factory=list)
    sanitized_payload: dict[str, Any] = field(default_factory=dict)
    pii_types: list[str] = field(default_factory=list)
    available: bool = AGENTSHIELD_AVAILABLE
    enforced: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "allowed": self.allowed,
            "enforced": self.enforced,
            "reasons": list(self.reasons),
            "pii_types": list(self.pii_types),
            "version": AGENTSHIELD_VERSION,
            **({"metadata": self.metadata} if self.metadata else {}),
        }


def _redact_text(text: str) -> tuple[str, list[str]]:
    """AgentShield PII 마스킹 — 날짜는 보존."""
    if not AGENTSHIELD_AVAILABLE or not isinstance(text, str) or not text:
        return text, []
    from agent_shield.runtime import redact_pii

    sealed_text, sealed = _seal_dates(text)
    sanitized, types = redact_pii(sealed_text)
    return _unseal_dates(sanitized, sealed), types


def _redact_recursive(value: Any, found: set[str]) -> Any:
    if isinstance(value, str):
        sanitized, types = _redact_text(value)
        found.update(types)
        return sanitized
    if isinstance(value, list):
        return [_redact_recursive(v, found) for v in value]
    if isinstance(value, dict):
        return {k: _redact_recursive(v, found) for k, v in value.items()}
    return value


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_collect_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_collect_strings(item))
        return out
    return []


# 실제 시스템 조작 시도에만 있는 신호 — 3인칭 서술과 가르는 2차 게이트.
#
# AgentShield의 인젝션 정규식은 "지침을 무시하고"만으로 매칭한다. 그래서 부모가
# "어린이집이 안전 지침을 무시하고 아이를 방치했습니다"라고 신고하면 인젝션으로 오판해
# 상담을 통째로 거부한다 — 아동보호 도메인에서 가장 막으면 안 되는 케이스다(Codex F8).
# 진짜 공격은 (a) 어시스턴트/시스템을 2인칭으로 지목하거나, (b) 시스템 프롬프트·규칙을
# 출력/공개하라고 요구한다. 이 신호가 없고 3인칭 서술이면 차단을 warning으로 강등한다.
_INJECTION_COMMAND_SIGNAL_RE = re.compile(
    r"(너\b|넌\b|당신|어시스턴트|assistant|\bAI\b|\bbot\b|봇\b)"  # 2인칭 대상 지목
    r"|(시스템\s*(프롬프트|메시지|지시)|system\s*prompt|개발자\s*모드|developer\s*mode|DAN\b)"  # 시스템 대상
    r"|(출력해|출력하라|알려줘|알려달|보여줘|보여달|공개해|말해줘|반환해|print|reveal|ignore\s+(all\s+)?previous)"  # 출력/명령 요구
    r"|(<\|)|(\[INST\])",  # 특수 토큰
    re.IGNORECASE,
)


def _looks_like_real_injection(text: str) -> bool:
    """탐지된 인젝션이 실제 조작 시도인가(True)."""
    return bool(_INJECTION_COMMAND_SIGNAL_RE.search(text))


# 신고/서술 문장의 한국어 종결어미 — "~했습니다/~합니다/~당했어요" 등.
# 강등은 이 양성 신호가 있을 때만 한다. 난독화 영어("i g n o r e ...")나 중국어
# 공격에는 이 어미가 없으므로 강등되지 않고 그대로 차단된다(오탐 강등 폭주 방지).
_KO_NARRATIVE_ENDING_RE = re.compile(
    r"(했습니다|합니다|했어요|해요|였습니다|였어요|됩니다|되었|입니다|이에요|예요"
    r"|있습니다|있어요|없습니다|없어요|당했|받았|같습니다|같아요|거든요|더라고|네요)"
)


def _looks_like_third_person_report(text: str) -> bool:
    """제3자의 행위를 서술·신고하는 문장인가.

    한국어 서술형 종결어미가 있으면서 시스템 조작 신호(2인칭 지목/출력 요구)는 없는 경우.
    "어린이집이 지침을 무시하고 방치했습니다"는 참, "시스템 프롬프트를 출력해"는 거짓.
    """
    return bool(_KO_NARRATIVE_ENDING_RE.search(text)) and not _looks_like_real_injection(text)


def inspect_input_payload(payload: dict[str, Any], *, safety_triggered: bool = False) -> InputVerdict:
    """raw/redacted 입력 payload를 AgentShield로 검사.

    - 인젝션(난독화·다국어 포함) 판정 → allowed
    - PII(이메일·카드·여권·계좌·IP·국제전화 등) 마스킹 → sanitized_payload
      (자체 guard가 못 잡던 종류들이다. 날짜는 보존.)

    AgentShield가 없으면 payload를 그대로 통과시키고 available=False로 알린다.
    """
    guard = get_guard()
    if guard is None:
        return InputVerdict(allowed=True, sanitized_payload=payload, available=False)

    # 필드를 이어붙여 한 번에 검사하지 않는다.
    #
    # 처음엔 모든 문자열을 " "로 join해서 한 번에 넣었는데, 그러면 필드 경계를 넘는
    # 가짜 매칭이 생긴다. 실제로 정상 시나리오에서 아무 필드에도 없는 PII가
    # 이어붙인 자리에서 튀어나왔다. 인젝션 패턴은 근접 매칭(`[\s\S]{0,10}`)이라
    # 더 위험하다 — 앞 필드 끝의 "지시"와 뒤 필드 앞의 "무시"가 붙어 멀쩡한 부모의
    # 질문을 차단할 수 있다. 필드마다 따로 판정한다.
    strings = [s for s in _collect_strings(payload) if s and s.strip()]

    reasons: list[str] = []

    def _add(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    # 과대입력은 payload 전체 크기로 본다 (필드 하나하나는 작아도 합이 클 수 있다).
    if sum(len(s) for s in strings) > MAX_INPUT_CHARS:
        _add("input_too_large")

    # 판정도 날짜를 봉인한 뒤에 한다.
    #
    # 봉인 없이 넣으면 아이 생년월일 "2024-05-15"가 계좌번호 정규식에 걸려 매 상담마다
    # `pii_redacted`가 올라온다 — 실제로 마스킹된 것은 아무것도 없는데도. 그 거짓 신호가
    # audit log에 쌓이면 진짜 PII 유출과 구분할 수 없게 된다.
    # (마스킹 자체는 _redact_text가 이미 날짜를 보존하며 처리한다.)
    #
    # 인젝션 판정은 마스킹 전 원문에 한다 — 마스킹된 텍스트로 판정하면 공격 문구가
    # 이미 훼손돼 탐지를 놓칠 수 있다. 날짜 봉인은 공격 문구를 건드리지 않는다.
    for text in strings:
        sealed_text, _ = _seal_dates(text)
        for reason in guard.inspect_input(sealed_text).reasons:
            _add(reason)

    found: set[str] = set()
    sanitized_payload = _redact_recursive(payload, found)
    # PII는 차단 사유가 아니다 (마스킹으로 해소). 인젝션/과대입력만 차단.
    blocking = {"prompt_injection_pattern", "input_too_large", "crescendo_cumulative_risk"}
    blocking.update(r for r in reasons if r.startswith("semantic_"))
    hit = sorted(r for r in reasons if r in blocking)

    # 인젝션류 사유(과대입력 제외)가 3인칭 서술 오탐인지 2차 확인.
    # 강등은 **양성 증거**(한국어 서술형 종결어미 + 조작 신호 부재)가 있을 때만 한다.
    # 난독화 영어·중국어 공격은 이 어미가 없어 강등되지 않고 그대로 차단된다.
    injection_hits = [r for r in hit if r != "input_too_large"]
    blob = " ".join(strings)
    downgraded_fp = False
    if injection_hits and _looks_like_third_person_report(blob):
        # "어린이집이 안전 지침을 무시하고 아이를 방치했습니다" 같은 신고 문장.
        # 차단하지 않고 warning으로 남긴다 (audit엔 기록).
        hit = [r for r in hit if r == "input_too_large"]
        downgraded_fp = True

    enforce = enforcement_enabled()
    allowed = True
    # 안전 신호(학대/응급/자해/가정폭력)가 잡힌 입력은 인젝션 의심이어도 차단하지 않는다.
    # 학대를 신고하려는 부모를 단어 하나로 막는 것이 가장 큰 사고다. 안전 라우팅이
    # 우선한다 (Codex F8).
    if hit and enforce and not safety_triggered:
        allowed = False

    metadata: dict[str, Any] = {}
    if hit:
        metadata["blocking_reasons"] = hit
    if downgraded_fp:
        metadata["injection_downgraded_third_person"] = injection_hits
    if safety_triggered and injection_hits:
        metadata["injection_bypassed_for_safety"] = injection_hits

    return InputVerdict(
        allowed=allowed,
        reasons=reasons,
        sanitized_payload=sanitized_payload,
        pii_types=sorted(found),
        available=True,
        enforced=bool(hit) and enforce and not safety_triggered,
        metadata=metadata,
    )


# === 5. 출력 검사 ===


@dataclass
class OutputVerdict:
    """출력 guard 판정 — 호출자는 sanitized_text를 반드시 써야 한다."""

    allowed: bool = True
    sanitized_text: str = ""
    reasons: list[str] = field(default_factory=list)
    pii_types: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    available: bool = AGENTSHIELD_AVAILABLE

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "available": self.available,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
        }
        if self.pii_types:
            out["pii_types"] = list(self.pii_types)
        if self.unsupported_claims:
            out["unsupported_claims"] = list(self.unsupported_claims)
        return out


# AgentShield의 절대단정 탐지는 영어 표현("100% guaranteed") 위주라, 한국 부모가
# 실제로 읽을 한글 확언을 놓친다. 결정론 계층에서 함께 잡는다. 법적 의무 서술
# ("사용자는 반드시 휴가를 주어야 한다")까지 오탐하지 않도록, 확실성 부사 뒤에
# **사용자에게 유리한 결과 동사**(승소·환불·합격 등)가 붙는 경우만 매칭한다.
_KO_ABSOLUTE_CLAIM_RES = (
    re.compile(r"(?:100|백)\s*(?:%|퍼센트)\s*(?:보장|안전|승소|성공|합법|환불|해결|당첨|확실|완치)"),
    re.compile(r"절대(?:적으로)?\s*(?:안전|실패\s*하지\s*않|문제\s*(?:가)?\s*없|틀리지\s*않|걱정\s*(?:할\s*필요\s*)?없|안\s*(?:걸리|잡히|집니))"),
    re.compile(r"무조건\s*(?:승소|이깁|이길|이기|환불|받으실|받을\s*수\s*있|가능|해결|합격|성공)"),
    re.compile(r"반드시\s*(?:승소|이깁|이길|이기실|환불\s*받|받으실\s*수\s*있|성공|합격)"),
    re.compile(r"틀림없이\s*(?:승소|이깁|받으실|환불|성공|합격)"),
    re.compile(r"확실(?:하게|히)\s*(?:승소|이깁|환불|보장|합격)"),
)


def _detect_korean_absolute_claims(text: str) -> list[str]:
    """한글 근거 없는 절대 단정("100% 승소", "무조건 환불")을 찾아 매칭 구절을 반환."""
    found: list[str] = []
    for pattern in _KO_ABSOLUTE_CLAIM_RES:
        for match in pattern.finditer(text):
            phrase = match.group(0).strip()
            if phrase not in found:
                found.append(phrase)
    return found


def inspect_output_text(text: str) -> OutputVerdict:
    """LLM 답변을 부모 화면에 내보내기 전에 검사.

    - PII / API 키·토큰 유출 마스킹 → sanitized_text (이걸 써야 한다)
    - "100% 보장", "절대 안전" 류 근거 없는 절대 단정 → unsupported_claims
      (법률 안내에서 이 표현이 나가면 그 자체가 사고다)

    시행일·생년월일은 봉인 후 검사하므로 마스킹되지 않는다.
    """
    if not AGENTSHIELD_AVAILABLE or not isinstance(text, str) or not text.strip():
        return OutputVerdict(allowed=True, sanitized_text=text or "", available=AGENTSHIELD_AVAILABLE)

    guard = get_guard()
    sealed_text, sealed = _seal_dates(text)
    decision = guard.inspect_output(sealed_text)

    sanitized = _unseal_dates(decision.sanitized or sealed_text, sealed)
    reasons = list(decision.reasons)
    claims = [r.split(":", 1)[1] for r in reasons if r.startswith("unsupported_claim:")]

    for phrase in _detect_korean_absolute_claims(sanitized):
        if phrase not in claims:
            claims.append(phrase)
            reasons.append(f"unsupported_claim:{phrase}")

    return OutputVerdict(
        allowed=bool(decision.allowed),
        sanitized_text=sanitized,
        reasons=reasons,
        pii_types=list(decision.metadata.get("pii_types", [])),
        unsupported_claims=claims,
        available=True,
    )


# === 6. 안정성 — 재시도 + 회로 차단 ===


class _Permanent(BaseException):
    """재시도해도 소용없는 오류를 retry_call의 `except Exception` 밖으로 빼내는 봉투.

    BaseException을 상속하는 이유가 전부다 — retry_call은 Exception만 잡으므로
    이 봉투는 잡히지 않고 그대로 통과한다. 호출자에게 돌려줄 땐 벗겨서 원래 예외를 던진다.
    """

    def __init__(self, exc: BaseException):
        super().__init__(str(exc))
        self.exc = exc


_BREAKERS: dict[str, Any] = {}


def _breaker(service: str) -> Any:
    if not AGENTSHIELD_AVAILABLE:
        return None
    if service not in _BREAKERS:
        from agent_shield.resilience import CircuitBreaker

        _BREAKERS[service] = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
    return _BREAKERS[service]


def reset_breakers() -> None:
    """테스트용 — 회로 상태 초기화."""
    _BREAKERS.clear()


def resilient_call(
    service: str,
    fn: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    no_retry_on: tuple[type[BaseException], ...] = (),
    **kwargs: Any,
) -> Any:
    """외부 호출을 재시도 + 회로 차단으로 감싼다.

    - 일시적 네트워크 실패는 지수 백오프로 재시도 (기존: 1회 실패 = 그대로 실패)
    - 같은 의존이 연속 5회 죽으면 회로를 열어 30초간 호출을 끊는다
    - `no_retry_on`: 재시도해도 소용없는 오류(인증 실패 등)는 즉시 올린다

    회로 상태의 수명 (정직): `_BREAKERS`는 **프로세스 안에만** 산다. UI(server.ts)는
    상담 1건마다 새 Python 프로세스를 띄우므로, 회로는 **한 상담 안의 반복 호출**에만
    효과가 있다 — 법제처처럼 상담당 최대 15개 법령을 부르는 경로에서는 앞쪽 5회가 죽으면
    뒤쪽을 끊어 예산을 아낀다. 반대로 OpenAI처럼 상담당 1-2회만 부르는 경로에서는 상담
    사이에 상태가 누적되지 않아 효과가 작다. 상담 간 누적이 필요하면 공유 저장소(Redis 등)나
    장기 실행 worker가 있어야 한다(Codex F7).

    AgentShield가 없으면 fn을 그대로 호출한다 — 기존 동작 유지.
    """
    if not AGENTSHIELD_AVAILABLE:
        return fn(*args, **kwargs)

    from agent_shield.resilience import CircuitOpen, RetryExhausted, retry_call

    breaker = _breaker(service)

    def _inner() -> tuple[str, Any]:
        """영구 오류를 회로 차단기에게 **성공으로 보이게** 감싼다.

        핵심은 "400을 장애로 세지 않는다"가 아니라 그 이상이다. 400은 서버가 살아서
        요청을 거절했다는 뜻이므로, 회로 입장에서는 오히려 '서비스 정상'의 증거다.
        그래서 예외로 던지지 않고 ("permanent", exc) 튜플로 **정상 반환**한다.
        그러면 breaker.call은 `_record_success()`를 타고, 특히 half-open probe가
        400을 받아도 슬롯을 정상 반환하며 회로를 닫는다.

        (초기 구현은 _Permanent(BaseException)로 breaker의 except를 건너뛰게 했는데,
        그러면 half-open 상태에서 400 probe가 슬롯을 반환도 실패도 하지 못해 회로가
        영구 고착됐다 — Codex 리뷰가 재현한 F4. "성공 반환"이 그 부작용을 없앤다.)
        """
        try:
            return ("ok", fn(*args, **kwargs))
        except no_retry_on as exc:  # type: ignore[misc]
            return ("permanent", exc)

    def _call_once() -> Any:
        try:
            kind, payload = breaker.call(_inner)
        except CircuitOpen as exc:
            # 회로가 열려 있으면 재시도해봐야 같은 예외를 즉시 다시 받는다.
            raise _Permanent(exc) from exc
        if kind == "permanent":
            # breaker는 성공으로 봤지만 호출자에겐 영구 오류다. retry_call의 except를
            # 건너뛰도록 BaseException 봉투로 즉시 빼낸다 (재시도하지 않는다).
            raise _Permanent(payload)
        return payload

    try:
        return retry_call(
            _call_once,
            max_attempts=max_attempts,
            base_delay=0.2,
            max_delay=2.0,
            retry_on=retry_on,
        )
    except _Permanent as wrapper:
        raise wrapper.exc from None
    except RetryExhausted as exc:
        # 원래 예외를 호출자에게 그대로 보여준다 — RetryExhausted로 감싸면
        # 호출자의 예외 분기(OpenAiError 등)가 전부 깨진다.
        cause = exc.__cause__
        if cause is not None:
            raise cause
        raise


def status() -> dict[str, Any]:
    """리포트/진단에 싣는 배선 상태 — '연결됐다고 주장'하지 말고 실측을 싣는다."""
    return {
        "available": AGENTSHIELD_AVAILABLE,
        "version": AGENTSHIELD_VERSION,
        "injection_enforce": enforcement_enabled(),
        "breakers": {name: b.state for name, b in _BREAKERS.items()},
    }
