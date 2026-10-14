"""One-command local demo: SQLite + local storage, seeded candidates, recruiter page at /demo.

    apps/api/.venv/Scripts/python -m apps.api.scripts.run_demo [--port 8000] [--reset]
"""

import argparse
import hashlib
import os
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
API_DIR = REPO_ROOT / "apps" / "api"
DEMO_DB = REPO_ROOT / "attest-demo.db"

# Configure before importing the app: engine and storage read env at import time.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{DEMO_DB.as_posix()}")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("LOCAL_STORAGE_DIR", str(REPO_ROOT / "storage" / "api-uploads"))

CANDIDATES = [
    # name, email, source, cv, cover letter, certificates  (paths relative to apps/api)
    ("Mwila Banda", "mwila.banda@example.com", "portal", "tests/fixtures/cv_mwila.txt", "tests/fixtures/cover_mwila.txt",
     ["demo/candidates/degree_certificate_mwila.txt"]),
    ("Grace Lungu", "grace.lungu@example.com", "email", "demo/candidates/grace_lungu_cv.txt", "demo/candidates/grace_lungu_cover.txt", []),
    ("Chipo Mulenga", "chipo.mulenga@example.com", "portal", "demo/candidates/chipo_mulenga_cv.txt", "demo/candidates/chipo_mulenga_cover.txt", []),
    ("Natasha Zulu", "natasha.zulu@example.com", "api", "demo/candidates/natasha_zulu_cv.txt", None, []),
    ("Bwalya Tembo", "bwalya.tembo@example.com", "portal", "demo/candidates/bwalya_tembo_cv.txt", "demo/candidates/bwalya_tembo_cover.txt", []),
    ("John Phiri", "john.phiri@example.com", "email", "tests/fixtures/cv_weak.txt", None, []),
]


def seed_demo_candidates() -> int:
    from sqlalchemy import func, select

    from apps.api.models.database import SessionLocal
    from apps.api.models.entities import Application, Document, JobPosting
    from apps.api.services.pipeline import process_application
    from apps.api.services.storage import put_object

    with SessionLocal() as db:
        job = db.scalar(select(JobPosting).where(JobPosting.slug == "finance-officer-lusaka"))
        if db.scalar(select(func.count()).select_from(Application).where(Application.job_posting_id == job.id)):
            return 0
        for name, email, source, cv, cover, certs in CANDIDATES:
            app = Application(tenant_id=job.tenant_id, job_posting_id=job.id, candidate_name=name,
                              candidate_email=email, source=source)
            db.add(app)
            db.flush()
            files = [("cv", cv)] + ([("cover_letter", cover)] if cover else []) + [("certificate", c) for c in certs]
            for doc_type, rel in files:
                path = API_DIR / rel
                data = path.read_bytes()
                key = f"{job.tenant_id}/{app.id}/{uuid4()}-{path.name}"
                put_object(key, data, "text/plain")
                db.add(Document(tenant_id=job.tenant_id, application_id=app.id, doc_type=doc_type, s3_key=key,
                                content_hash=hashlib.sha256(data).hexdigest(), original_filename=path.name, size_bytes=len(data)))
            db.commit()
            process_application(db, app.id)
        return len(CANDIDATES)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    ap.add_argument("--reset", action="store_true", help="delete the demo database and start fresh")
    args = ap.parse_args()
    if args.reset and DEMO_DB.exists():
        DEMO_DB.unlink()

    import uvicorn

    from apps.api.services.seed import init_dev_database

    init_dev_database()
    seeded = seed_demo_candidates()
    print(f"Demo ready ({seeded} candidates seeded). Open http://localhost:{args.port}/demo")
    uvicorn.run("apps.api.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
