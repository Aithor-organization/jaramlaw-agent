from jaramlaw_agent.models import (
    AtomicClaim,
    DraftDocument,
    LawArticle,
    LegalBasis,
    RightsCard,
    SupportMatch,
)
from jaramlaw_agent.verifier import collect_atomic_claims, verify_claims


def _full_basis():
    return LegalBasis(
        law="근로기준법", article="제74조",
        effective_date="2024-10-22",
        source_url="https://www.law.go.kr/lsInfoP.do?lsId=001706",
    )


def test_verify_claims_full_citation_verified():
    claim = AtomicClaim(
        claim_id="c1", statement="x", source_node="support_matches",
        citation=_full_basis(),
    )
    res = verify_claims([claim])
    assert res.verified_count == 1
    assert res.unverifiable_count == 0
    assert claim.status == "verified"


def test_verify_claims_partial():
    partial = LegalBasis(law="근로기준법", article="제74조", effective_date="")
    claim = AtomicClaim(claim_id="c1", statement="x", source_node="x", citation=partial)
    res = verify_claims([claim])
    assert res.partial_count == 1
    assert claim.status == "partial"


def test_verify_claims_unverifiable():
    claim = AtomicClaim(claim_id="c1", statement="x", source_node="x", citation=None)
    res = verify_claims([claim])
    assert res.unverifiable_count == 1
    assert claim.status == "unverifiable"


def test_collect_atomic_claims_from_sources():
    law = LawArticle(
        law_id="x", law_name="근로기준법", article="제74조", title="t",
        effective_date="2024-10-22", text_summary="...",
        source_url="https://www.law.go.kr/",
    )
    support = SupportMatch(
        support_id="s1", name="부모급여", amount_krw=1000000,
        amount_description="월 100만원", condition_summary="만 0세",
        legal_basis=_full_basis(), application_channel="정부24",
    )
    card = RightsCard(
        card_id="r1", title="출산휴가 90일", holder="임산부",
        legal_basis=_full_basis(),
    )
    doc = DraftDocument(
        doc_id="d1", title="환불 요청서", kind="refund_request",
        body_markdown="...",
        legal_basis=[_full_basis()],
    )
    claims = collect_atomic_claims([law], [support], [card], [doc])
    assert len(claims) == 4
    # 모두 verified 가능 (시드 완전)
    res = verify_claims(claims)
    assert res.verified_count == 4
    assert res.verified_ratio == 1.0
