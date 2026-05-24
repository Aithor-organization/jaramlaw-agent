"""verifier — Atomic Claim Citation 검증.

Constitution 원칙 2 강제. 모든 법령 관련 claim은 (law, article, effective_date, source_url) 인용을 가져야 한다.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from .models import (
    AtomicClaim,
    DraftDocument,
    LawArticle,
    LegalBasis,
    RightsCard,
    SupportMatch,
    VerifierResults,
)


def _short_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _classify_citation(basis: Optional[LegalBasis]) -> str:
    """citation 완성도 → status."""
    if basis is None:
        return "unverifiable"
    has_law = bool(basis.law)
    has_article = bool(basis.article)
    has_effective = bool(basis.effective_date)
    has_url = bool(basis.source_url)
    count = sum([has_law, has_article, has_effective, has_url])
    if count == 4:
        return "verified"
    if count >= 2:
        return "partial"
    return "unverifiable"


def collect_atomic_claims(
    matched_laws: list[LawArticle],
    support_matches: list[SupportMatch],
    rights_cards: list[RightsCard],
    draft_documents: list[DraftDocument],
) -> list[AtomicClaim]:
    """4 출력 소스에서 atomic claim 추출."""
    claims: list[AtomicClaim] = []

    # 1) 매칭된 법령 자체가 1 claim
    for law in matched_laws:
        basis = law.to_legal_basis()
        statement = f"{law.law_name} {law.article} '{law.title}' 적용됨"
        claims.append(AtomicClaim(
            claim_id=f"law-{_short_id(statement)}",
            statement=statement,
            source_node="matched_laws",
            citation=basis,
            status="unverifiable",  # 다음 단계에서 갱신
            reasoning="법령 시드에서 retrieval됨",
        ))

    # 2) 지원 매칭 — 각 매치는 legal_basis claim
    for s in support_matches:
        statement = f"{s.name}: 자격 충족 (조건 — {s.condition_summary})"
        claims.append(AtomicClaim(
            claim_id=f"support-{_short_id(s.support_id)}",
            statement=statement,
            source_node="support_matches",
            citation=s.legal_basis,
            status="unverifiable",
            reasoning="; ".join(s.eligibility_evidence) if s.eligibility_evidence else "자동 매칭",
        ))

    # 3) 권리 카드 — 각 카드는 1 claim
    for c in rights_cards:
        statement = f"권리: {c.title}"
        claims.append(AtomicClaim(
            claim_id=f"rights-{_short_id(c.card_id)}",
            statement=statement,
            source_node="rights_cards",
            citation=c.legal_basis,
            status="unverifiable",
        ))

    # 4) 초안 문서 — 각 legal_basis가 별도 claim
    for d in draft_documents:
        for i, lb in enumerate(d.legal_basis):
            statement = f"초안 '{d.title}'에서 {lb.law} {lb.article} 인용"
            claims.append(AtomicClaim(
                claim_id=f"doc-{_short_id(d.doc_id)}-{i}",
                statement=statement,
                source_node="draft_documents",
                citation=lb,
                status="unverifiable",
            ))

    return claims


def verify_claims(claims: list[AtomicClaim]) -> VerifierResults:
    """모든 claim의 citation 완성도 검사 + 통계."""
    verified = partial = unverifiable = 0
    for c in claims:
        status = _classify_citation(c.citation)
        c.status = status
        if status == "verified":
            verified += 1
            c.reasoning = c.reasoning or "law/article/effective_date/source_url 모두 존재"
        elif status == "partial":
            partial += 1
            c.reasoning = (
                c.reasoning + "; " if c.reasoning else ""
            ) + "citation 일부 누락 (시행일 또는 출처 URL)"
        else:
            unverifiable += 1
            c.reasoning = (
                c.reasoning + "; " if c.reasoning else ""
            ) + "citation 부재 또는 부족"

    total = max(1, len(claims))
    verified_ratio = round(verified / total, 4)

    return VerifierResults(
        atomic_claims=claims,
        verified_count=verified,
        partial_count=partial,
        unverifiable_count=unverifiable,
        verified_ratio=verified_ratio,
    )


def verify_claims_with_retry(
    claims: list[AtomicClaim],
    *,
    max_attempts: int = 3,
) -> VerifierResults:
    """Run the citation verifier with an explicit bounded retry record.

    The deterministic workflow does not invent missing citations during retry.
    It re-runs the same verifier and records the retry loop so downstream
    gates can distinguish "not attempted" from "attempted and still blocked".
    """
    attempts: list[dict[str, Any]] = []
    final = verify_claims(claims)
    attempts.append({"attempt": 1, **final.summarize()})

    while final.unverifiable_count > 0 and len(attempts) < max(1, max_attempts):
        final = verify_claims(claims)
        attempts.append({"attempt": len(attempts) + 1, **final.summarize()})

    final.retry_summary = {
        "max_attempts": max_attempts,
        "attempts_used": len(attempts),
        "resolved": final.unverifiable_count == 0,
        "history": attempts,
    }
    return final
