import Link from "next/link";
import { getRubric, listSuites } from "@/lib/api";
import { RubricEditor } from "@/components/rubric-editor";

export default async function RubricPage({
  params,
}: {
  params: { id: string };
}) {
  const [rubric, suites] = await Promise.all([
    getRubric(params.id),
    listSuites(),
  ]);
  const suite = suites.find((s) => s.id === params.id);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/" className="hover:underline">
          Runs
        </Link>
        <span>/</span>
        <span>Suites</span>
        <span>/</span>
        <span>{suite?.name ?? params.id.slice(0, 8)}</span>
        <span>/</span>
        <span>Rubric</span>
      </div>
      <h1 className="text-2xl font-semibold">Rubric Editor</h1>
      <RubricEditor
        suiteId={params.id}
        initialContent={rubric.content}
        path={rubric.path}
      />
    </div>
  );
}
