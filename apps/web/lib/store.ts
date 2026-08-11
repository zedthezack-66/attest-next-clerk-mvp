import { mkdir, readFile, writeFile } from "fs/promises";
import path from "path";
import crypto from "crypto";
import type { Application, CandidateProfile, DataStore, DocumentRecord, ExtractionResult } from "./types";

const dataDir = path.join(process.cwd(), "data");
const uploadDir = path.join(process.cwd(), "storage", "uploads");
const dataPath = path.join(dataDir, "attest.local.json");
const tenantId = "tenant_pilot";

const seed: DataStore = {
  tenants: [{ id: tenantId, name: "Pilot Employer" }],
  jobs: [{
    id: "job_finance_officer",
    tenantId,
    title: "Finance Officer",
    slug: "finance-officer-lusaka",
    description: "Manage reconciliations, statutory reporting, and grant controls for a Lusaka-based operations team.",
    requirements: { qualificationLevel: "Diploma", skills: ["Excel", "financial reporting", "controls"], documents: ["CV", "certificate"] },
    status: "open",
  }],
  applications: [],
  documents: [],
  extractions: [],
  profiles: [],
};

export async function readStore(): Promise<DataStore> {
  await mkdir(dataDir, { recursive: true });
  await mkdir(uploadDir, { recursive: true });
  try {
    return JSON.parse(await readFile(dataPath, "utf8"));
  } catch {
    await writeStore(seed);
    return structuredClone(seed);
  }
}

export async function writeStore(store: DataStore) {
  await mkdir(dataDir, { recursive: true });
  await writeFile(dataPath, JSON.stringify(store, null, 2));
}

export function id(prefix: string) {
  return `${prefix}_${crypto.randomUUID()}`;
}

export function hashBuffer(buffer: Buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

export async function saveUpload(file: File, applicationId: string) {
  const bytes = Buffer.from(await file.arrayBuffer());
  const hash = hashBuffer(bytes);
  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, "_");
  const storageName = `${applicationId}-${crypto.randomUUID()}-${safeName}`;
  const storagePath = path.join(uploadDir, storageName);
  await writeFile(storagePath, bytes);
  return { hash, storagePath, filename: file.name, bytes };
}

export function extractPreviewText(filename: string, bytes: Buffer) {
  const ext = path.extname(filename).toLowerCase();
  if (ext === ".txt") return bytes.toString("utf8");
  return `Uploaded document: ${filename}\n\nLocal MVP preview captured the file and queued it for production OCR/extraction adapter integration.`;
}

export function structureText(rawText: string, candidateName: string, candidateEmail: string) {
  const lines = rawText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const skills = ["Excel", "Python", "SQL", "financial reporting", "project management", "JavaScript"].filter((skill) => rawText.toLowerCase().includes(skill.toLowerCase()));
  const education = lines.filter((line) => /diploma|degree|bachelor|master|certificate/i.test(line)).map((line) => ({ raw: line, qualification: line }));
  return {
    structured: {
      bio: { candidateName, summary: lines[0] ?? "Awaiting reviewer summary", contact: { email: candidateEmail } },
      education,
      experience: lines.filter((line) => /experience|worked|managed|led/i.test(line)).map((line) => ({ raw: line })),
      skills,
      links: rawText.match(/https?:\/\/\S+/g) ?? [],
    },
    confidences: { "bio.summary": lines.length ? 0.68 : 0.25, education: education.length ? 0.7 : 0.25, skills: skills.length ? 0.8 : 0.3 },
  };
}

export function createProfile(app: Application, extraction: ExtractionResult): CandidateProfile {
  const structured = extraction.structured as { bio?: Record<string, unknown>; education?: unknown[]; experience?: unknown[]; skills?: unknown[]; links?: unknown[] };
  return {
    id: id("profile"),
    tenantId: app.tenantId,
    applicationId: app.id,
    bio: structured.bio ?? {},
    education: structured.education ?? [],
    experience: structured.experience ?? [],
    skills: structured.skills ?? [],
    links: structured.links ?? [],
  };
}

