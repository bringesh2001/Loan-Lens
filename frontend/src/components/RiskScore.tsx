import { useMemo } from "react";

interface RiskScoreProps {
  score: number;
}

const RiskScore = ({ score }: RiskScoreProps) => {
  const { label, colorClass, bgClass } = useMemo(() => {
    if (score >= 70) return { label: "High Risk", colorClass: "text-destructive", bgClass: "bg-destructive" };
    if (score >= 40) return { label: "Moderate Risk", colorClass: "text-warning", bgClass: "bg-warning" };
    return { label: "Low Risk", colorClass: "text-success", bgClass: "bg-success" };
  }, [score]);

  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-28 h-28">
        <svg className="w-28 h-28 -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" fill="none" stroke="hsl(var(--border))" strokeWidth="8" />
          <circle
            cx="60"
            cy="60"
            r="54"
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={`${colorClass} transition-all duration-1000 ease-out`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-2xl font-bold ${colorClass}`}>{score}</span>
          <span className="text-[10px] text-muted-foreground font-medium">/ 100</span>
        </div>
      </div>
      <span className={`text-xs font-semibold ${colorClass}`}>{label}</span>
    </div>
  );
};

export default RiskScore;
