"use client";

import { FormEvent, useState } from "react";
import { api, sha256 } from "../../../lib/api-client";

export default function ApplyPage({ params }: { params: { jobId: string } }) {
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    const app = await api<{ id: string }>("/applications", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_posting_id: params.jobId, candidate_name: form.get("name"), candidate_email: form.get("email") }) });
    for (const entry of Array.from(form.getAll("documents"))) {
      const file = entry as File;
      if (!file.size) continue;
      const content_hash = await sha256(file);
      const presign = await api<{ duplicate: boolean; upload_url?: string; s3_key?: string }>("/applications/uploads/presign", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ application_id: app.id, filename: file.name, content_type: file.type || "application/octet-stream", doc_type: form.get("doc_type"), content_hash }) });
      if (!presign.duplicate && presign.upload_url && presign.s3_key) {
        await fetch(presign.upload_url, { method: "PUT", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file });
        await api("/applications/uploads/complete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ application_id: app.id, doc_type: form.get("doc_type"), s3_key: presign.s3_key, content_hash }) });
      }
    }
    setBusy(false);
    setDone(true);
  }

  if (done) return <main className="mx-auto max-w-2xl px-6 py-16"><h1 className="text-3xl font-semibold">Application received</h1><p className="mt-3 text-stone-700">Your documents are being processed for hiring manager review.</p></main>;
  return <main className="mx-auto max-w-2xl px-6 py-10">
    <h1 className="text-3xl font-semibold">Submit Application</h1>
    <form onSubmit={submit} className="mt-6 grid gap-4">
      <input required name="name" className="rounded border border-stone-300 p-3" placeholder="Full name" />
      <input required name="email" type="email" className="rounded border border-stone-300 p-3" placeholder="Email address" />
      <select name="doc_type" className="rounded border border-stone-300 p-3"><option value="cv">CV</option><option value="certificate">Certificate</option><option value="cover_letter">Cover letter</option><option value="national_id">National ID</option></select>
      <input required multiple name="documents" type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" className="rounded border border-stone-300 bg-white p-3" />
      <button disabled={busy} className="rounded bg-emerald-800 px-4 py-3 font-medium text-white disabled:opacity-60">{busy ? "Submitting..." : "Submit"}</button>
    </form>
  </main>;
}

