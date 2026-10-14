"""Multi-factor Candidate Fit Score (0-100).

    Skills & experience match          40%
    Cover letter relevance (semantic)  20%
    Verified education / ZQF alignment 30%
    Additional certifications          10%

Each component produces a 0..1 sub-score plus a plain-language explanation, so recruiters can
see *why* a candidate ranked where they did. Missing requirements raise flags; they never
silently zero the score, so a human stays in the loop for every rejection.
"""

import re
from dataclasses import asdict, dataclass, field

from apps.api.services.similarity import LexicalSimilarity, Similarity
from apps.api.services.verification.verifier import CertificationCatalog, VerificationStatus
from apps.api.services.verification.zqf import ZQF_LEVEL_LABELS

SCORING_VERSION = "fit-v1"

VERIFICATION_TRUST = {
    VerificationStatus.VERIFIED: 1.0,
    VerificationStatus.RECOGNISED_FOREIGN: 0.9,
    VerificationStatus.NEEDS_REVIEW: 0.6,
    VerificationStatus.UNVERIFIED: 0.4,
    VerificationStatus.UNRECOGNISED: 0.0,
}
DEFAULT_MIN_ZQF_LEVEL = 6  # Diploma, when a job doesn't specify one


@dataclass(frozen=True)
class ScoringWeights:
    skills_experience: float = 0.40
    cover_letter: float = 0.20
    education: float = 0.30
    certifications: float = 0.10

    def __post_init__(self):
        total = self.skills_experience + self.cover_letter + self.education + self.certifications
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Scoring weights must sum to 1.0 (got {total:.3f})")
        if min(self.skills_experience, self.cover_letter, self.education, self.certifications) < 0:
            raise ValueError("Scoring weights must be non-negative")


@dataclass
class JobCriteria:
    title: str
    description: str
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    min_years_experience: float = 0.0
    min_zqf_level: int | None = None
    preferred_fields_of_study: list[str] = field(default_factory=list)
    required_certifications: list[str] = field(default_factory=list)
    preferred_certifications: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join([self.title, self.description, *self.required_skills, *self.preferred_skills])


@dataclass
class QualificationEvidence:
    title: str
    zqf_level: int | None
    verification_status: VerificationStatus
    institution: str | None = None
    field_of_study: str | None = None


@dataclass
class CandidateEvidence:
    skills: list[str]
    total_experience_years: float
    qualifications: list[QualificationEvidence]
    certifications: list[str]
    cover_letter_text: str | None = None


@dataclass
class ComponentScore:
    score: float  # 0..1
    weight: float
    points: float  # contribution to the 0-100 total
    explanation: str
    details: dict = field(default_factory=dict)


@dataclass
class ScoreResult:
    total: float
    components: dict[str, ComponentScore]
    flags: list[str]
    version: str = SCORING_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _has(items: set[str], wanted: str) -> bool:
    w = _norm(wanted)
    return any(w == i or re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", i) for i in items)


def _weighted_coverage(have: set[str], required: list[str], preferred: list[str]) -> tuple[float, list[str], list[str]]:
    """Required items count double. Returns (coverage, matched, missing_required)."""
    matched = [s for s in required + preferred if _has(have, s)]
    missing_required = [s for s in required if not _has(have, s)]
    total = 2 * len(required) + len(preferred)
    got = 2 * (len(required) - len(missing_required)) + sum(1 for s in preferred if _has(have, s))
    return (got / total if total else 1.0), matched, missing_required


def score_skills_experience(job: JobCriteria, cand: CandidateEvidence, flags: list[str]) -> tuple[float, str, dict]:
    have = {_norm(s) for s in cand.skills}
    coverage, matched, missing = _weighted_coverage(have, job.required_skills, job.preferred_skills)
    if job.min_years_experience > 0:
        experience_fit = min(1.0, cand.total_experience_years / job.min_years_experience)
    else:
        experience_fit = 1.0
    score = 0.7 * coverage + 0.3 * experience_fit
    if missing:
        flags.append(f"Missing required skill(s): {', '.join(missing)}")
    if cand.total_experience_years < job.min_years_experience:
        flags.append(f"{cand.total_experience_years:g} yrs experience vs {job.min_years_experience:g} required")
    explanation = (f"Matched {len(matched)}/{len(job.required_skills) + len(job.preferred_skills)} listed skills"
                   if job.required_skills or job.preferred_skills else "No skill criteria set on the job")
    explanation += f"; {cand.total_experience_years:g} yrs experience (min {job.min_years_experience:g})."
    return score, explanation, {
        "skill_coverage": round(coverage, 3), "experience_fit": round(experience_fit, 3),
        "matched_skills": matched, "missing_required_skills": missing,
        "experience_years": cand.total_experience_years,
    }


def score_cover_letter(job: JobCriteria, cand: CandidateEvidence, similarity: Similarity, flags: list[str]) -> tuple[float, str, dict]:
    text = (cand.cover_letter_text or "").strip()
    if not text:
        flags.append("No cover letter provided")
        return 0.0, "No cover letter provided.", {}
    semantic = similarity(text, job.text)
    skills = job.required_skills + job.preferred_skills
    mentioned = [s for s in skills if re.search(rf"(?<![a-z]){re.escape(s.lower())}(?![a-z])", text.lower())]
    mention_ratio = len(mentioned) / len(skills) if skills else semantic
    words = len(text.split())
    length_factor = 0.7 if words < 80 else 1.0
    score = (0.75 * semantic + 0.25 * mention_ratio) * length_factor
    explanation = f"Relevance to job {semantic:.0%} ({getattr(similarity, 'name', 'custom')}); mentions {len(mentioned)} key skills"
    explanation += "; letter is very short." if length_factor < 1 else "."
    return score, explanation, {"semantic_relevance": round(semantic, 3), "skills_mentioned": mentioned,
                                "word_count": words, "method": getattr(similarity, "name", "custom")}


def _level_fit(level: int | None, target: int) -> float:
    if level is None:
        return 0.2
    gap = target - level
    return 1.0 if gap <= 0 else 0.6 if gap == 1 else 0.3 if gap == 2 else 0.1


def _field_relevant(field_of_study: str | None, title: str, preferred: list[str]) -> bool:
    haystack = _norm(f"{field_of_study or ''} {title}")
    return any(_norm(p) in haystack or any(w in haystack for w in _norm(p).split() if len(w) > 4) for p in preferred)


def score_education(job: JobCriteria, cand: CandidateEvidence, flags: list[str]) -> tuple[float, str, dict]:
    if not cand.qualifications:
        flags.append("No academic qualifications found")
        return 0.0, "No academic qualifications found.", {}
    target = job.min_zqf_level or DEFAULT_MIN_ZQF_LEVEL
    best, best_q, best_parts = -1.0, None, {}
    for q in cand.qualifications:
        level_fit = _level_fit(q.zqf_level, target)
        trust = VERIFICATION_TRUST[VerificationStatus(q.verification_status)]
        relevant = _field_relevant(q.field_of_study, q.title, job.preferred_fields_of_study) if job.preferred_fields_of_study else None
        field_factor = 1.0 if relevant in (None, True) else 0.85
        s = level_fit * trust * field_factor
        if s > best:
            best, best_q = s, q
            best_parts = {"level_fit": level_fit, "verification_trust": trust, "field_relevant": relevant}
        if q.verification_status == VerificationStatus.UNRECOGNISED:
            flags.append(f"'{q.title}' is from an unrecognised/deregistered institution ({q.institution})")
        elif q.verification_status == VerificationStatus.NEEDS_REVIEW:
            flags.append(f"'{q.title}' needs manual verification")
    credible = [q for q in cand.qualifications if q.verification_status != VerificationStatus.UNRECOGNISED]
    if job.min_zqf_level and not any((q.zqf_level or 0) >= job.min_zqf_level for q in credible):
        flags.append(f"No qualification at ZQF level {job.min_zqf_level} ({ZQF_LEVEL_LABELS.get(job.min_zqf_level)}) or above")
    level_txt = f"ZQF {best_q.zqf_level}" if best_q.zqf_level else "unmapped level"
    explanation = (f"Best: {best_q.title} ({level_txt}, {VerificationStatus(best_q.verification_status).value}) "
                   f"vs required ZQF {target}.")
    return best, explanation, {"best_qualification": best_q.title, "target_zqf_level": target, **best_parts}


def score_certifications(job: JobCriteria, cand: CandidateEvidence, flags: list[str]) -> tuple[float, str, dict]:
    catalog = CertificationCatalog()
    # Resolve aliases so "Chartered Certified Accountant" satisfies a job asking for "ACCA".
    def canon(name: str) -> str:
        rec = catalog.resolve(name)
        return _norm(rec.name if rec else name)

    have = {canon(c) for c in cand.certifications}
    required = [canon(c) for c in job.required_certifications]
    preferred = [canon(c) for c in job.preferred_certifications]
    if not required and not preferred:
        score = min(1.0, 0.5 + 0.25 * len(have))
        return score, f"No certifications required; {len(have)} recognised certification(s) held.", {"held": sorted(have)}
    coverage, matched, missing = _weighted_coverage(have, required, preferred)
    if missing:
        flags.append(f"Missing required certification(s): {', '.join(missing)}")
    return coverage, f"Holds {len(matched)}/{len(required) + len(preferred)} listed certifications.", {
        "held": sorted(have), "matched": matched, "missing_required": missing}


def score_candidate(job: JobCriteria, cand: CandidateEvidence, weights: ScoringWeights | None = None,
                    similarity: Similarity | None = None) -> ScoreResult:
    weights = weights or ScoringWeights()
    similarity = similarity or LexicalSimilarity()
    flags: list[str] = []
    parts = {
        "skills_experience": (weights.skills_experience, score_skills_experience(job, cand, flags)),
        "cover_letter": (weights.cover_letter, score_cover_letter(job, cand, similarity, flags)),
        "education": (weights.education, score_education(job, cand, flags)),
        "certifications": (weights.certifications, score_certifications(job, cand, flags)),
    }
    components = {
        name: ComponentScore(score=round(s, 4), weight=w, points=round(s * w * 100, 2), explanation=expl, details=details)
        for name, (w, (s, expl, details)) in parts.items()
    }
    total = round(sum(c.score * c.weight for c in components.values()) * 100, 1)
    return ScoreResult(total=total, components=components, flags=flags)
