export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type FileRecord = {
  id: string;
  original_name: string;
  mime_type: string;
  file_size: number;
  page_count: number;
  created_at: string;
};

export type JobStatus = "uploaded" | "queued" | "processing" | "completed" | "failed" | "canceled";

export type Job = {
  id: string;
  file_id: string;
  mode: string;
  output_format: string;
  template_type?: string | null;
  status: JobStatus;
  progress: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  file?: FileRecord | null;
};

export type PageResult = {
  id: string;
  job_id: string;
  page_no: number;
  raw_text: string;
  raw_markdown: string;
  reviewed_text: string;
  reviewed_markdown: string;
  confidence_summary: Record<string, unknown>;
  is_confirmed: boolean;
};

export type StructuredResult = {
  id: string;
  job_id: string;
  template_type?: string | null;
  raw_json: Record<string, unknown>;
  reviewed_json: Record<string, unknown>;
  is_confirmed: boolean;
};

export type JobResult = {
  job: Job;
  pages: PageResult[];
  structured_result?: StructuredResult | null;
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Ignore non-JSON errors.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function uploadFile(file: File): Promise<FileRecord> {
  const form = new FormData();
  form.append("upload", file);
  return apiFetch<FileRecord>("/api/files/upload", { method: "POST", body: form });
}

export function createJob(payload: {
  file_id: string;
  mode: string;
  output_format: string;
  template_type?: string | null;
}): Promise<Job> {
  return apiFetch<Job>("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
}

export function listJobs(params?: { q?: string; status_filter?: string }): Promise<Job[]> {
  const search = new URLSearchParams();
  if (params?.q) search.set("q", params.q);
  if (params?.status_filter) search.set("status_filter", params.status_filter);
  const qs = search.toString();
  return apiFetch<Job[]>(`/api/jobs${qs ? `?${qs}` : ""}`);
}

export function retryJob(jobId: string): Promise<Job> {
  return apiFetch<Job>(`/api/jobs/${jobId}/retry`, { method: "POST" });
}

export function getJobResult(jobId: string): Promise<JobResult> {
  return apiFetch<JobResult>(`/api/jobs/${jobId}/result`);
}

export function updateResult(
  jobId: string,
  payload: {
    page_no?: number;
    reviewed_text?: string;
    reviewed_markdown?: string;
    reviewed_json?: Record<string, unknown>;
    is_confirmed?: boolean;
  },
): Promise<JobResult> {
  return apiFetch<JobResult>(`/api/jobs/${jobId}/result`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function exportJob(jobId: string, format: string): Promise<{ format: string; filename: string; download_url: string }> {
  return apiFetch(`/api/jobs/${jobId}/export`, { method: "POST", body: JSON.stringify({ format }) });
}
