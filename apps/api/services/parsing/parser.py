"""CV parsing entry point: LLM extraction when configured, heuristic extraction otherwise.

The LLM only *extracts*. ZQF levels, verification and scoring are always computed by
deterministic code downstream, so a model hallucination cannot mark a degree as verified.
"""

import json
import logging
import re

from pydantic import ValidationError

from apps.api.services.llm import LLMClient
from apps.api.services.similarity import lexical_similarity, sentences

from .heuristics import heuristic_parse
from .schemas import ParsedCV

log = logging.getLogger(__name__)

CV_SYSTEM_PROMPT = """You extract structured data from CVs/resumes for an applicant tracking system in Zambia.
Return ONLY a JSON object matching this JSON Schema:
{schema}
Rules:
- Copy institution names and award titles exactly as written; do not correct, expand or guess them.
- Use null for anything not stated. Never invent dates, grades or institutions.
- experience[].start / end as "YYYY-MM" or "YYYY"; end = "present" for current roles.
- total_experience_years: sum of non-overlapping paid work experience, in years.
- Leave field_confidences empty and extraction_method as "llm"."""

MAX_CV_CHARS = 24_000


class CVParser:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm

    @classmethod
    def from_env(cls) -> "CVParser":
        return cls(LLMClient.from_env())

    def parse(self, text: str, skill_vocabulary: list[str] | None = None) -> ParsedCV:
        heuristic = heuristic_parse(text, skill_vocabulary)
        if not self.llm or not text.strip():
            return heuristic
        schema = ParsedCV.model_json_schema()
        schema["properties"].pop("field_confidences", None)
        raw = self.llm.complete_json(CV_SYSTEM_PROMPT.format(schema=json.dumps(schema)), text[:MAX_CV_CHARS])
        if raw is None:
            return heuristic
        try:
            parsed = ParsedCV.model_validate(raw)
        except ValidationError as exc:
            log.warning("LLM CV output failed validation, using heuristics: %s", exc)
            return heuristic
        return _reconcile(parsed, heuristic)


def _reconcile(llm: ParsedCV, heuristic: ParsedCV) -> ParsedCV:
    """Prefer LLM structure, but keep deterministic signals the LLM missed."""
    llm.extraction_method = "llm"
    llm.contact.email = llm.contact.email or heuristic.contact.email
    llm.contact.phone = llm.contact.phone or heuristic.contact.phone
    known = {s.lower() for s in llm.skills}
    llm.skills += [s for s in heuristic.skills if s.lower() not in known]
    known_certs = {c.name.lower() for c in llm.certifications}
    llm.certifications += [c for c in heuristic.certifications if c.name.lower() not in known_certs]
    if not llm.total_experience_years and heuristic.total_experience_years:
        llm.total_experience_years = heuristic.total_experience_years
    llm.field_confidences = {k: min(0.95, v + 0.1) for k, v in heuristic.field_confidences.items()}
    return llm


def summarize_cover_letter(text: str | None, job_text: str, llm: LLMClient | None = None, max_sentences: int = 3) -> str | None:
    """Short recruiter-facing summary. LLM when available, else the most job-relevant sentences."""
    if not text or not text.strip():
        return None
    if llm:
        out = llm.complete_json(
            'Summarise this cover letter for a recruiter in at most 3 sentences, focusing on evidence relevant to the job. '
            'Return JSON {"summary": "..."}. Do not add facts that are not in the letter.',
            f"JOB:\n{job_text[:4000]}\n\nCOVER LETTER:\n{text[:8000]}",
        )
        if out and isinstance(out.get("summary"), str):
            return out["summary"].strip()
    candidates = [s for s in sentences(text) if len(s.split()) >= 6 and not re.match(r"^(dear|yours|sincerely|kind regards)", s, re.I)]
    ranked = sorted(candidates, key=lambda s: lexical_similarity(s, job_text), reverse=True)[:max_sentences]
    ordered = [s for s in candidates if s in ranked]  # keep original order for readability
    return " ".join(ordered) or None
