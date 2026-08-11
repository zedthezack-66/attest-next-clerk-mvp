import { NextResponse } from "next/server";
import { createProfile, extractPreviewText, id, readStore, saveUpload, structureText, writeStore } from "../../../../lib/store";
import type { Application, DocumentRecord, ExtractionResult } from "../../../../lib/types";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const form = await request.formData();
  const jobId = String(form.get("jobId") ?? "");
  const candidateName = String(form.get("candidateName") ?? "");
  const candidateEmail = String(form.get("candidateEmail") ?? "");
  const docType = String(form.get("docType") ?? "cv") as DocumentRecord["docType"];
  const files = form.getAll("documents").filter((item): item is File => item instanceof File && item.size > 0);
  if (!jobId || !candidateName || !candidateEmail || !files.length) return new NextResponse("Missing application details", { status: 400 });

  const store = await readStore();
  const job = store.jobs.find((item) => item.id === jobId && item.status === "open");
  if (!job) return new NextResponse("Job not found", { status: 404 });

  const application: Application = {
    id: id("app"),
    tenantId: job.tenantId,
    jobPostingId: job.id,
    candidateName,
    candidateEmail,
    submittedAt: new Date().toISOString(),
    status: "ready",
  };
  store.applications.push(application);

  for (const file of files) {
    const upload = await saveUpload(file, application.id);
    const duplicate = store.documents.find((doc) => doc.applicationId === application.id && doc.contentHash === upload.hash);
    if (duplicate) continue;
    const document: DocumentRecord = {
      id: id("doc"),
      tenantId: application.tenantId,
      applicationId: application.id,
      docType,
      filename: upload.filename,
      storagePath: upload.storagePath,
      contentHash: upload.hash,
      uploadedAt: new Date().toISOString(),
    };
    const rawText = extractPreviewText(upload.filename, upload.bytes);
    const { structured, confidences } = structureText(rawText, candidateName, candidateEmail);
    const extraction: ExtractionResult = {
      id: id("ext"),
      tenantId: application.tenantId,
      documentId: document.id,
      rawText,
      structured,
      fieldConfidences: confidences,
      extractionMethod: "local_preview",
      createdAt: new Date().toISOString(),
    };
    store.documents.push(document);
    store.extractions.push(extraction);
    if (!store.profiles.some((profile) => profile.applicationId === application.id)) {
      store.profiles.push(createProfile(application, extraction));
    }
  }

  await writeStore(store);
  return NextResponse.json({ applicationId: application.id });
}

