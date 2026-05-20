import { Badge } from "@/components/ui/badge";

type RunStatus = "pending" | "running" | "completed" | "failed";

interface RunStatusBadgeProps {
  status: RunStatus | boolean;
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  if (typeof status === "boolean") {
    return status ? (
      <Badge className="bg-green-600 text-white hover:bg-green-600">Pass</Badge>
    ) : (
      <Badge variant="destructive">Fail</Badge>
    );
  }

  switch (status) {
    case "pending":
      return <Badge variant="secondary">Pending</Badge>;
    case "running":
      return (
        <Badge variant="outline" className="animate-pulse">
          Running
        </Badge>
      );
    case "completed":
      return (
        <Badge className="bg-green-600 text-white hover:bg-green-600">
          Completed
        </Badge>
      );
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
  }
}
