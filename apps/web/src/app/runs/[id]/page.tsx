import Link from "next/link";
import { getRun } from "@/lib/api";
import { RunDetail } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RunStatusBadge } from "@/components/run-status-badge";
import { ScoreCell } from "@/components/score-cell";
import { LiveRunProgress } from "@/components/live-run-progress";

export default async function RunPage({
  params,
}: {
  params: { id: string };
}) {
  const run: RunDetail = await getRun(params.id);

  const criteriaIds = Object.keys(run.cases[0]?.rubric_scores ?? {});

  const completedAt = run.completed_at
    ? new Date(run.completed_at).toLocaleString()
    : "—";
  const startedAt = new Date(run.started_at).toLocaleString();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/" className="hover:underline">
            Runs
          </Link>
          <span>/</span>
          <span className="font-mono">{run.id.slice(0, 8)}…</span>
        </div>
        <Link
          href={`/compare?a=${run.id}`}
          className="text-xs hover:underline text-muted-foreground"
        >
          Compare →
        </Link>
      </div>

      {/* Run metadata card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            Run detail
            <RunStatusBadge status={run.status} />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Suite</dt>
              <dd className="font-mono">{run.suite_id.slice(0, 8)}…</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Agent version</dt>
              <dd>{run.agent_version}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Git SHA</dt>
              <dd className="font-mono">{run.git_sha?.slice(0, 8) ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Started</dt>
              <dd>{startedAt}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Completed</dt>
              <dd>{completedAt}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Pass rate</dt>
              <dd>
                {run.total_cases > 0
                  ? `${run.passed_cases} / ${run.total_cases} (${Math.round((run.passed_cases / run.total_cases) * 100)}%)`
                  : "—"}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Live progress bar while running */}
      {run.status === "running" && (
        <Card>
          <CardContent className="pt-6">
            <LiveRunProgress
              runId={run.id}
              initialCases={run.cases}
              totalCases={run.total_cases}
            />
          </CardContent>
        </Card>
      )}

      {/* Case results table */}
      {run.cases.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Cases</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Case ID</TableHead>
                <TableHead>Result</TableHead>
                {criteriaIds.map((c) => (
                  <TableHead key={c} className="font-mono text-xs">
                    {c}
                  </TableHead>
                ))}
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.cases.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-mono text-xs">{c.case_id}</TableCell>
                  <TableCell>
                    <RunStatusBadge status={c.passed} />
                  </TableCell>
                  {criteriaIds.map((criterionId) => {
                    const scoreEntry = c.rubric_scores[criterionId];
                    if (!scoreEntry) return <TableCell key={criterionId}>—</TableCell>;
                    const isNum = typeof scoreEntry.score === "number";
                    return (
                      <TableCell key={criterionId}>
                        <ScoreCell
                          score={scoreEntry.score}
                          type={isNum ? "scale" : "bool"}
                        />
                      </TableCell>
                    );
                  })}
                  <TableCell>
                    <Link
                      href={`/runs/${run.id}/cases/${c.id}`}
                      className="text-xs hover:underline"
                    >
                      Trace →
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
