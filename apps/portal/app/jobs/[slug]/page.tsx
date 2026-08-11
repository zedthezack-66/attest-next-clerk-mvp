import type { JobPosting } from "@attest/shared-types";
import Link from "next/link";
import { api } from "../../../lib/api-client";

export default async function JobPage({ params }: { params: { slug: string } }) {
  const job = await api<JobPosting>(`/jobs/public/${params.slug}`);
  return <main className="mx-auto max-w-3xl px-6 py-10">
    <Link className="text-sm text-emerald-800" href="/">Back to roles</Link>
    <h1 className="mt-5 text-3xl font-semibold">{job.title}</h1>
    <p className="mt-4 text-stone-700">{job.description}</p>
    <section className="mt-6 border-t border-stone-300 pt-5">
      <h2 className="font-semibold">Requirements</h2>
      <pre className="mt-3 rounded bg-stone-100 p-4 text-sm">{JSON.stringify(job.requirements_json, null, 2)}</pre>
    </section>
    <Link className="mt-8 inline-flex rounded bg-emerald-800 px-4 py-2 text-white" href={`/apply/${job.id}`}>Apply</Link>
  </main>;
}

