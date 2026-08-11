import type { JobPosting } from "@attest/shared-types";
import Link from "next/link";
import { api } from "../lib/api-client";

export default async function Page() {
  const jobs = await api<JobPosting[]>("/jobs/public");
  return <main className="mx-auto max-w-5xl px-6 py-10">
    <header className="mb-8 border-b border-stone-300 pb-5">
      <p className="text-sm font-semibold uppercase tracking-wide text-emerald-800">Attest Careers</p>
      <h1 className="mt-2 text-3xl font-semibold">Open Roles</h1>
    </header>
    <div className="grid gap-3">
      {jobs.map((job) => <Link className="rounded border border-stone-300 bg-white p-5 hover:border-emerald-700" href={`/jobs/${job.slug}`} key={job.id}>
        <h2 className="text-xl font-semibold">{job.title}</h2>
        <p className="mt-2 text-sm text-stone-700">{job.description}</p>
      </Link>)}
    </div>
  </main>;
}

