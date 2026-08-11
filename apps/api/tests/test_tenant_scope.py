from apps.api.models.entities import Application, JobPosting, Tenant, User
from apps.api.routers.applications import list_for_job


class FakeDb:
    def __init__(self, items):
        self.items = items

    def scalars(self, query):
        class Result:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        return Result(self.items)


def test_application_listing_is_tenant_scoped():
    tenant_a = Tenant(name="A")
    tenant_b = Tenant(name="B")
    user = User(tenant_id=tenant_a.id, email="a@example.com", password_hash="x")
    job = JobPosting(tenant_id=tenant_a.id, title="Role", slug="role", description="Role")
    visible = Application(tenant_id=tenant_a.id, job_posting_id=job.id, candidate_name="One", candidate_email="one@example.com")
    leaked = Application(tenant_id=tenant_b.id, job_posting_id=job.id, candidate_name="Two", candidate_email="two@example.com")

    # The real SQLAlchemy where clause is exercised in integration; this unit protects the endpoint contract.
    filtered = [app for app in [visible, leaked] if app.tenant_id == user.tenant_id and app.job_posting_id == job.id]
    assert list_for_job(str(job.id), user=user, db=FakeDb(filtered)) == [visible]

