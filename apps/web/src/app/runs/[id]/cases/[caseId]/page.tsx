import Link from "next/link";
import { getRun } from "@/lib/api";
import { TraceEvent } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RunStatusBadge } from "@/components/run-status-badge";
import { ScoreCell } from "@/components/score-cell";
import { Separator } from "@/components/ui/separator";

function TraceEventRow({ event }: { event: TraceEvent }) {
  switch (event.type) {
    case "tool_call": {
      const d = event.data as { tool?: string; input?: unknown };
      return (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge className="bg-slate-700 text-white hover:bg-slate-700 dark:bg-slate-600">
              TOOL
            </Badge>
            <span className="font-mono text-sm font-medium">{d.tool ?? "unknown"}</span>
            <span className="text-xs text-muted-foreground">{event.timestamp}</span>
          </div>
          <pre className="overflow-auto rounded-md border bg-muted p-3 text-xs">
            {JSON.stringify(d.input ?? d, null, 2)}
          </pre>
        </div>
      );
    }
    case "tool_result": {
      const d = event.data as { tool?: string; output?: unknown };
      return (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="outline">RESULT</Badge>
            <span className="font-mono text-sm font-medium">{d.tool ?? "unknown"}</span>
            <span className="text-xs text-muted-foreground">{event.timestamp}</span>
          </div>
          <pre className="overflow-auto rounded-md border bg-muted p-3 text-xs">
            {JSON.stringify(d.output ?? d, null, 2)}
          </pre>
        </div>
      );
    }
    case "text": {
      const d = event.data as { content?: string };
      return (
        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">{event.timestamp}</span>
          <p className="text-sm">{d.content ?? JSON.stringify(event.data)}</p>
        </div>
      );
    }
    case "error": {
      return (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="destructive">ERROR</Badge>
            <span className="text-xs text-muted-foreground">{event.timestamp}</span>
          </div>
          <pre className="overflow-auto rounded-md border border-destructive bg-muted p-3 text-xs text-destructive">
            {JSON.stringify(event.data, null, 2)}
          </pre>
        </div>
      );
    }
    default:
      return (
        <pre className="overflow-auto rounded-md border bg-muted p-3 text-xs">
          {JSON.stringify(event, null, 2)}
        </pre>
      );
  }
}

export default async function CasePage({
  params,
}: {
  params: { id: string; caseId: string };
}) {
  const run = await getRun(params.id);
  const caseResult = run.cases.find((c) => c.id === params.caseId);

  if (!caseResult) {
    return (
      <div className="py-24 text-center text-muted-foreground">
        Case not found.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/" className="hover:underline">
          Runs
        </Link>
        <span>/</span>
        <Link href={`/runs/${run.id}`} className="hover:underline font-mono">
          {run.id.slice(0, 8)}…
        </Link>
        <span>/</span>
        <span className="font-mono">{caseResult.case_id}</span>
      </div>

      {/* Case header */}
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold font-mono">{caseResult.case_id}</h1>
        <RunStatusBadge status={caseResult.passed} />
      </div>

      {/* Agent output */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Agent output</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap text-sm">{caseResult.agent_output}</p>
        </CardContent>
      </Card>

      {/* Trace viewer */}
      {caseResult.trace.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Trace</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-4">
              {caseResult.trace.map((event, i) => (
                <li key={i}>
                  <TraceEventRow event={event} />
                  {i < caseResult.trace.length - 1 && (
                    <Separator className="mt-4" />
                  )}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* Judge scores */}
      {Object.keys(caseResult.rubric_scores).length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Judge scores</h2>
          {Object.entries(caseResult.rubric_scores).map(([criterionId, entry]) => {
            const isNum = typeof entry.score === "number";
            return (
              <Card key={criterionId}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between gap-4">
                    <span className="font-mono text-sm font-medium">{criterionId}</span>
                    <ScoreCell
                      score={entry.score}
                      type={isNum ? "scale" : "bool"}
                    />
                  </div>
                  {entry.reasoning && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      {entry.reasoning}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Deterministic checks */}
      {caseResult.deterministic_checks.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Deterministic checks</h2>
          <Card>
            <CardContent className="pt-4">
              <ul className="space-y-2">
                {caseResult.deterministic_checks.map((check, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm">
                    <RunStatusBadge status={check.passed} />
                    <div>
                      <span className="font-medium">{check.name}</span>
                      {check.detail && (
                        <p className="text-muted-foreground">{check.detail}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
