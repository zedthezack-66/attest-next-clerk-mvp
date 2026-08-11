import { NextResponse } from "next/server";
import { readStore } from "../../../lib/store";

export async function GET() {
  const store = await readStore();
  return NextResponse.json(store.jobs.filter((job) => job.status === "open"));
}

