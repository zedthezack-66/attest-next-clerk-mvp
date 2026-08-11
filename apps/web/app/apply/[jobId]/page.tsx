"use client";

import { FormEvent, useState } from "react";

export default function ApplyPage({ params }: { params: { jobId: string } }) {
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    form.set("jobId", params.jobId);
    const res = await fetch("/api/applications/upload", { method: "POST", body: form });
    setBusy(false);
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    setDone(true);
  }

  if (done) {
    return <main className="mx-auto max-w-2xl px-6 py-16"><h1 className="text-3xl font-semibold">Application received</h1><p className="mt-3 text-stone-700">Your documents were captured and are ready for hiring manager review.</p></main>;
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-3xl font-semibold">Submit Application</h1>
      <form onSubmit={submit} className="mt-6 grid gap-4">
        <input required name="candidateName" className="rounded border border-stone-300 p-3" placeholder="Full name" />
        <input required name="candidateEmail" type="email" className="rounded border border-stone-300 p-3" placeholder="Email address" />
        <select name="docType" className="rounded border border-stone-300 p-3">
          <option value="cv">CV</option>
          <option value="certificate">Certificate</option>
          <option value="cover_letter">Cover letter</option>
          <option value="national_id">National ID</option>
        </select>
        <input required multiple name="documents" type="file" accept=".pdf,.docx,.png,.jpg,.jpeg,.txt" className="rounded border border-stone-300 bg-white p-3" />
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button disabled={busy} className="rounded bg-emerald-800 px-4 py-3 font-medium text-white disabled:opacity-60">{busy ? "Submitting..." : "Submit"}</button>
      </form>
    </main>
  );
}

