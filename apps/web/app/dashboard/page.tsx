import Link from "next/link";
import { readStore } from "../../lib/store";

export default async function Dashboard() {
  const store = await readStore();
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6 border-b border-stone-300 pb-4">
        <p className="text-sm font-semibold uppercase text-emerald-800">Hiring Dashboard</p>
        <h1 className="text-3xl font-semibold">Job Postings</h1>
      </header>
      <div className="grid gap-3">
        {store.jobs.map((job) => {
          const count = store.applications.filter((app) => app.jobPostingId === job.id).length;
          return (
            <Link key={job.id} href={`/dashboard/jobs/${job.id}/candidates`} className="rounded border border-stone-300 bg-white p-4 hover:border-slate-800">
              <h2 className="font-semibold">{job.title}</h2>
              <p className="mt-1 text-sm text-stone-700">{count} applications</p>
            </Link>
          );
        })}
      </div>
    </main>
  );
}

