from datetime import date

import pytest

from apps.api.services.verification import (
    InstitutionRegistry,
    VerificationStatus,
    infer_zqf_level,
    level_from_requirement,
    verify_qualification,
)
from apps.api.services.verification.zqf import infer_field_of_study

TODAY = date(2026, 10, 14)


@pytest.mark.parametrize("title,level", [
    ("PhD in Economics", 10),
    ("Master of Business Administration", 9),
    ("MBA", 9),
    ("Postgraduate Diploma in Human Resource Management", 8),
    ("BSc (Hons) Computer Science", 8),
    ("Bachelor of Accountancy", 7),
    ("LLB", 7),
    ("Diploma in Accountancy", 6),
    ("Advanced Certificate in Plumbing", 5),
    ("Craft Certificate in Welding", 4),
    ("Grade 12 School Certificate", 3),
])
def test_zqf_levels(title, level):
    assert infer_zqf_level(title).level == level


def test_unmappable_title():
    assert infer_zqf_level("Team player with drive") is None


@pytest.mark.parametrize("value,level", [("Diploma", 6), ("bachelor", 7), (9, 9), ("7", 7), ("Master of Laws", 9), (None, None)])
def test_level_from_requirement(value, level):
    assert level_from_requirement(value) == level


def test_field_of_study():
    assert infer_field_of_study("Bachelor of Accountancy") == "Accountancy"
    assert infer_field_of_study("Bachelor of Science in Computer Science") == "Computer Science"
    assert infer_field_of_study("Bachelor of Science") is None


def test_registry_matches_acronym_alias_and_fuzzy():
    reg = InstitutionRegistry()
    assert reg.match("UNZA")[0].code == "zm-unza"
    assert reg.match("Copperbelt University, Kitwe")[0].code == "zm-cbu"
    rec, score = reg.match("Univeristy of Zambia")  # typo
    assert rec.code == "zm-unza" and score >= 0.8
    rec, score = reg.match("Copperbelt Univ")  # abbreviated: probable, not confident
    assert rec.code == "zm-cbu" and 0.8 <= score < 0.92
    assert reg.match("Hogwarts School of Witchcraft") is None


def test_local_registered_award_is_verified():
    r = verify_qualification("Bachelor of Accountancy", "Copperbelt University", 2018, today=TODAY)
    assert r.status == VerificationStatus.VERIFIED
    assert r.zqf_level == 7 and r.confidence > 0.9


def test_foreign_award_is_recognised_foreign():
    r = verify_qualification("MSc Development Studies", "University of Cape Town", 2015, today=TODAY)
    assert r.status == VerificationStatus.RECOGNISED_FOREIGN
    assert any("foreign" in n.lower() for n in r.notes)


def test_unaccredited_institution_is_unrecognised():
    r = verify_qualification("Master of Business Administration", "Global Pacific Open University", 2020, today=TODAY)
    assert r.status == VerificationStatus.UNRECOGNISED


def test_level_above_institution_ceiling_needs_review():
    # TEVETA college (max ZQF 6) cannot award a bachelor's degree
    r = verify_qualification("Bachelor of Commerce", "Evelyn Hone College", 2016, today=TODAY)
    assert r.status == VerificationStatus.NEEDS_REVIEW
    assert any(c.name == "award_level" and not c.passed for c in r.checks)


def test_award_before_founding_needs_review():
    r = verify_qualification("Bachelor of Arts", "Mulungushi University", 2001, today=TODAY)
    assert r.status == VerificationStatus.NEEDS_REVIEW
    assert any(c.name == "award_year_after_founding" and not c.passed for c in r.checks)


def test_provisional_registration_needs_review():
    r = verify_qualification("Bachelor of Education", "New Horizons University Zambia", 2024, today=TODAY)
    assert r.status == VerificationStatus.NEEDS_REVIEW


def test_unknown_or_missing_institution_is_unverified():
    assert verify_qualification("Diploma in Nursing", "Some Unlisted College", 2019).status == VerificationStatus.UNVERIFIED
    assert verify_qualification("Diploma in Nursing", None).status == VerificationStatus.UNVERIFIED
