"""Deterministic CV extractor. Always available; also the fallback when the LLM is off or fails."""

import re
from datetime import date

from apps.api.services.verification.verifier import CertificationCatalog
from apps.api.services.verification.zqf import infer_zqf_level

from .schemas import CertificationEntry, ContactInfo, EducationEntry, ExperienceEntry, ParsedCV

DEFAULT_SKILLS = [
    "Excel", "financial reporting", "IFRS", "IPSAS", "budgeting", "reconciliations", "auditing", "taxation",
    "Sage", "Pastel", "QuickBooks", "SAP", "Python", "SQL", "JavaScript", "TypeScript", "React", "Java",
    "Power BI", "data analysis", "project management", "procurement", "stakeholder management",
    "monitoring and evaluation", "grant management", "payroll", "customer service", "networking", "Linux",
]
SKILL_SYNONYMS = {
    "ms excel": "Excel", "microsoft excel": "Excel", "advanced excel": "Excel",
    "m&e": "monitoring and evaluation", "powerbi": "Power BI", "js": "JavaScript",
    "bank reconciliations": "reconciliations", "financial statements": "financial reporting",
}

SECTION_HEADERS = {
    "education": r"education(al)?( background| qualifications| and training)?|academic (qualifications|background|history)|qualifications",
    "experience": r"(work |professional |employment )?(experience|history)|employment|career history|work history",
    "skills": r"(key |core |technical )?skills|competenc(e|ies)|expertise",
    "certifications": r"certifications?|professional (qualifications|certifications|memberships?|bodies)|licen[cs]es|memberships?",
    "summary": r"(professional |career )?(summary|profile|objective)|about me",
    "references": r"references|referees",
}
_HEADER_RES = {name: re.compile(rf"^\s*({pat})\s*:?\s*$", re.I) for name, pat in SECTION_HEADERS.items()}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE = r"(?:(?P<{p}m>[A-Za-z]{{3,9}})\.?\s+)?(?P<{p}y>(?:19|20)\d{{2}})"
DATE_RANGE = re.compile(
    _DATE.format(p="s") + r"\s*(?:-|–|—|to|until)\s*(?:" + _DATE.format(p="e") + r"|(?P<present>present|current|date|now))",
    re.I,
)
YEAR = re.compile(r"\b(19[5-9]\d|20\d{2})\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?260[\s-]?|0)(?:9[5-9]|7[5-9]|21)\d[\s-]?\d{3}[\s-]?\d{3,4}|\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{3}[\s-]?\d{3,4}")
CLASSIFICATION = re.compile(
    r"\b(distinction|merit|credit|pass|first class|upper second|lower second|second class( upper| lower)?|"
    r"third class|2:1|2:2|summa cum laude|magna cum laude|cum laude)\b", re.I)
GPA = re.compile(r"\b(?:GPA|CGPA)\s*[:\-]?\s*([0-4]\.\d{1,2})", re.I)
INSTITUTION_HINT = re.compile(r"\b(university|college|institute|school|academy|polytechnic|UNZA|CBU|ZCAS|UNISA|NIPA)\b", re.I)
ZAMBIAN_TOWNS = ["Lusaka", "Kitwe", "Ndola", "Livingstone", "Kabwe", "Chipata", "Solwezi", "Kasama", "Chingola", "Mufulira", "Mansa"]


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        if len(line) <= 45:
            name = next((n for n, rx in _HEADER_RES.items() if rx.match(line)), None)
            if name:
                current = name
                sections.setdefault(current, [])
                continue
        sections.setdefault(current, []).append(line)
    return sections


def _month(token: str | None) -> int:
    return MONTHS.get((token or "")[:3].lower(), 1)


def _months_between(start: tuple[int, int], end: tuple[int, int]) -> int:
    return max(0, (end[0] - start[0]) * 12 + end[1] - start[1] + 1)


def _merge_intervals(intervals: list[tuple[int, int]]) -> int:
    """Total months covered, counting overlapping jobs once."""
    total, cur = 0, None
    for s, e in sorted(intervals):
        if cur and s <= cur[1]:
            cur = (cur[0], max(cur[1], e))
        else:
            if cur:
                total += cur[1] - cur[0] + 1
            cur = (s, e)
    if cur:
        total += cur[1] - cur[0] + 1
    return total


def parse_experience(lines: list[str], today: date) -> tuple[list[ExperienceEntry], float]:
    entries, intervals = [], []
    for i, line in enumerate(lines):
        m = DATE_RANGE.search(line)
        if not m:
            continue
        start = (int(m.group("sy")), _month(m.group("sm")))
        end = (today.year, today.month) if m.group("present") else (int(m.group("ey")), _month(m.group("em")) if m.group("em") else 12)
        if end < start:
            continue
        months = _months_between(start, end)
        heading = line[: m.start()].strip(" ,|-–—:()") or (lines[i - 1] if i > 0 else "")
        trailing = line[m.end():].strip(" ,|-–—:()")
        title, org = _split_role(heading or trailing)
        entries.append(ExperienceEntry(
            title=title, organisation=org,
            start=f"{start[0]}-{start[1]:02d}",
            end="present" if m.group("present") else f"{end[0]}-{end[1]:02d}",
            months=months, raw=line,
        ))
        intervals.append((start[0] * 12 + start[1], end[0] * 12 + end[1]))
    return entries, round(_merge_intervals(intervals) / 12, 1)


def _split_role(text: str) -> tuple[str | None, str | None]:
    for sep in (" at ", " - ", " – ", " — ", " | ", ", "):
        if sep in text:
            a, b = text.split(sep, 1)
            return a.strip() or None, b.strip() or None
    return (text.strip() or None), None


def _institution_in(text: str) -> str | None:
    for part in re.split(r"\s[-–—|]\s|,|;|\(|\)|\bat\b|\bfrom\b", text):
        part = part.strip()
        if part and INSTITUTION_HINT.search(part) and not infer_zqf_level(part):
            return part
    return None


def parse_education(lines: list[str]) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    for i, line in enumerate(lines):
        if not infer_zqf_level(line) or len(line) > 200:
            continue
        # Neighbouring lines may hold the institution/year, unless they are another award's line.
        window = [line] + [lines[j] for j in (i + 1, i - 1) if 0 <= j < len(lines) and not infer_zqf_level(lines[j])]
        institution = next((inst for inst in map(_institution_in, window) if inst), None)
        year_src = next((w for w in window if YEAR.search(w)), "")
        years = [int(y) for y in YEAR.findall(year_src)]
        cls = next((m for m in map(CLASSIFICATION.search, window) if m), None)
        gpa = GPA.search(" ".join(window))
        title = re.split(r"\s[-–—|]\s|,|\(|\bat\b|\bfrom\b", line)[0].strip()
        title = YEAR.sub("", title).strip(" ,-–—") or line
        if infer_zqf_level(title) is None:
            title = line
        entries.append(EducationEntry(
            title=title, institution=institution, award_year=max(years) if years else None,
            classification=cls.group(0).title() if cls else None,
            gpa=float(gpa.group(1)) if gpa else None, raw=" / ".join(window[:2]),
        ))
    # A title line and a separate institution line can both match; keep the first occurrence of each title.
    seen, unique = set(), []
    for e in entries:
        key = e.title.lower()
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def parse_skills(text: str, skills_section: list[str], vocabulary: list[str]) -> list[str]:
    found: dict[str, str] = {}
    lowered = text.lower()
    for synonym, canonical in SKILL_SYNONYMS.items():
        if re.search(rf"(?<![a-z]){re.escape(synonym)}(?![a-z])", lowered):
            found[canonical.lower()] = canonical
    for skill in vocabulary:
        if re.search(rf"(?<![a-z]){re.escape(skill.lower())}(?![a-z])", lowered):
            found.setdefault(skill.lower(), skill)
    for line in skills_section:
        for item in re.split(r"[,;•|·]|\s{2,}", line):
            item = item.strip(" -*:")
            if 1 < len(item) <= 40 and len(item.split()) <= 4:
                canonical = SKILL_SYNONYMS.get(item.lower(), item)
                found.setdefault(canonical.lower(), canonical)
    return list(found.values())


def parse_contact(lines: list[str], text: str) -> ContactInfo:
    email = EMAIL.search(text)
    phone = PHONE.search(text)
    name = None
    for line in lines[:5]:
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z'.-]+", w) for w in words) and not INSTITUTION_HINT.search(line) \
                and not any(rx.match(line) for rx in _HEADER_RES.values()) and line.lower() not in {"curriculum vitae", "resume"}:
            name = line.title() if line.isupper() else line
            break
    location = next((t for t in ZAMBIAN_TOWNS if re.search(rf"\b{t}\b", text)), None)
    return ContactInfo(full_name=name, email=email.group(0) if email else None,
                       phone=re.sub(r"\s+", " ", phone.group(0)).strip() if phone else None, location=location)


def heuristic_parse(text: str, skill_vocabulary: list[str] | None = None, today: date | None = None) -> ParsedCV:
    today = today or date.today()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections = split_sections(lines)

    edu_lines = sections.get("education") or lines
    exp_lines = sections.get("experience") or [ln for ln in lines if ln not in set(sections.get("education", []))]
    education = parse_education(edu_lines)
    experience, years = parse_experience(exp_lines, today)
    skills = parse_skills(text, sections.get("skills", []), list(dict.fromkeys(DEFAULT_SKILLS + (skill_vocabulary or []))))
    certs = [CertificationEntry(name=c.name, issuer=c.issuer) for c in CertificationCatalog().find_all(text)]
    summary_lines = sections.get("summary") or []
    contact = parse_contact(lines, text)

    return ParsedCV(
        contact=contact,
        summary=" ".join(summary_lines)[:600] or None,
        education=education,
        experience=experience,
        total_experience_years=years,
        skills=skills,
        certifications=certs,
        links=re.findall(r"https?://\S+", text),
        field_confidences={
            "contact.email": 0.95 if contact.email else 0.1,
            "contact.full_name": 0.6 if contact.full_name else 0.1,
            "education": 0.7 if education else 0.2,
            "experience": 0.7 if experience else 0.2,
            "skills": 0.75 if skills else 0.3,
            "certifications": 0.8 if certs else 0.4,
        },
        extraction_method="heuristic",
    )
