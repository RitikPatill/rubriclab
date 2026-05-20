import type { RunDetail, RunSummary, Suite } from "./types";

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

export { API_URL };
