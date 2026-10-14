"""End-to-end: recruiter creates a job, candidates apply, pipeline scores them, recruiter ranks/reviews."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.main import app
from apps.api.models.database import SessionLocal
from apps.api.models.entities import AuditLog, Tenant, User
from apps.api.services.auth import hash_password

from .conftest import FIXTURES


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # runs lifespan: schema + seed
        yield c


def login(client, email="manager@attest.local", password="password123"):
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def recruiter(client):
    return login(client)


@pytest.fixture(scope="module")
def job(client, recruiter):
    body = json.loads((FIXTURES / "finance_officer_job.json").read_text())
    resp = client.post("/jobs", json=body, headers=recruiter)
    assert resp.status_code == 201, resp.text
    return resp.json()


def submit(client, job_id, name, email, cv_file, cover_file=None, certificates=()):
    files = [("cv", (cv_file, (FIXTURES / cv_file).read_bytes(), "text/plain"))]
    if cover_file:
        files.append(("cover_letter", (cover_file, (FIXTURES / cover_file).read_bytes(), "text/plain")))
    for name_, content in certificates:
        files.append(("certificates", (name_, content, "text/plain")))
    return client.post("/applications/submit", data={"job_id": job_id, "candidate_name": name, "candidate_email": email}, files=files)


@pytest.fixture(scope="module")
def applications(client, job):
    strong = submit(client, job["id"], "Mwila Banda", "mwila.banda@example.com", "cv_mwila.txt", "cover_mwila.txt",
                    certificates=[("degree.txt", b"This is to certify that Mwila Banda was awarded the\nBachelor of Accountancy\nCopperbelt University 2018")])
    weak = submit(client, job["id"], "John Phiri", "john.phiri@example.com", "cv_weak.txt")
    assert strong.status_code == 202, strong.text
    assert weak.status_code == 202, weak.text
    return strong.json(), weak.json()


def test_job_created_with_zqf_level(job):
    assert job["min_zqf_level"] == 7
    assert job["required_skills"] == ["Excel", "financial reporting", "reconciliations"]


def test_submission_is_processed_and_status_hides_score(client, applications):
    strong, _ = applications
    assert strong["documents"] == 3
    status = client.get(strong["status_url"]).json()
    assert status == {"application_id": strong["application_id"], "status": "scored"}


def test_ranked_candidates(client, recruiter, job, applications):
    strong, weak = applications
    resp = client.get(f"/jobs/{job['id']}/candidates", headers=recruiter)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 2
    first, second = data["items"]
    assert (first["application_id"], first["rank"]) == (strong["application_id"], 1)
    assert second["application_id"] == weak["application_id"]
    assert first["fit_score"] > 80 > 30 > second["fit_score"]
    assert set(first["components"]) == {"skills_experience", "cover_letter", "education", "certifications"}
    assert first["best_qualification"]["verification_status"] == "verified"
    assert first["best_qualification"]["zqf_level"] == 7
    assert any("unrecognised" in f for f in second["flags"])


def test_ranked_candidates_filters(client, recruiter, job, applications):
    strong, _ = applications
    verified = client.get(f"/jobs/{job['id']}/candidates?verified_only=true", headers=recruiter).json()
    assert [i["application_id"] for i in verified["items"]] == [strong["application_id"]]
    high = client.get(f"/jobs/{job['id']}/candidates?min_score=50", headers=recruiter).json()
    assert high["total"] == 1


def test_assessment_deep_dive(client, recruiter, applications):
    strong, _ = applications
    data = client.get(f"/applications/{strong['application_id']}/assessment", headers=recruiter).json()
    assert data["cover_letter_summary"]
    assert data["profile"]["bio"]["total_experience_years"] > 3
    degree = next(q for q in data["qualifications"] if q["title"] == "Bachelor of Accountancy")
    assert degree["verification_details"]["certificate_uploaded"] is True
    assert degree["verification_details"]["institution_code"] == "zm-cbu"
    assert {q["kind"] for q in data["qualifications"]} == {"academic", "certification"}


def test_rescore_after_job_criteria_change(client, recruiter, job, applications):
    _, weak = applications
    before = client.get(f"/applications/{weak['application_id']}/assessment", headers=recruiter).json()["fit_score"]
    resp = client.patch(f"/jobs/{job['id']}", json={"required_skills": ["Excel", "customer service"]}, headers=recruiter)
    assert resp.status_code == 200
    after = client.post(f"/applications/{weak['application_id']}/rescore", headers=recruiter).json()["fit_score"]
    assert after > before


def test_audit_trail_written(applications):
    strong, _ = applications
    with SessionLocal() as db:
        actions = {a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == strong["application_id"]))}
    assert {"application.submitted", "application.parsed", "application.scored", "application.viewed"} <= actions


def test_other_tenant_cannot_see_candidates(client, job, applications):
    with SessionLocal() as db:
        other = Tenant(name="Other Employer")
        db.add(other)
        db.flush()
        db.add(User(tenant_id=other.id, email="other@attest.local", password_hash=hash_password("pw-other"), role="recruiter"))
        db.commit()
    headers = login(client, "other@attest.local", "pw-other")
    assert client.get(f"/jobs/{job['id']}/candidates", headers=headers).status_code == 404
    assert client.get(f"/applications/{applications[0]['application_id']}/assessment", headers=headers).status_code == 404


def test_endpoints_require_recruiter(client, job):
    assert client.get(f"/jobs/{job['id']}/candidates").status_code == 401
    assert client.post("/jobs", json={}).status_code == 401


def test_rejects_unsupported_file_type(client, job):
    files = [("cv", ("cv.exe", b"MZ...", "application/octet-stream"))]
    resp = client.post("/applications/submit", files=files,
                       data={"job_id": job["id"], "candidate_name": "X Y", "candidate_email": "x@example.com"})
    assert resp.status_code == 415


def test_rejects_unknown_job(client):
    files = [("cv", ("cv.txt", b"hello", "text/plain"))]
    resp = client.post("/applications/submit", files=files, data={
        "job_id": "00000000-0000-0000-0000-000000000000", "candidate_name": "X Y", "candidate_email": "x@example.com"})
    assert resp.status_code == 404
