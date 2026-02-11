import { useQuery } from "@tanstack/react-query";
import { useDocument } from "@/context/DocumentContext";
import { getRedFlags } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertTriangle, AlertCircle, Info, ChevronRight } from "lucide-react";
import type { RedFlag } from "@/lib/types";

// ==========================================================================
// Severity Config
// ==========================================================================

const severityConfig = {
  high: { icon: AlertTriangle, label: "High Risk", className: "risk-high", order: 0 },
  medium: { icon: AlertCircle, label: "Medium Risk", className: "risk-medium", order: 1 },
  low: { icon: Info, label: "Low Risk", className: "risk-low", order: 2 },
};

// ==========================================================================
// Props
// ==========================================================================

interface RedFlagsTabProps {
  activeTab: string;
  onClauseClick: (clauseRef: string, page: number, section: string, snippet?: string) => void;
}

// ==========================================================================
// Component
// ==========================================================================

const RedFlagsTab = ({ activeTab, onClauseClick }: RedFlagsTabProps) => {
  const { documentId } = useDocument();

  const { data, isLoading } = useQuery({
    queryKey: ["red-flags", documentId],
    queryFn: () => getRedFlags(documentId!),
    enabled: !!documentId && activeTab === "redflags",
    refetchInterval: (query) =>
      query.state.data?.status === "processing" ? 3000 : false,
  });

  // ── Loading / Processing ──────────────────────────────────────────────
  if (isLoading || !data || data.status === "processing") {
    return <RedFlagsSkeleton />;
  }

  // ── Failed ────────────────────────────────────────────────────────────
  if (data.status === "failed") {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-destructive">Red Flags Unavailable</p>
            <p className="text-xs text-destructive/80 mt-1">
              {data.error || "Could not detect red flags."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Complete ──────────────────────────────────────────────────────────
  const flags = [...(data.data ?? [])].sort(
    (a, b) => severityConfig[a.severity].order - severityConfig[b.severity].order,
  );

  if (flags.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-muted-foreground">No red flags detected in this document.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {flags.map((flag: RedFlag) => {
        const config = severityConfig[flag.severity];
        const Icon = config.icon;
        return (
          <button
            key={flag.id}
            onClick={() => onClauseClick(flag.location.section, flag.location.page, flag.location.section, flag.description)}
            className={`w-full text-left rounded-lg border p-3.5 transition-all hover:shadow-md ${config.className}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2.5">
                <Icon className="w-4 h-4 mt-0.5 shrink-0" />
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold">{flag.title}</span>
                  </div>
                  <p className="text-xs opacity-80 leading-relaxed">{flag.description}</p>
                  {flag.recommendation && (
                    <p className="text-xs opacity-70 mt-1.5 italic">💡 {flag.recommendation}</p>
                  )}
                  <p className="text-[11px] opacity-60 mt-1.5 font-medium">
                    {flag.location.section} · Page {flag.location.page}
                  </p>
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

// ==========================================================================
// Skeleton
// ==========================================================================

function RedFlagsSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border p-3.5 space-y-2">
          <div className="flex items-center gap-2">
            <Skeleton className="h-4 w-4 rounded" />
            <Skeleton className="h-4 w-40" />
          </div>
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-3/4" />
          <Skeleton className="h-3 w-32" />
        </div>
      ))}
    </div>
  );
}

export default RedFlagsTab;
