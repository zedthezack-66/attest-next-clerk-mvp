"use client";
import { Badge } from "@attest/ui";
import { useEffect, useState } from "react";
import { api } from "../../../../../lib/api-client";

type Review = {
  application: { candidate_name: string; candidate_email: string };
  profile: any;
  documents: { document: { id: string; doc_type: string }; latest_extraction?: { raw_text: string; field_confidences_json: Record<string, number>; extraction_method: string } }[];
};

export default function CandidateReview({ params }: { params: { candidateId: string } }) {
  const [review, setReview] = useState<Review | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { api<Review>(`/applications/${params.candidateId}/review`).then(setReview).catch(() => location.href = "/login"); }, [params.candidateId]);
  async function save() {
    if (!review?.profile) return;
    setSaving(true);
    const updated = await api(`/applications/${params.candidateId}/profile`, { method: "PATCH", body: JSON.stringify(review.profile) });
    setReview({ ...review, profile: updated });
    setSaving(false);
  }
  if (!review) return <main className="p-8">Loading...</main>;
  const raw = review.documents.find((d) => d.latest_extraction)?.latest_extraction;
  return <main className="px-6 py-8">
    <header className="mb-5 flex items-center justify-between border-b border-stone-300 pb-4">
      <div><h1 className="text-2xl font-semibold">{review.application.candidate_name}</h1><p className="text-sm text-stone-700">{review.application.candidate_email}</p></div>
      <button onClick={save} disabled={saving || !review.profile} className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-60">{saving ? "Saving..." : "Save profile"}</button>
    </header>
    <section className="grid gap-4 lg:grid-cols-2">
      <div className="rounded border border-stone-300 bg-white p-4">
        <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Parsed Profile</h2><Badge tone={review.profile ? "green" : "amber"}>{review.profile ? "Editable" : "Pending"}</Badge></div>
        {review.profile ? <div className="grid gap-3">
          {(["bio_json", "education_json", "experience_json", "skills_json", "links_json"] as const).map((key) => <label key={key} className="grid gap-1 text-sm font-medium">
            {key.replace("_json", "").replace("_", " ")}
            <textarea className="min-h-28 rounded border border-stone-300 p-3 font-mono text-xs" value={JSON.stringify(review.profile[key], null, 2)} onChange={(e) => setReview({ ...review, profile: { ...review.profile, [key]: JSON.parse(e.target.value || "null") } })} />
          </label>)}
        </div> : <p className="text-sm text-stone-700">Extraction has not populated a profile yet.</p>}
      </div>
      <div className="rounded border border-stone-300 bg-white p-4">
        <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Source Text</h2>{raw && <Badge>{raw.extraction_method}</Badge>}</div>
        {raw ? <><pre className="max-h-[42rem] overflow-auto whitespace-pre-wrap rounded bg-stone-100 p-3 text-sm">{raw.raw_text}</pre><pre className="mt-3 rounded bg-stone-100 p-3 text-xs">{JSON.stringify(raw.field_confidences_json, null, 2)}</pre></> : <p className="text-sm text-stone-700">Raw extraction is still processing.</p>}
      </div>
    </section>
  </main>;
}

