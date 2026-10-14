"""Score a candidate against a job from local files, without a database.

    python -m apps.api.scripts.score_candidate \
        --job apps/api/tests/fixtures/finance_officer_job.json \
        --cv apps/api/tests/fixtures/cv_mwila.txt \
        --cover-letter apps/api/tests/fixtures/cover_mwila.txt [--json]

Job JSON keys: title, description, required_skills, preferred_skills, min_years_experience,
min_qualification (ZQF level or label), preferred_fields_of_study, required_certifications,
preferred_certifications, optional scoring_weights.
"""

import argparse
import json
import sys
from pathlib import Path

from apps.api.services.parsing import CVParser, extract_text
from apps.api.services.scoring import CandidateEvidence, JobCriteria, QualificationEvidence, ScoringWeights, score_candidate
from apps.api.services.similarity import similarity_from_env
from apps.api.services.verification import level_from_requirement, verify_qualification


def load_job(path: Path) -> tuple[JobCriteria, ScoringWeights]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    criteria = JobCriteria(
        title=raw["title"],
        description=raw["description"],
        required_skills=raw.get("required_skills", []),
        preferred_skills=raw.get("preferred_skills", []),
        min_years_experience=raw.get("min_years_experience", 0),
        min_zqf_level=level_from_requirement(raw.get("min_qualification")),
        preferred_fields_of_study=raw.get("preferred_fields_of_study", []),
        required_certifications=raw.get("required_certifications", []),
        preferred_certifications=raw.get("preferred_certifications", []),
    )
    return criteria, ScoringWeights(**raw["scoring_weights"]) if raw.get("scoring_weights") else ScoringWeights()


def read_document(path: Path) -> str:
    extracted = extract_text(path.name, path.read_bytes())
    if not extracted.text.strip():
        sys.exit(f"Could not extract text from {path} (method: {extracted.method})")
    return extracted.text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", type=Path, required=True)
    ap.add_argument("--cv", type=Path, required=True)
    ap.add_argument("--cover-letter", type=Path)
    ap.add_argument("--json", action="store_true", help="print the full machine-readable result")
    args = ap.parse_args(argv)

    criteria, weights = load_job(args.job)
    cv = CVParser.from_env().parse(read_document(args.cv), criteria.required_skills + criteria.preferred_skills)
    verified = [(e, verify_qualification(e.title, e.institution, e.award_year)) for e in cv.education]
    evidence = CandidateEvidence(
        skills=cv.skills,
        total_experience_years=cv.total_experience_years,
        qualifications=[QualificationEvidence(e.title, r.zqf_level, r.status, e.institution, r.field_of_study) for e, r in verified],
        certifications=[c.name for c in cv.certifications],
        cover_letter_text=read_document(args.cover_letter) if args.cover_letter else None,
    )
    result = score_candidate(criteria, evidence, weights, similarity_from_env())

    if args.json:
        print(json.dumps({
            "candidate": cv.model_dump(exclude={"field_confidences"}),
            "verification": [{"title": e.title, "status": r.status.value, "zqf_level": r.zqf_level, **r.details()} for e, r in verified],
            "score": result.to_dict(),
        }, indent=2, default=str))
        return 0

    print(f"\n{cv.contact.full_name or args.cv.name} -> {criteria.title}")
    print(f"Candidate Fit Score: {result.total:.1f} / 100  ({result.version}, parser: {cv.extraction_method})\n")
    for name, c in result.components.items():
        print(f"  {name:<18} {c.points:5.1f} / {c.weight * 100:4.0f}   {c.explanation}")
    print("\nQualifications:")
    for e, r in verified:
        inst = r.institution.name if r.institution else (e.institution or "institution not stated")
        print(f"  [{r.status.value:<18}] {e.title} - {inst} (ZQF {r.zqf_level or '?'}, confidence {r.confidence:.0%})")
    if result.flags:
        print("\nFlags for reviewer:")
        for f in result.flags:
            print(f"  - {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
