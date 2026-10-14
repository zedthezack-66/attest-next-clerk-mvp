from datetime import date

from apps.api.services.parsing import CVParser, summarize_cover_letter
from apps.api.services.parsing.heuristics import heuristic_parse

TODAY = date(2026, 10, 14)


def test_heuristic_parse_strong_cv(fixture_text):
    cv = heuristic_parse(fixture_text("cv_mwila.txt"), ["grant management"], today=TODAY)
    assert cv.contact.full_name == "Mwila Banda"
    assert cv.contact.email == "mwila.banda@example.com"
    assert cv.contact.phone.startswith("+260")
    assert [(e.title, e.institution, e.award_year) for e in cv.education] == [
        ("Bachelor of Accountancy", "Copperbelt University", 2018),
        ("Diploma in Accountancy", "Evelyn Hone College", 2014),
    ]
    assert cv.education[0].classification == "Merit"
    assert cv.education[1].classification is None  # must not bleed from the neighbouring line
    assert {"Excel", "reconciliations", "financial reporting", "grant management"} <= set(cv.skills)
    assert {c.name for c in cv.certifications} >= {"ACCA"}
    assert len(cv.experience) == 2 and cv.experience[0].organisation == "Zambezi Agro Ltd"
    assert cv.total_experience_years == 7.7  # Mar 2019-Dec 2020 + Jan 2021-Oct 2026


def test_overlapping_jobs_are_counted_once():
    text = "EXPERIENCE\nAnalyst, A Ltd, 2018 - 2020\nConsultant, B Ltd, 2019 - 2021\n"
    cv = heuristic_parse(text, today=TODAY)
    assert cv.total_experience_years == 4.0  # Jan 2018 - Dec 2021, not 3 + 3


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.embedding_model = None

    def complete_json(self, system, user):
        return self.response


def test_llm_output_is_used_and_reconciled(fixture_text):
    llm = FakeLLM({
        "contact": {"full_name": "Mwila Banda"},
        "education": [{"title": "Bachelor of Accountancy", "institution": "Copperbelt University", "award_year": 2018}],
        "skills": ["Excel"],
        "total_experience_years": 5,
    })
    cv = CVParser(llm).parse(fixture_text("cv_mwila.txt"))
    assert cv.extraction_method == "llm"
    assert cv.total_experience_years == 5
    assert cv.contact.email == "mwila.banda@example.com"  # backfilled from heuristics
    assert "reconciliations" in cv.skills  # heuristic skills merged in


def test_invalid_llm_output_falls_back_to_heuristics(fixture_text):
    cv = CVParser(FakeLLM({"education": "not-a-list"})).parse(fixture_text("cv_mwila.txt"))
    assert cv.extraction_method == "heuristic"
    assert len(cv.education) == 2


def test_llm_unavailable_falls_back(fixture_text):
    assert CVParser(FakeLLM(None)).parse(fixture_text("cv_mwila.txt")).extraction_method == "heuristic"


def test_cover_letter_summary_is_extractive(fixture_text):
    letter = fixture_text("cover_mwila.txt")
    summary = summarize_cover_letter(letter, "Finance Officer reconciliations IFRS financial reporting budgeting")
    assert summary and "Dear" not in summary and "faithfully" not in summary
    assert all(s.strip() in letter for s in summary.split(". ") if s.strip())


def test_docx_and_unsupported_extraction(fixture_text):
    import io

    from docx import Document

    from apps.api.services.parsing import extract_text

    doc = Document()
    for line in fixture_text("cv_mwila.txt").splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    extracted = extract_text("cv.docx", buf.getvalue())
    assert extracted.method == "direct_text" and "Copperbelt University" in extracted.text
    assert extract_text("cv.xyz", b"data").method == "unsupported"
