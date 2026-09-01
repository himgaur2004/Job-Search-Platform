import { Job, Reply, SummaryData, Followup } from "./types";

const API = "/api";

export async function fetchSummary(): Promise<SummaryData> {
  const res = await fetch(`${API}/summary`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function fetchJobs(limit = 100, offset = 0, q?: string, location?: string, source?: string): Promise<Job[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q && q.trim()) params.set("q", q.trim());
  if (location && location.trim()) params.set("location", location.trim());
  if (source && source.trim()) params.set("source", source.trim());
  const res = await fetch(`${API}/jobs?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch jobs");
  return res.json();
}

export async function fetchReplies(limit = 50, offset = 0): Promise<Reply[]> {
  const res = await fetch(`${API}/replies?limit=${limit}&offset=${offset}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch replies");
  return res.json();
}

export async function fetchFollowups(limit = 50, offset = 0): Promise<Followup[]> {
  const res = await fetch(`${API}/followups?limit=${limit}&offset=${offset}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch followups");
  return res.json();
}

export async function resumeJob(jobId: number, email: string): Promise<void> {
  const res = await fetch(`${API}/jobs/${jobId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error("Failed to resume job");
}

export async function fetchScoutStatus() {
  const res = await fetch(`${API}/service1/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch scout status");
  return res.json();
}

export async function runScout(keyword: string, location: string) {
  const res = await fetch(`${API}/service1/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword, location }),
  });
  if (!res.ok) throw new Error("Failed to start scout");
  return res.json();
}

export async function autoApply(jobId: number, url: string, resumeMode: "prebuilt" | "generate" = "prebuilt") {
  const res = await fetch(`${API}/jobs/${jobId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, url, resume_mode: resumeMode }),
  });
  if (!res.ok) throw new Error("Failed to start auto apply");
  return res.json();
}

export async function fetchTemplates() {
  const res = await fetch(`${API}/templates`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch templates");
  return res.json();
}

export async function createTemplate(data: { name: string; subject_template: string; body_template: string; is_active: boolean }) {
  const res = await fetch(`${API}/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create template");
  return res.json();
}

export async function updateTemplate(id: number, data: { name: string; subject_template: string; body_template: string; is_active: boolean }) {
  const res = await fetch(`${API}/templates/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update template");
  return res.json();
}

export async function deleteTemplate(id: number) {
  const res = await fetch(`${API}/templates/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete template");
  return res.json();
}
