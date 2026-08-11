export type JobPosting = {
  id: string;
  tenantId: string;
  title: string;
  slug: string;
  description: string;
  requirements: Record<string, unknown>;
  status: "open" | "closed";
};

export type Application = {
  id: string;
  tenantId: string;
  jobPostingId: string;
  candidateName: string;
  candidateEmail: string;
  submittedAt: string;
  status: "submitted" | "processing" | "ready";
};

export type DocumentRecord = {
  id: string;
  tenantId: string;
  applicationId: string;
  docType: "cv" | "cover_letter" | "certificate" | "national_id";
  filename: string;
  storagePath: string;
  contentHash: string;
  uploadedAt: string;
};

export type ExtractionResult = {
  id: string;
  tenantId: string;
  documentId: string;
  rawText: string;
  structured: Record<string, unknown>;
  fieldConfidences: Record<string, number>;
  extractionMethod: "direct_text" | "local_preview";
  createdAt: string;
};

export type CandidateProfile = {
  id: string;
  tenantId: string;
  applicationId: string;
  bio: Record<string, unknown>;
  education: unknown[];
  experience: unknown[];
  skills: unknown[];
  links: unknown[];
  lastEditedBy?: string;
  lastEditedAt?: string;
};

export type DataStore = {
  tenants: { id: string; name: string }[];
  jobs: JobPosting[];
  applications: Application[];
  documents: DocumentRecord[];
  extractions: ExtractionResult[];
  profiles: CandidateProfile[];
};

