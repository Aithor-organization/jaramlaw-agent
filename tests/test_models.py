from dataclasses import asdict

from jaramlaw_agent.models import (
    Child,
    FamilyProfile,
    LegalBasis,
    Parent,
    LawArticle,
)


def test_family_profile_serializable():
    p = FamilyProfile(
        parents=[Parent(role="mother", age=32)],
        children=[Child(name_masked="C1", birth_date="2024-05-01")],
    )
    d = p.to_dict()
    assert d["parents"][0]["role"] == "mother"
    assert d["children"][0]["name_masked"] == "C1"


def test_legal_basis_is_complete():
    full = LegalBasis(law="L", article="A", effective_date="2024-01-01", source_url="https://x")
    partial = LegalBasis(law="L", article="A", effective_date="")
    assert full.is_complete()
    assert not partial.is_complete()


def test_law_article_to_legal_basis():
    law = LawArticle(
        law_id="x", law_name="근로기준법", article="제74조", title="t",
        effective_date="2024-10-22", text_summary="s",
        source_url="https://www.law.go.kr/",
    )
    lb = law.to_legal_basis()
    assert lb.law == "근로기준법"
    assert lb.article == "제74조"
    assert lb.is_complete()
