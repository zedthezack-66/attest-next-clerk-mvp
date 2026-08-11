import Link from "next/link";
import { readStore } from "../../../../../lib/store";

export default async function Candidates({ params }: { params: { jobId: string } }) {
  const store = await readStore();
  const items = store.applications.filter((app) => app.jobPostingId === params.jobId);
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <Link href="/dashboard" className="text-sm text-emerald-800">Back to jobs</Link>
      <h1 className="mt-4 text-3xl font-semibold">Applications</h1>
      <table className="mt-6 w-full border-collapse bg-white text-sm">
        <thead><tr className="border-b bg-stone-100 text-left"><th className="p-3">Candidate</th><th className="p-3">Email</th><th className="p-3">Status</th><th className="p-3">Submitted</th></tr></thead>
        <tbody>{items.map((app) => (
          <tr key={app.id} className="border-b border-stone-200 hover:bg-stone-50">
            <td className="p-3"><Link className="font-medium underline" href={`/dashboard/candidates/${app.id}`}>{app.candidateName}</Link></td>
            <td className="p-3">{app.candidateEmail}</td>
            <td className="p-3">{app.status}</td>
            <td className="p-3">{new Date(app.submittedAt).toLocaleString()}</td>
          </tr>
        ))}</tbody>
      </table>
    </main>
  );
}

