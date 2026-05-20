interface ScoreCellProps {
  score: number | boolean;
  type: "scale" | "bool";
  scaleMax?: number;
  invert?: boolean;
}

export function ScoreCell({
  score,
  type,
  scaleMax = 5,
  invert = false,
}: ScoreCellProps) {
  if (type === "bool") {
    const passed = invert ? !score : !!score;
    return passed ? (
      <span className="font-medium text-green-600 dark:text-green-400">✓</span>
    ) : (
      <span className="font-medium text-red-600 dark:text-red-400">✗</span>
    );
  }

  const numScore = typeof score === "boolean" ? (score ? scaleMax : 1) : score;
  const threshold = Math.ceil((1 + scaleMax) / 2);
  const isGood = numScore >= threshold;

  return (
    <span
      className={
        isGood
          ? "font-medium text-green-600 dark:text-green-400"
          : "font-medium text-red-600 dark:text-red-400"
      }
    >
      {numScore}/{scaleMax}
    </span>
  );
}
