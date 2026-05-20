import Link from "next/link";
import { listRuns } from "@/lib/api";
import { RunSummary } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RunStatusBadge } from "@/components/run-status-badge";

function formatDuration(started: string, completed: string | null): string {
  if (!completed) return "running…";
  const ms = new Date(completed).getTime() - new Date(started).getTime();
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function passRate(run: RunSummary): string {
  if (run.total_cases === 0) return "—";
  const pct = Math.round((run.passed_cases / run.total_cases) * 100);
  return `${run.passed_cases} / ${run.total_cases} (${pct}%)`;
}

export default async function Home() {
  let runs: RunSummary[] = [];
  try {
    runs = await listRuns();
  } catch {
    // API not available — show empty state
  }

  if (runs.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-24 text-center">
        <h1 className="text-2xl font-semibold">No runs yet</h1>
        <p className="text-muted-foreground">
          Start one from the API or CLI:
        </p>
        <pre className="rounded-md border bg-muted px-4 py-3 text-left text-sm">
          POST http://localhost:8000/suites/&#123;suite_id&#125;/runs
        </pre>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Runs</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Run ID</TableHead>
            <TableHead>Suite</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Pass rate</TableHead>
            <TableHead>Started</TableHead>
            <TableHead>Duration</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow key={run.id}>
              <TableCell>
                <Link
                  href={`/runs/${run.id}`}
                  className="font-mono text-xs hover:underline"
                >
                  {run.id.slice(0, 8)}…
                </Link>
              </TableCell>
              <TableCell className="font-mono text-xs">{run.suite_id.slice(0, 8)}…</TableCell>
              <TableCell>
                <RunStatusBadge status={run.status} />
              </TableCell>
              <TableCell>{passRate(run)}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {new Date(run.started_at).toLocaleString()}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {formatDuration(run.started_at, run.completed_at)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
