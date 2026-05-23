export interface Suite {
  id: string;
  name: string;
  rubric_path: string;
  dataset_path: string;
  created_at: string;
}

export interface RunSummary {
  id: string;
  suite_id: string;
  status: "pending" | "running" | "completed" | "failed";
  git_sha: string | null;
  agent_version: string;
  started_at: string;
  completed_at: string | null;
  total_cases: number;
  passed_cases: number;
}

export interface TraceEvent {
  type: "tool_call" | "tool_result" | "text" | "error";
  timestamp: string;
  data: Record<string, unknown>;
}

export interface CriterionScore {
  score: number | boolean;
  reasoning: string;
}

export interface DeterministicCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface CaseResultResponse {
  id: string;
  case_id: string;
  agent_output: string;
  trace: TraceEvent[];
  rubric_scores: Record<string, CriterionScore>;
  deterministic_checks: DeterministicCheck[];
  passed: boolean;
}

export interface RunDetail extends RunSummary {
  cases: CaseResultResponse[];
}

export interface SSEProgressEvent {
  type: "progress";
  case_id: string;
  passed: boolean;
  completed: number;
  total: number;
}

export interface SSEDoneEvent {
  type: "done";
  status: string;
  run_id: string;
}

export interface ScoreDelta {
  a: number | boolean | null;
  b: number | boolean | null;
  delta: number | null;
}

export interface CaseComparison {
  case_id: string;
  a_passed: boolean | null;
  b_passed: boolean | null;
  flipped: boolean;
  score_deltas: Record<string, ScoreDelta>;
}

export interface RunComparison {
  run_a: RunSummary;
  run_b: RunSummary;
  cases: CaseComparison[];
}

export interface RubricContent {
  content: string;
  path: string;
}
