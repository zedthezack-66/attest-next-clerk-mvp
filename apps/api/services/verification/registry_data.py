"""MOCK institution registry for Phase 1.

This is a hand-built fixture shaped like the data a live integration would return from ZAQA's
qualification verification service, the Higher Education Authority (HEA) register and the
TEVETA register. Registration statuses, award ceilings and founding years are illustrative and
must NOT be treated as authoritative. Replace `MockRegistryProvider` with a live provider before
relying on verification outcomes for hiring decisions.

Entries with code prefix `fixture-` are fictitious and exist only to exercise negative paths.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstitutionRecord:
    code: str
    name: str
    country_code: str
    kind: str  # public_university | private_university | college | foreign_university
    regulator: str  # HEA | TEVETA | FOREIGN
    registration_status: str  # registered | provisional | recognised | deregistered | unaccredited
    max_zqf_level: int
    aliases: tuple[str, ...] = field(default_factory=tuple)
    founded_year: int | None = None


MOCK_INSTITUTIONS: tuple[InstitutionRecord, ...] = (
    # --- Zambian public universities (HEA) ---
    InstitutionRecord("zm-unza", "University of Zambia", "ZM", "public_university", "HEA", "registered", 10, ("UNZA",), 1966),
    InstitutionRecord("zm-cbu", "Copperbelt University", "ZM", "public_university", "HEA", "registered", 10, ("CBU", "The Copperbelt University"), 1987),
    InstitutionRecord("zm-mu", "Mulungushi University", "ZM", "public_university", "HEA", "registered", 9, ("MU",), 2008),
    InstitutionRecord("zm-mukuba", "Mukuba University", "ZM", "public_university", "HEA", "registered", 9),
    InstitutionRecord("zm-knu", "Kwame Nkrumah University", "ZM", "public_university", "HEA", "registered", 9, ("KNU",)),
    InstitutionRecord("zm-chau", "Chalimbana University", "ZM", "public_university", "HEA", "registered", 9),
    # --- Zambian private universities (HEA) ---
    InstitutionRecord("zm-zaou", "Zambian Open University", "ZM", "private_university", "HEA", "registered", 9, ("ZAOU", "Zambia Open University"), 2005),
    InstitutionRecord("zm-unilus", "University of Lusaka", "ZM", "private_university", "HEA", "registered", 9, ("UNILUS",)),
    InstitutionRecord("zm-cavendish", "Cavendish University Zambia", "ZM", "private_university", "HEA", "registered", 9, ("Cavendish University", "CUZ"), 2004),
    InstitutionRecord("zm-zcas", "ZCAS University", "ZM", "private_university", "HEA", "registered", 9, ("ZCAS", "Zambia Centre for Accountancy Studies")),
    InstitutionRecord("zm-icu", "Information and Communications University", "ZM", "private_university", "HEA", "registered", 9, ("ICU Zambia", "ICU")),
    InstitutionRecord("zm-northrise", "Northrise University", "ZM", "private_university", "HEA", "registered", 7),
    # --- Zambian TEVET colleges (TEVETA) ---
    InstitutionRecord("zm-evelynhone", "Evelyn Hone College", "ZM", "college", "TEVETA", "registered", 6, ("Evelyn Hone College of Applied Arts and Commerce", "Evelyn Hone"), 1963),
    InstitutionRecord("zm-nipa", "National Institute of Public Administration", "ZM", "college", "TEVETA", "registered", 6, ("NIPA",)),
    InstitutionRecord("zm-nortec", "Northern Technical College", "ZM", "college", "TEVETA", "registered", 6, ("NORTEC",)),
    InstitutionRecord("zm-lbtc", "Lusaka Business and Technical College", "ZM", "college", "TEVETA", "registered", 6, ("LBTC",)),
    # --- Foreign universities (recognised in country of origin; ZAQA foreign evaluation still applies) ---
    InstitutionRecord("za-uct", "University of Cape Town", "ZA", "foreign_university", "FOREIGN", "recognised", 10, ("UCT",)),
    InstitutionRecord("za-wits", "University of the Witwatersrand", "ZA", "foreign_university", "FOREIGN", "recognised", 10, ("Wits", "Wits University")),
    InstitutionRecord("za-up", "University of Pretoria", "ZA", "foreign_university", "FOREIGN", "recognised", 10, ("UP", "Tuks")),
    InstitutionRecord("za-unisa", "University of South Africa", "ZA", "foreign_university", "FOREIGN", "recognised", 10, ("UNISA",)),
    InstitutionRecord("ke-uon", "University of Nairobi", "KE", "foreign_university", "FOREIGN", "recognised", 10),
    InstitutionRecord("ug-mak", "Makerere University", "UG", "foreign_university", "FOREIGN", "recognised", 10),
    InstitutionRecord("zw-uz", "University of Zimbabwe", "ZW", "foreign_university", "FOREIGN", "recognised", 10, ("UZ",)),
    InstitutionRecord("bw-ub", "University of Botswana", "BW", "foreign_university", "FOREIGN", "recognised", 10),
    InstitutionRecord("gb-ox", "University of Oxford", "GB", "foreign_university", "FOREIGN", "recognised", 10, ("Oxford University",)),
    InstitutionRecord("gb-man", "University of Manchester", "GB", "foreign_university", "FOREIGN", "recognised", 10),
    InstitutionRecord("gb-lon", "University of London", "GB", "foreign_university", "FOREIGN", "recognised", 10),
    InstitutionRecord("in-du", "University of Delhi", "IN", "foreign_university", "FOREIGN", "recognised", 10, ("Delhi University",)),
    InstitutionRecord("cn-tsinghua", "Tsinghua University", "CN", "foreign_university", "FOREIGN", "recognised", 10),
    # --- Fictitious negative-path fixtures ---
    InstitutionRecord("fixture-gpou", "Global Pacific Open University", "XX", "foreign_university", "FOREIGN", "unaccredited", 10, ("GPOU",)),
    InstitutionRecord("fixture-lpc", "Lusaka Premier College of Commerce", "ZM", "college", "TEVETA", "deregistered", 6, ("LPCC",)),
    InstitutionRecord("fixture-nhu", "New Horizons University Zambia", "ZM", "private_university", "HEA", "provisional", 7, ("NHUZ",), 2021),
)


@dataclass(frozen=True)
class CertificationRecord:
    code: str
    name: str
    issuer: str
    aliases: tuple[str, ...] = ()


# Professional certifications / designations recognised for scoring. Also a mock catalog.
CERTIFICATIONS: tuple[CertificationRecord, ...] = (
    CertificationRecord("acca", "ACCA", "Association of Chartered Certified Accountants", ("Chartered Certified Accountant", "FCCA")),
    CertificationRecord("cima", "CIMA", "Chartered Institute of Management Accountants", ("CGMA", "ACMA")),
    CertificationRecord("zica-ca", "CA Zambia", "Zambia Institute of Chartered Accountants", ("Chartered Accountant Zambia", "CA (Z)", "ZICA Chartered Accountant")),
    CertificationRecord("zica-dip", "ZICA Diploma in Accountancy", "Zambia Institute of Chartered Accountants", ("ZICA Technician", "ZICA Licentiate")),
    CertificationRecord("cpa", "CPA", "Certified Public Accountant", ("Certified Public Accountant",)),
    CertificationRecord("cia", "CIA", "Institute of Internal Auditors", ("Certified Internal Auditor",)),
    CertificationRecord("cisa", "CISA", "ISACA", ("Certified Information Systems Auditor",)),
    CertificationRecord("pmp", "PMP", "Project Management Institute", ("Project Management Professional",)),
    CertificationRecord("prince2", "PRINCE2", "AXELOS", ("PRINCE2 Practitioner", "PRINCE2 Foundation")),
    CertificationRecord("ccna", "CCNA", "Cisco", ("Cisco Certified Network Associate",)),
    CertificationRecord("aws-saa", "AWS Solutions Architect", "Amazon Web Services", ("AWS Certified Solutions Architect", "AWS SAA")),
    CertificationRecord("cissp", "CISSP", "ISC2", ()),
    CertificationRecord("eiz", "EIZ Registered Engineer", "Engineering Institution of Zambia", ("EIZ", "Registered Engineer")),
    CertificationRecord("laz", "LAZ Practising Certificate", "Law Association of Zambia", ("LAZ", "Advocate of the High Court")),
    CertificationRecord("hpcz", "HPCZ Registration", "Health Professions Council of Zambia", ("HPCZ",)),
    CertificationRecord("zipm", "ZIHRM Membership", "Zambia Institute of Human Resource Management", ("ZIHRM", "ZIPM")),
    CertificationRecord("cips", "CIPS", "Chartered Institute of Procurement & Supply", ("MCIPS",)),
    CertificationRecord("zips", "ZIPS Membership", "Zambia Institute of Purchasing and Supply", ("ZIPS",)),
)
