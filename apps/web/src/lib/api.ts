import type { RubricContent, RunComparison, RunDetail, RunSummary, Suite } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function listRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_URL}/runs`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch runs: ${res.status}`);
  return res.json();
}

export async function getRun(id: string): Promise<RunDetail> {
  const res = await fetch(`${API_URL}/runs/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch run ${id}: ${res.status}`);
  return res.json();
}

export async function listSuites(): Promise<Suite[]> {
  const res = await fetch(`${API_URL}/suites`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch suites: ${res.status}`);
  return res.json();
}

export async function compareRuns(a: string, b: string): Promise<RunComparison> {
  const res = await fetch(`${API_URL}/runs/compare?a=${a}&b=${b}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to compare runs: ${res.status}`);
  return res.json();
}

export async function getRubric(suiteId: string): Promise<RubricContent> {
  const res = await fetch(`${API_URL}/suites/${suiteId}/rubric`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch rubric: ${res.status}`);
  return res.json();
}

export async function updateRubric(
  suiteId: string,
  content: string,
): Promise<RubricContent> {
  const res = await fetch(`${API_URL}/suites/${suiteId}/rubric`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Failed to update rubric: ${res.status}`);
  return res.json();
}

export async function cloneSuite(suiteId: string, name: string): Promise<Suite> {
  const res = await fetch(`${API_URL}/suites/${suiteId}/clone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Failed to clone suite: ${res.status}`);
  return res.json();
}

export { API_URL };
