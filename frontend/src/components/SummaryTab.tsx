import { useQuery } from "@tanstack/react-query";
import { useDocument } from "@/context/DocumentContext";
import { getSummary } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { DollarSign, Percent, Calendar, TrendingUp, CreditCard, AlertCircle, CheckCircle, AlertTriangle } from "lucide-react";
import type { Highlight } from "@/lib/types";

// ==========================================================================
// Component
// ==========================================================================

const SummaryTab = () => {
  const { documentId } = useDocument();

  const { data, isLoading } = useQuery({
    queryKey: ["summary", documentId],
    queryFn: () => getSummary(documentId!),
    enabled: !!documentId,
    refetchInterval: (query) =>
      query.state.data?.status === "processing" ? 3000 : false,
  });

  // ── Loading / Processing ──────────────────────────────────────────────
  if (isLoading || !data || data.status === "processing") {
    return <SummarySkeleton />;
  }

  // ── Failed ────────────────────────────────────────────────────────────
  if (data.status === "failed") {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-destructive">Summary Unavailable</p>
            <p className="text-xs text-destructive/80 mt-1">
              {data.error || "Could not generate summary for this document."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Complete ──────────────────────────────────────────────────────────
  const summary = data.data!;
  const kn = summary.key_numbers;

  const items = [
    { icon: DollarSign, label: "Loan Amount", value: kn.total_loan != null ? `$${kn.total_loan.toLocaleString()}` : "—" },
    { icon: TrendingUp, label: "Interest Rate", value: kn.interest_rate != null ? `${kn.interest_rate}%` : "—" },
    { icon: Calendar, label: "Term", value: kn.term_months != null ? `${kn.term_months} months` : "—" },
    { icon: CreditCard, label: "Monthly Payment", value: kn.monthly_payment != null ? `$${kn.monthly_payment.toLocaleString()}` : "—" },
    { icon: Percent, label: "Total Interest", value: kn.total_interest != null ? `$${kn.total_interest.toLocaleString()}` : "—" },
    { icon: DollarSign, label: "Document Type", value: summary.document_type },
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        {items.map((item) => (
          <div key={item.label} className="bg-muted/50 rounded-lg p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <item.icon className="w-3.5 h-3.5 text-accent" />
              <span className="text-[11px] text-muted-foreground font-medium">{item.label}</span>
            </div>
            <p className="text-sm font-semibold text-foreground">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Highlights */}
      {summary.highlights.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Key Highlights
          </h4>
          {summary.highlights.map((h: Highlight, i: number) => (
            <div
              key={i}
              className={`flex items-start gap-2 text-sm rounded-lg p-2.5 ${h.type === "positive"
                  ? "bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]"
                  : h.type === "negative"
                    ? "bg-destructive/10 text-destructive"
                    : "bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]"
                }`}
            >
              {h.type === "positive" ? (
                <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
              ) : h.type === "negative" ? (
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              )}
              <span>{h.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* Overview */}
      {summary.overview && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Overview
          </h4>
          <p className="text-sm text-foreground/80 leading-relaxed">{summary.overview}</p>
        </div>
      )}
    </div>
  );
};

// ==========================================================================
// Skeleton
// ==========================================================================

function SummarySkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-muted/50 rounded-lg p-3 space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-5 w-24" />
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-16 w-full" />
      </div>
    </div>
  );
}

export default SummaryTab;
