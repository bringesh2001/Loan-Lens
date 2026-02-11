import { useQuery } from "@tanstack/react-query";
import { useDocument } from "@/context/DocumentContext";
import { getHiddenClauses } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronRight, Scale, AlertCircle } from "lucide-react";
import type { HiddenClause } from "@/lib/types";

// ==========================================================================
// Impact styling
// ==========================================================================

const impactStyles = {
  high: "border-destructive/20 bg-destructive/5",
  medium: "border-[hsl(var(--warning))]/20 bg-[hsl(var(--warning))]/5",
  low: "border-border bg-card",
};

// ==========================================================================
// Props
// ==========================================================================

interface HiddenClausesTabProps {
  activeTab: string;
  onClauseClick: (clauseRef: string, page: number, section: string, snippet?: string) => void;
}

// ==========================================================================
// Component
// ==========================================================================

const HiddenClausesTab = ({ activeTab, onClauseClick }: HiddenClausesTabProps) => {
  const { documentId } = useDocument();

  const { data, isLoading } = useQuery({
    queryKey: ["hidden-clauses", documentId],
    queryFn: () => getHiddenClauses(documentId!),
    enabled: !!documentId && activeTab === "hidden",
    refetchInterval: (query) =>
      query.state.data?.status === "processing" ? 3000 : false,
  });

  // ── Loading / Processing ──────────────────────────────────────────────
  if (isLoading || !data || data.status === "processing") {
    return <HiddenClausesSkeleton />;
  }

  // ── Failed ────────────────────────────────────────────────────────────
  if (data.status === "failed") {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-destructive">Hidden Clauses Unavailable</p>
            <p className="text-xs text-destructive/80 mt-1">
              {data.error || "Could not detect hidden clauses."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Complete ──────────────────────────────────────────────────────────
  const clauses = data.data ?? [];

  if (clauses.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-muted-foreground">No hidden clauses detected in this document.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {clauses.map((clause: HiddenClause) => (
        <button
          key={clause.id}
          onClick={() => onClauseClick(clause.location.section, clause.location.page, clause.location.section, clause.original_text)}
          className={`w-full text-left rounded-lg border p-3.5 transition-all hover:shadow-md group ${impactStyles[clause.impact] ?? impactStyles.low
            }`}
        >
          <div className="flex items-start gap-2.5">
            <div className="w-8 h-8 rounded-md bg-accent/10 flex items-center justify-center shrink-0 group-hover:bg-accent/20 transition-colors">
              <Scale className="w-4 h-4 text-accent" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] text-accent font-medium">{clause.category}</span>
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-sm font-semibold text-foreground mt-0.5">{clause.title}</p>
              <p className="text-xs text-muted-foreground leading-relaxed mt-1">{clause.plain_english}</p>
              <p className="text-[11px] text-muted-foreground/60 mt-1.5 font-medium">
                {clause.location.section} · Page {clause.location.page} · Impact: {clause.impact}
              </p>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
};

// ==========================================================================
// Skeleton
// ==========================================================================

function HiddenClausesSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border p-3.5">
          <div className="flex items-start gap-2.5">
            <Skeleton className="w-8 h-8 rounded-md" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default HiddenClausesTab;
