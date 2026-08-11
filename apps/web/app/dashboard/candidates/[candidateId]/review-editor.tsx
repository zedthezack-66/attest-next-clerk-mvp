"use client";

import { useState } from "react";

type Review = {
  application?: { candidateName: string; candidateEmail: string };
  profile?: any;
  documents: { document: { filename: string; docType: string }; latestExtraction?: { rawText: string; fieldConfidences: Record<string, number>; extractionMethod: string } }[];
};

export default function ReviewEditor({ initial, applicationId }: { initial: Review; applicationId: string }) {
  const [review, setReview] = useState(initial);
  const [saving, setSaving] = useState(false);
  const raw = review.documents.find((doc) => doc.latestExtraction)?.latestExtraction;

  async function save() {
    if (!review.profile) return;
    setSaving(true);
    const res = await fetch(`/api/applications/${applicationId}/profile`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(review.profile),
    });
    const profile = await res.json();
    setReview({ ...review, profile });
    setSaving(false);
  }

  if (!review.application) return <main className="p-8">Application not found.</main>;
  return (
    <main className="px-6 py-8">
      <header className="mb-5 flex items-center justify-between border-b border-stone-300 pb-4">
        <div><h1 className="text-2xl font-semibold">{review.application.candidateName}</h1><p className="text-sm text-stone-700">{review.application.candidateEmail}</p></div>
        <button onClick={save} disabled={saving || !review.profile} className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-60">{saving ? "Saving..." : "Save profile"}</button>
      </header>
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded border border-stone-300 bg-white p-4">
          <h2 className="mb-3 font-semibold">Parsed Profile</h2>
          {review.profile ? (["bio", "education", "experience", "skills", "links"] as const).map((key) => (
            <label key={key} className="mb-3 grid gap-1 text-sm font-medium">
              {key}
              <textarea className="min-h-28 rounded border border-stone-300 p-3 font-mono text-xs" value={JSON.stringify(review.profile[key], null, 2)} onChange={(e) => setReview({ ...review, profile: { ...review.profile, [key]: JSON.parse(e.target.value || "null") } })} />
            </label>
          )) : <p className="text-sm text-stone-700">Profile is still pending.</p>}
        </div>
        <div className="rounded border border-stone-300 bg-white p-4">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Source Text</h2>{raw && <span className="rounded bg-stone-100 px-2 py-1 text-xs">{raw.extractionMethod}</span>}</div>
          {raw ? <><pre className="max-h-[42rem] overflow-auto whitespace-pre-wrap rounded bg-stone-100 p-3 text-sm">{raw.rawText}</pre><pre className="mt-3 rounded bg-stone-100 p-3 text-xs">{JSON.stringify(raw.fieldConfidences, null, 2)}</pre></> : <p className="text-sm text-stone-700">No extraction result yet.</p>}
        </div>
      </section>
    </main>
  );
}

