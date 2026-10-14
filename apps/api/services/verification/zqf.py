"""Zambia Qualifications Framework (ZQF) level inference.

ZAQA's framework has 10 levels. This mapping is an indicative Phase 1 approximation used to
compare a claimed award against a job's minimum level; it is not a ZAQA determination.
"""

import re
from dataclasses import dataclass

ZQF_LEVEL_LABELS = {
    1: "Grade 7 / Basic",
    2: "Grade 9 / Junior Secondary",
    3: "Grade 12 / School Certificate",
    4: "Craft Certificate",
    5: "Advanced / Technician Certificate",
    6: "Diploma",
    7: "Bachelor's Degree",
    8: "Bachelor Honours / Postgraduate Diploma",
    9: "Master's Degree",
    10: "Doctorate",
}

# Order matters: more specific awards must be tested before the generic ones they contain
# (e.g. "Postgraduate Diploma" before "Diploma", "School Certificate" before "Certificate").
_PATTERNS: list[tuple[int, str, re.Pattern]] = [
    (10, "Doctorate", re.compile(r"\b(ph\.?\s?d|d\.?phil|doctorate|doctor of (?!medicine))", re.I)),
    (9, "Master's Degree", re.compile(r"\b(masters?|m\.?sc|mba|m\.?phil|llm|m\.?ed|m\.?a)\b|\bmaster of\b", re.I)),
    (8, "Honours / Postgraduate Diploma", re.compile(r"\b(post\s?-?graduate diploma|pgd[e]?|honours|hons)\b", re.I)),
    (7, "Bachelor's Degree", re.compile(r"\b(bachelor|b\.?sc|b\.?eng|b\.?com|b\.?ed|b\.?a|bba|llb|mbchb|mb\s?chb|degree|doctor of medicine)\b", re.I)),
    (6, "Diploma", re.compile(r"\b(advanced diploma|higher diploma|diploma)\b", re.I)),
    (5, "Advanced Certificate", re.compile(r"\b(advanced certificate|technician certificate|technologist)\b", re.I)),
    (3, "School Certificate", re.compile(r"\b(grade\s?12|school certificate|o[\s-]?levels?|a[\s-]?levels?|gce)\b", re.I)),
    (4, "Craft Certificate", re.compile(r"\b(craft certificate|trade test|certificate)\b", re.I)),
]

_LABEL_TO_LEVEL = {
    "certificate": 4,
    "craft certificate": 4,
    "advanced certificate": 5,
    "diploma": 6,
    "degree": 7,
    "bachelor": 7,
    "bachelors": 7,
    "bachelor's": 7,
    "honours": 8,
    "postgraduate diploma": 8,
    "master": 9,
    "masters": 9,
    "master's": 9,
    "doctorate": 10,
    "phd": 10,
}


@dataclass(frozen=True)
class ZqfMatch:
    level: int
    label: str


def infer_zqf_level(title: str | None) -> ZqfMatch | None:
    if not title:
        return None
    for level, label, pattern in _PATTERNS:
        if pattern.search(title):
            return ZqfMatch(level, label)
    return None


def level_from_requirement(value: str | int | None) -> int | None:
    """Accept a job's minimum qualification as an int level, a label ("Diploma") or a full title."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if text.isdigit():
        return int(text)
    if text in _LABEL_TO_LEVEL:
        return _LABEL_TO_LEVEL[text]
    match = infer_zqf_level(text)
    return match.level if match else None


_FIELD_PATTERN = re.compile(r"\b(?:in|of)\s+(?!science\b|arts\b|philosophy\b|education\b(?=\s+in))([A-Za-z&,\s]+?)(?:\s*[\(\-–—|,]|\s+from\b|\s+at\b|$)", re.I)
_FIELD_AFTER_GENERIC = re.compile(r"\b(?:science|arts|philosophy|education|technology|engineering)\s+(?:in|\()\s*([A-Za-z&\s]+?)(?:\)|\s*[\-–—|,]|\s+from\b|\s+at\b|$)", re.I)


def infer_field_of_study(title: str | None) -> str | None:
    """Pull "Accountancy" out of "Bachelor of Accountancy" or "BSc in Computer Science"."""
    if not title:
        return None
    for pattern in (_FIELD_AFTER_GENERIC, _FIELD_PATTERN):
        m = pattern.search(title)
        if m:
            field = m.group(1).strip(" ,&")
            if field and len(field) <= 80:
                return field
    return None
