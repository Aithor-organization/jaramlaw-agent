"""document_drafter — 육아휴직/학교폭력 draft + dispatcher 나머지 분기 보강.

기존 test_document_drafter.py가 academy/daycare/cctv를 커버하므로,
여기선 미커버였던 parental_leave / school_violence / unknown 분기만 추가.
"""

from __future__ import annotations

import pytest

from jaramlaw_agent.document_drafter import (
    draft_documents_for_scenario,
    draft_parental_leave_application,
    draft_school_violence_report,
)
from jaramlaw_agent.family_context import build_family_profile


@pytest.fixture
def profile():
    return build_family_profile({
        "reference_date": "2026-05-24",
        "parents": [{"role": "mother", "age": 33, "employment": "정규직"}],
        "children": [{"name_masked": "C1", "birth_date": "2020-05-01"}],
    })


def test_parental_leave_application(profile):
    doc = draft_parental_leave_application(profile, {})
    assert doc.kind == "parental_leave_application"
    assert "육아휴직" in doc.body_markdown
    assert doc.signature_required is True
    assert any(lb.law and lb.article for lb in doc.legal_basis)
    assert "법률 자문이 아닙니다" in doc.body_markdown


def test_school_violence_report(profile):
    doc = draft_school_violence_report(profile, {})
    assert doc.kind == "school_violence_report"
    assert "학교폭력" in doc.body_markdown
    assert doc.legal_basis


def test_dispatcher_parental_leave(profile):
    docs = draft_documents_for_scenario("parental_leave_denied", profile, {})
    assert len(docs) == 1
    assert docs[0].kind == "parental_leave_application"


def test_dispatcher_school_violence(profile):
    docs = draft_documents_for_scenario("school_violence", profile, {})
    assert len(docs) == 1
    assert docs[0].kind == "school_violence_report"


def test_dispatcher_unknown_returns_empty(profile):
    assert draft_documents_for_scenario("unknown_scenario_xyz", profile, {}) == []
