import pytest

from apps.api.services.scoring import (
    CandidateEvidence,
    JobCriteria,
    QualificationEvidence,
    ScoringWeights,
    score_candidate,
)
from apps.api.services.similarity import lexical_similarity
from apps.api.services.verification import VerificationStatus as VS

JOB = JobCriteria(
    title="Finance Officer",
    description="Manage bank reconciliations, monthly financial reporting under IFRS, budgeting and grant controls.",
    required_skills=["Excel", "financial reporting", "reconciliations"],
    preferred_skills=["IFRS", "budgeting"],
    min_years_experience=3,
    min_zqf_level=7,
    preferred_fields_of_study=["Accountancy"],
    preferred_certifications=["ACCA"],
)
LETTER = (
    "I have five years of experience in monthly financial reporting under IFRS, bank reconciliations and budgeting. "
    "I built Excel budgeting models and supported grant controls and external audits for donor-funded programmes. "
    "I would bring strong reconciliations discipline and reporting accuracy to the Finance Officer role and your team. "
) * 2


def candidate(**overrides) -> CandidateEvidence:
    base = dict(
        skills=["Excel", "financial reporting", "reconciliations", "IFRS", "budgeting"],
        total_experience_years=5,
        qualifications=[QualificationEvidence("Bachelor of Accountancy", 7, VS.VERIFIED, "Copperbelt University", "Accountancy")],
        certifications=["ACCA"],
        cover_letter_text=LETTER,
    )
    return CandidateEvidence(**(base | overrides))


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        ScoringWeights(skills_experience=0.5, cover_letter=0.5, education=0.5, certifications=0)


def test_components_sum_to_total_and_use_brief_weights():
    result = score_candidate(JOB, candidate())
    assert {k: c.weight for k, c in result.components.items()} == {
        "skills_experience": 0.40, "cover_letter": 0.20, "education": 0.30, "certifications": 0.10}
    assert result.total == pytest.approx(sum(c.points for c in result.components.values()), abs=0.1)
    assert 0 <= result.total <= 100


def test_ideal_candidate_scores_high_with_no_flags():
    result = score_candidate(JOB, candidate())
    assert result.total >= 90
    assert result.flags == []


def test_verification_status_drives_education_score():
    def edu(status):
        q = [QualificationEvidence("Bachelor of Accountancy", 7, status, "X", "Accountancy")]
        return score_candidate(JOB, candidate(qualifications=q)).components["education"].score

    assert edu(VS.VERIFIED) > edu(VS.RECOGNISED_FOREIGN) > edu(VS.NEEDS_REVIEW) > edu(VS.UNVERIFIED) > edu(VS.UNRECOGNISED) == 0


def test_unrecognised_degree_does_not_satisfy_minimum_level():
    q = [QualificationEvidence("MBA", 9, VS.UNRECOGNISED, "Global Pacific Open University")]
    result = score_candidate(JOB, candidate(qualifications=q))
    assert any("ZQF level 7" in f for f in result.flags)
    assert any("unrecognised" in f for f in result.flags)


def test_below_required_level_is_penalised_not_zeroed():
    q = [QualificationEvidence("Diploma in Accountancy", 6, VS.VERIFIED, "Evelyn Hone College", "Accountancy")]
    edu = score_candidate(JOB, candidate(qualifications=q)).components["education"]
    assert 0 < edu.score < 1


def test_missing_required_skill_and_experience_are_flagged():
    result = score_candidate(JOB, candidate(skills=["Excel"], total_experience_years=1))
    assert any("Missing required skill" in f for f in result.flags)
    assert any("yrs experience" in f for f in result.flags)
    assert result.components["skills_experience"].score < 0.5


def test_missing_cover_letter_scores_zero_for_that_component():
    result = score_candidate(JOB, candidate(cover_letter_text=None))
    assert result.components["cover_letter"].score == 0
    assert "No cover letter provided" in result.flags


def test_irrelevant_cover_letter_scores_lower_than_relevant():
    off_topic = ("I love cooking and have run a bakery for many years, decorating cakes for weddings and parties. " * 4)
    relevant = score_candidate(JOB, candidate()).components["cover_letter"].score
    irrelevant = score_candidate(JOB, candidate(cover_letter_text=off_topic)).components["cover_letter"].score
    assert relevant > 0.7 > 0.2 > irrelevant


def test_lexical_similarity_is_bounded():
    assert lexical_similarity("", "anything") == 0
    assert lexical_similarity(JOB.description, JOB.description) == 1


def test_certification_aliases_resolve():
    result = score_candidate(JOB, candidate(certifications=["Chartered Certified Accountant"]))
    assert result.components["certifications"].score == 1


def test_custom_weights_change_total():
    edu_heavy = ScoringWeights(skills_experience=0.1, cover_letter=0.1, education=0.7, certifications=0.1)
    no_letter = candidate(cover_letter_text=None)
    assert score_candidate(JOB, no_letter, edu_heavy).total > score_candidate(JOB, no_letter).total
