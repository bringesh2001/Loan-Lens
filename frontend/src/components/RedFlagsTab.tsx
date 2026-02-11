import { LoanAnalysis } from "@/lib/mock-data";
import { AlertTriangle, AlertCircle, Info, ChevronRight } from "lucide-react";

interface RedFlagsTabProps {
  redFlags: LoanAnalysis["redFlags"];
  onClauseClick: (clauseRef: string, page: number) => void;
}

const severityConfig = {
  high: { icon: AlertTriangle, label: "High Risk", className: "risk-high" },
  medium: { icon: AlertCircle, label: "Medium Risk", className: "risk-medium" },
  low: { icon: Info, label: "Low Risk", className: "risk-low" },
};

const RedFlagsTab = ({ redFlags, onClauseClick }: RedFlagsTabProps) => {
  return (
    <div className="space-y-3">
      {redFlags.map((flag) => {
        const config = severityConfig[flag.severity];
        const Icon = config.icon;
        return (
          <button
            key={flag.id}
            onClick={() => onClauseClick(flag.clauseRef, flag.page)}
            className={`w-full text-left rounded-lg border p-3.5 transition-all hover:shadow-md ${config.className}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2.5">
                <Icon className="w-4 h-4 mt-0.5 shrink-0" />
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold">{flag.title}</span>
                  </div>
                  <p className="text-xs opacity-80 leading-relaxed">{flag.explanation}</p>
                  <p className="text-[11px] opacity-60 mt-1.5 font-medium">{flag.clauseRef} · Page {flag.page}</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 opacity-40 shrink-0 mt-0.5" />
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default RedFlagsTab;
