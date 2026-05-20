"use client";

import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import type { CaseResultResponse, SSEDoneEvent, SSEProgressEvent } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface LiveRunProgressProps {
  runId: string;
  initialCases: CaseResultResponse[];
  totalCases: number;
}

export function LiveRunProgress({
  runId,
  initialCases,
  totalCases,
}: LiveRunProgressProps) {
  const [completed, setCompleted] = useState(initialCases.length);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const es = new EventSource(`${API_URL}/runs/${runId}/stream`);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SSEProgressEvent | SSEDoneEvent;
        if (data.type === "progress") {
          setCompleted(data.completed);
        } else if (data.type === "done") {
          setCompleted(totalCases);
          setDone(true);
          es.close();
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId, totalCases]);

  const pct = totalCases > 0 ? Math.round((completed / totalCases) * 100) : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{done ? "Complete" : "Running…"}</span>
        <span>
          {completed} / {totalCases} cases
        </span>
      </div>
      <Progress value={pct} />
    </div>
  );
}
