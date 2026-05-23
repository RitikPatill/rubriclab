"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import yaml from "js-yaml";
import { cloneSuite, updateRubric } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  suiteId: string;
  initialContent: string;
  path: string;
}

function validateRubricYaml(content: string): string | null {
  let parsed: unknown;
  try {
    parsed = yaml.load(content);
  } catch (e: unknown) {
    return e instanceof Error ? e.message : "YAML parse error";
  }
  if (typeof parsed !== "object" || parsed === null) {
    return "Root must be an object";
  }
  const obj = parsed as Record<string, unknown>;
  if (!obj.name) return "Missing required field: name";
  if (!Array.isArray(obj.criteria) || obj.criteria.length === 0) {
    return "criteria must be a non-empty array";
  }
  for (const c of obj.criteria as unknown[]) {
    if (typeof c !== "object" || c === null) {
      return "Each criterion must be an object";
    }
    const crit = c as Record<string, unknown>;
    if (!crit.id) return "Each criterion must have an id";
    if (!["scale", "bool"].includes(crit.type as string)) {
      return `criterion type must be "scale" or "bool", got: ${crit.type}`;
    }
    if (crit.type === "scale" && !crit.scale) {
      return `Scale criterion "${crit.id}" must have a scale block`;
    }
  }
  return null;
}

export function RubricEditor({ suiteId, initialContent, path }: Props) {
  const router = useRouter();
  const [content, setContent] = useState(initialContent);
  const [validationError, setValidationError] = useState<string | null>(
    validateRubricYaml(initialContent),
  );
  const [saveStatus, setSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");
  const [cloneName, setCloneName] = useState("");
  const [showClone, setShowClone] = useState(false);

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setContent(val);
    setValidationError(validateRubricYaml(val));
    setSaveStatus("idle");
  }

  async function handleSave() {
    setSaveStatus("saving");
    try {
      await updateRubric(suiteId, content);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch {
      setSaveStatus("error");
    }
  }

  async function handleClone() {
    try {
      const newSuite = await cloneSuite(suiteId, cloneName);
      router.push(`/suites/${newSuite.id}/rubric`);
    } catch {
      // silently fail — user can retry
    }
  }

  const saveLabel =
    saveStatus === "saving"
      ? "Saving…"
      : saveStatus === "saved"
        ? "Saved ✓"
        : saveStatus === "error"
          ? "Error saving"
          : "Save";

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-mono text-muted-foreground">
            {path}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            className="w-full resize-y rounded-md border bg-muted p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring min-h-[400px]"
            value={content}
            onChange={handleChange}
            spellCheck={false}
          />
          {validationError && (
            <p className="text-sm text-destructive">{validationError}</p>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={validationError !== null || saveStatus === "saving"}
              className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
            >
              {saveLabel}
            </button>
            <button
              onClick={() => setShowClone(!showClone)}
              className="rounded-md border px-4 py-2 text-sm"
            >
              Clone rubric
            </button>
          </div>
        </CardContent>
      </Card>

      {showClone && (
        <Card>
          <CardHeader>
            <CardTitle>Clone rubric</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Creates a new suite with a copy of this rubric file. Shares the
              same dataset.
            </p>
            <div className="flex items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">
                  New suite name
                </label>
                <input
                  type="text"
                  value={cloneName}
                  onChange={(e) => setCloneName(e.target.value)}
                  placeholder="v2"
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                />
              </div>
              <button
                onClick={handleClone}
                disabled={!cloneName.trim()}
                className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
              >
                Clone
              </button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
