export type JobPosting = {
  id: string;
  title: string;
  slug: string;
  description: string;
  requirements_json: Record<string, unknown>;
  deadline?: string;
  status: string;
};

export type Application = {
  id: string;
  job_posting_id: string;
  candidate_name: string;
  candidate_email: string;
  submitted_at: string;
  status: string;
};

export type CandidateProfile = {
  id: string;
  application_id: string;
  bio_json: Record<string, unknown>;
  education_json: unknown[];
  experience_json: unknown[];
  skills_json: unknown[];
  links_json: unknown[];
  last_edited_at?: string;
};

