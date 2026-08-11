"use client";
import type { Application } from "@attest/shared-types";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../../../lib/api-client";

export default function Candidates({ params }: { params: { jobId: string } }) {
  const [items, setItems] = useState<Application[]>([]);
  useEffect(() => { api<Application[]>(`/applications/jobs/${params.jobId}`).then(setItems).catch(() => location.href = "/login"); }, [params.jobId]);
  return <main className="mx-auto max-w-6xl px-6 py-8">
    <Link href="/" className="text-sm text-emerald-800">Back to jobs</Link>
    <h1 className="mt-4 text-3xl font-semibold">Applications</h1>
    <table className="mt-6 w-full border-collapse bg-white text-sm">
      <thead><tr className="border-b bg-stone-100 text-left"><th className="p-3">Candidate</th><th className="p-3">Email</th><th className="p-3">Status</th><th className="p-3">Submitted</th></tr></thead>
      <tbody>{items.map((app) => <tr key={app.id} className="border-b border-stone-200 hover:bg-stone-50">
        <td className="p-3"><Link className="font-medium text-slate-900 underline" href={`/jobs/${params.jobId}/candidates/${app.id}`}>{app.candidate_name}</Link></td>
        <td className="p-3">{app.candidate_email}</td><td className="p-3">{app.status}</td><td className="p-3">{new Date(app.submitted_at).toLocaleString()}</td>
      </tr>)}</tbody>
    </table>
  </main>;
}

