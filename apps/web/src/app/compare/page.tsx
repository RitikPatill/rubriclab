import Link from "next/link";
import { compareRuns, getRun, listRuns } from "@/lib/api";
import { RunComparison, RunSummary, ScoreDelta } from "@/lib/types";
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

function fmtDelta(delta: number | null): string {
  if (delta === null) return "—";
  if (delta > 0) return `+${delta}`;
  if (delta < 0) return `${delta}`;
  return "0";
}

function DeltaCell({ scoreDelta }: { scoreDelta: ScoreDelta | undefined }) {
  if (!scoreDelta) return <span className="text-muted-foreground">—</span>;
  const { delta } = scoreDelta;
  if (delta === null) return <span className="text-muted-foreground">—</span>;
  if (delta > 0)
    return <span className="text-green-600 font-mono text-xs">{fmtDelta(delta)}</span>;
  if (delta < 0)
    return <span className="text-red-600 font-mono text-xs">{fmtDelta(delta)}</span>;
  return <span className="text-muted-foreground font-mono text-xs">0</span>;
}

function RunCard({ run, label }: { run: RunSummary; label: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">
          <span className="text-muted-foreground mr-2">{label}</span>
          <span className="font-mono">{run.id.slice(0, 8)}…</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <dt className="text-muted-foreground">Status</dt>
            <dd>
              <RunStatusBadge status={run.status} />
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Pass rate</dt>
            <dd>
              {run.total_cases > 0
                ? `${run.passed_cases}/${run.total_cases}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Agent version</dt>
            <dd>{run.agent_version}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Started</dt>
            <dd>{new Date(run.started_at).toLocaleString()}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: { a?: string; b?: string };
}) {
  const a = searchParams.a;
  const b = searchParams.b;

  if (!a && !b) {
    return (
      <div className="flex flex-col items-center gap-4 py-24 text-center">
        <h1 className="text-2xl font-semibold">Compare Runs</h1>
        <p className="text-muted-foreground">
          Navigate here with ?a=RUN_ID&b=RUN_ID
        </p>
        <pre className="rounded-md border bg-muted px-4 py-3 text-left text-sm">
          /compare?a=RUN_A_ID&b=RUN_B_ID
        </pre>
      </div>
    );
  }

  if (a && !b) {
    let runA;
    let otherRuns: RunSummary[] = [];
    try {
      [runA, otherRuns] = await Promise.all([getRun(a), listRuns()]);
    } catch {
      return (
        <div className="text-destructive py-12 text-center">Run not found</div>
      );
    }
    const others = otherRuns.filter((r) => r.id !== a);
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/" className="hover:underline">
            Runs
          </Link>
          <span>/</span>
          <span>Compare</span>
        </div>
        <h1 className="text-2xl font-semibold">Select second run to compare</h1>
        <RunCard run={runA} label="Run A" />
        {others.length === 0 ? (
          <p className="text-muted-foreground">
            No other runs available to compare.
          </p>
        ) : (
          <form method="GET" action="/compare" className="flex items-end gap-4">
            <input type="hidden" name="a" value={a} />
            <div className="flex flex-col gap-1">
              <label
                htmlFor="b-select"
                className="text-sm text-muted-foreground"
              >
                Compare with:
              </label>
              <select
                id="b-select"
                name="b"
                className="rounded-md border bg-background px-3 py-2 text-sm"
              >
                {others.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id.slice(0, 8)}… — {r.status} —{" "}
                    {new Date(r.started_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
            >
              Compare →
            </button>
          </form>
        )}
      </div>
    );
  }

  // Both a and b present
  let comparison: RunComparison;
  try {
    comparison = await compareRuns(a!, b!);
  } catch {
    return (
      <div className="text-destructive py-12 text-center">
        Failed to load comparison. Check that both run IDs are valid.
      </div>
    );
  }

  const criteriaIds = [
    ...new Set(comparison.cases.flatMap((c) => Object.keys(c.score_deltas))),
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/" className="hover:underline">
          Runs
        </Link>
        <span>/</span>
        <span>Compare</span>
      </div>
      <h1 className="text-2xl font-semibold">Run Comparison</h1>

      <div className="grid grid-cols-2 gap-4">
        <RunCard run={comparison.run_a} label="Run A" />
        <RunCard run={comparison.run_b} label="Run B" />
      </div>

      <div className="space-y-2">
        <h2 className="text-lg font-semibold">
          Case Comparison
          <span className="ml-3 text-sm font-normal text-muted-foreground">
            {comparison.cases.filter((c) => c.flipped).length} flipped
          </span>
        </h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Case ID</TableHead>
              <TableHead>A</TableHead>
              <TableHead>B</TableHead>
              <TableHead>Flipped</TableHead>
              {criteriaIds.map((c) => (
                <TableHead key={c} className="font-mono text-xs">
                  {c} Δ
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {comparison.cases.map((c) => (
              <TableRow
                key={c.case_id}
                className={
                  c.flipped ? "bg-yellow-50 dark:bg-yellow-900/20" : ""
                }
              >
                <TableCell className="font-mono text-xs">{c.case_id}</TableCell>
                <TableCell>
                  {c.a_passed === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <RunStatusBadge status={c.a_passed} />
                  )}
                </TableCell>
                <TableCell>
                  {c.b_passed === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <RunStatusBadge status={c.b_passed} />
                  )}
                </TableCell>
                <TableCell>
                  {c.flipped ? (
                    <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                      flipped
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                {criteriaIds.map((criterion) => (
                  <TableCell key={criterion}>
                    <DeltaCell scoreDelta={c.score_deltas[criterion]} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
