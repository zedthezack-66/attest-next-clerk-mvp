import { NextResponse } from "next/server";
import { readStore } from "../../../../../lib/store";

export async function GET(_request: Request, { params }: { params: { applicationId: string } }) {
  const store = await readStore();
  const application = store.applications.find((app) => app.id === params.applicationId);
  if (!application) return new NextResponse("Application not found", { status: 404 });
  const profile = store.profiles.find((item) => item.applicationId === application.id);
  const documents = store.documents.filter((doc) => doc.applicationId === application.id).map((document) => ({
    document,
    latestExtraction: store.extractions.filter((result) => result.documentId === document.id).at(-1),
  }));
  return NextResponse.json({ application, profile, documents });
}

