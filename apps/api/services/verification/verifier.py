"""Cross-checks claimed qualifications against the institution registry and the ZQF.

"verified" here means *registry-consistent*: the institution exists, is registered to award at
that level, and the claim has no internal contradictions. It does not prove the certificate is
authentic; that requires a live ZAQA verification request (see `registry_data.py`).
"""

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher
from enum import StrEnum

from .registry_data import CERTIFICATIONS, MOCK_INSTITUTIONS, CertificationRecord, InstitutionRecord
from .zqf import infer_field_of_study, infer_zqf_level


class VerificationStatus(StrEnum):
    VERIFIED = "verified"  # local institution, registered, consistent claim
    RECOGNISED_FOREIGN = "recognised_foreign"  # recognised abroad; ZAQA foreign evaluation advised
    NEEDS_REVIEW = "needs_review"  # matched, but a consistency check failed or the match is fuzzy
    UNVERIFIED = "unverified"  # institution not stated or not in registry
    UNRECOGNISED = "unrecognised"  # institution is deregistered / unaccredited


CONFIDENT_MATCH = 0.92
PROBABLE_MATCH = 0.80

_STOPWORDS = {"the", "of", "and", "&", "for"}


def normalise(name: str) -> str:
    text = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    return " ".join(t for t in text.split() if t not in _STOPWORDS)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class VerificationResult:
    status: VerificationStatus
    confidence: float
    zqf_level: int | None
    zqf_label: str | None
    field_of_study: str | None
    institution: InstitutionRecord | None = None
    match_score: float = 0.0
    checks: list[Check] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def details(self) -> dict:
        return {
            "basis": "registry_consistency",
            "institution_code": self.institution.code if self.institution else None,
            "institution_name": self.institution.name if self.institution else None,
            "regulator": self.institution.regulator if self.institution else None,
            "match_score": round(self.match_score, 3),
            "checks": [asdict(c) for c in self.checks],
            "notes": self.notes,
        }


class InstitutionRegistry:
    def __init__(self, records: tuple[InstitutionRecord, ...] | list[InstitutionRecord] = MOCK_INSTITUTIONS):
        self.records = list(records)
        self._names: list[tuple[str, InstitutionRecord]] = []
        self._acronyms: dict[str, InstitutionRecord] = {}
        for rec in self.records:
            for name in (rec.name, *rec.aliases):
                # Short all-caps aliases (UNZA, CBU) are matched as exact tokens, not fuzzily.
                if name.isupper() and len(name) <= 6:
                    self._acronyms[name] = rec
                else:
                    self._names.append((normalise(name), rec))

    @classmethod
    def from_db(cls, db) -> "InstitutionRegistry":
        from sqlalchemy import select

        from apps.api.models.entities import Institution

        rows = db.scalars(select(Institution)).all()
        if not rows:
            return cls()
        return cls([
            InstitutionRecord(r.code, r.name, r.country_code, r.kind, r.regulator, r.registration_status,
                              r.max_zqf_level, tuple(r.aliases or ()), r.founded_year)
            for r in rows
        ])

    def match(self, raw: str | None) -> tuple[InstitutionRecord, float] | None:
        if not raw or not raw.strip():
            return None
        tokens = set(re.findall(r"[A-Za-z]+", raw))
        for acronym, rec in self._acronyms.items():
            if acronym in tokens:
                return rec, 0.95
        query = normalise(raw)
        best: tuple[InstitutionRecord, float] | None = None
        for name, rec in self._names:
            if name and (name == query):
                return rec, 1.0
            if name and f" {name} " in f" {query} ":
                # Registry name fully contained in the text ("Copperbelt University, Kitwe").
                score = 0.97 + 0.02 * (len(name) / max(len(query), 1))
            else:
                score = SequenceMatcher(None, name, query).ratio()
            if not best or score > best[1]:
                best = (rec, min(score, 0.99))
        if best and best[1] >= PROBABLE_MATCH:
            return best
        return None


class CertificationCatalog:
    def __init__(self, records: tuple[CertificationRecord, ...] = CERTIFICATIONS):
        self.records = records
        self._patterns = [
            (re.compile(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", 0 if name.isupper() else re.I), rec)
            for rec in records
            for name in sorted((rec.name, *rec.aliases), key=len, reverse=True)
        ]

    def find_all(self, text: str) -> list[CertificationRecord]:
        found: dict[str, CertificationRecord] = {}
        for pattern, rec in self._patterns:
            if rec.code not in found and pattern.search(text):
                found[rec.code] = rec
        return list(found.values())

    def resolve(self, name: str) -> CertificationRecord | None:
        hits = self.find_all(name)
        return hits[0] if hits else None


def verify_qualification(
    title: str,
    institution_raw: str | None,
    award_year: int | None = None,
    registry: InstitutionRegistry | None = None,
    today: date | None = None,
) -> VerificationResult:
    registry = registry or InstitutionRegistry()
    today = today or date.today()
    zqf = infer_zqf_level(title)
    result = VerificationResult(
        status=VerificationStatus.UNVERIFIED,
        confidence=0.2,
        zqf_level=zqf.level if zqf else None,
        zqf_label=zqf.label if zqf else None,
        field_of_study=infer_field_of_study(title),
    )
    if not zqf:
        result.notes.append("Award level could not be mapped to the ZQF.")

    match = registry.match(institution_raw)
    if not institution_raw:
        result.notes.append("No awarding institution stated; manual ZAQA verification required.")
        return result
    if not match:
        result.confidence = 0.3
        result.notes.append(f"'{institution_raw}' not found in the institution registry; submit to ZAQA for verification.")
        return result

    inst, score = match
    result.institution, result.match_score = inst, score

    if inst.registration_status in {"deregistered", "unaccredited"}:
        result.status = VerificationStatus.UNRECOGNISED
        result.confidence = round(score, 3)
        result.checks.append(Check("registration", False, f"{inst.name} is {inst.registration_status}."))
        return result

    result.checks.append(Check("match_confidence", score >= CONFIDENT_MATCH,
                               f"Matched '{institution_raw}' to {inst.name} ({score:.0%})."))
    result.checks.append(Check("registration", inst.registration_status != "provisional",
                               f"{inst.regulator} status: {inst.registration_status}."))
    if zqf:
        result.checks.append(Check("award_level", zqf.level <= inst.max_zqf_level,
                                   f"ZQF level {zqf.level} claimed; institution awards up to level {inst.max_zqf_level}."))
    if award_year:
        if inst.founded_year:
            result.checks.append(Check("award_year_after_founding", award_year >= inst.founded_year,
                                       f"Awarded {award_year}; institution established {inst.founded_year}."))
        result.checks.append(Check("award_year_not_future", award_year <= today.year,
                                   f"Award year {award_year}."))

    failed = [c for c in result.checks if not c.passed]
    result.confidence = round(max(0.1, score * (1 - 0.2 * len(failed))), 3)
    if failed:
        result.status = VerificationStatus.NEEDS_REVIEW
    elif inst.regulator == "FOREIGN":
        result.status = VerificationStatus.RECOGNISED_FOREIGN
        result.notes.append("Foreign award: ZAQA recognition/evaluation of foreign qualifications recommended.")
    else:
        result.status = VerificationStatus.VERIFIED
    return result
