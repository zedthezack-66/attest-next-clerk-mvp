import { NextResponse } from "next/server";
import { readStore } from "../../../../lib/store";

export async function GET(_request: Request, { params }: { params: { slug: string } }) {
  const store = await readStore();
  const job = store.jobs.find((item) => item.slug === params.slug && item.status === "open");
  if (!job) return new NextResponse("Job not found", { status: 404 });
  return NextResponse.json(job);
}

