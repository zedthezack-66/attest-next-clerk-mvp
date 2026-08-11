"use client";
import type { JobPosting } from "@attest/shared-types";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api-client";

export default function DashboardHome() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  useEffect(() => { api<JobPosting[]>("/jobs").then(setJobs).catch(() => location.href = "/login"); }, []);
  return <main className="mx-auto max-w-6xl px-6 py-8">
    <header className="mb-6 flex items-end justify-between border-b border-stone-300 pb-4">
      <div><p className="text-sm font-semibold uppercase text-emerald-800">Attest Dashboard</p><h1 className="text-3xl font-semibold">Job Postings</h1></div>
    </header>
    <div className="grid gap-3">
      {jobs.map((job) => <Link key={job.id} href={`/jobs/${job.id}/candidates`} className="rounded border border-stone-300 bg-white p-4 hover:border-slate-800">
        <h2 className="font-semibold">{job.title}</h2><p className="mt-1 text-sm text-stone-700">{job.status}</p>
      </Link>)}
    </div>
  </main>;
}

