import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDocument } from "@/context/DocumentContext";
import { getFinancialTerms } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, BookOpen, ChevronDown, AlertCircle } from "lucide-react";
import type { FinancialTerm } from "@/lib/types";

// ==========================================================================
// Props
// ==========================================================================

interface FinancialTermsTabProps {
    activeTab: string;
}

// ==========================================================================
// Component
// ==========================================================================

const FinancialTermsTab = ({ activeTab }: FinancialTermsTabProps) => {
    const { documentId } = useDocument();
    const [searchQuery, setSearchQuery] = useState("");
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ["financial-terms", documentId],
        queryFn: () => getFinancialTerms(documentId!),
        enabled: !!documentId && activeTab === "terms",
        refetchInterval: (query) =>
            query.state.data?.status === "processing" ? 3000 : false,
    });

    // ── Loading / Processing ──────────────────────────────────────────────
    if (isLoading || !data || data.status === "processing") {
        return <FinancialTermsSkeleton />;
    }

    // ── Failed ────────────────────────────────────────────────────────────
    if (data.status === "failed") {
        return (
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
                <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
                    <div>
                        <p className="text-sm font-semibold text-destructive">Financial Terms Unavailable</p>
                        <p className="text-xs text-destructive/80 mt-1">
                            {data.error || "Could not extract financial terms."}
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    // ── Complete ──────────────────────────────────────────────────────────
    const allTerms = data.terms ?? [];
    const terms = searchQuery
        ? allTerms.filter(
            (t) =>
                t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                t.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                t.short_description.toLowerCase().includes(searchQuery.toLowerCase()),
        )
        : allTerms;

    if (allTerms.length === 0) {
        return (
            <div className="text-center py-8">
                <p className="text-sm text-muted-foreground">No financial terms detected in this document.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Search */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                    type="text"
                    placeholder="Search for a term..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/30 transition-shadow"
                />
            </div>

            {/* Count */}
            <p className="text-xs font-semibold text-muted-foreground tracking-wide flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                FOUND {terms.length} FINANCIAL TERM{terms.length !== 1 ? "S" : ""}
            </p>

            {/* Term List */}
            {terms.length === 0 ? (
                <div className="text-center py-6">
                    <p className="text-sm text-muted-foreground">
                        No terms match "{searchQuery}"
                    </p>
                </div>
            ) : (
                <div className="space-y-2.5">
                    {terms.map((term: FinancialTerm) => {
                        const isExpanded = expandedId === term.id;
                        return (
                            <div key={term.id} className="rounded-lg border border-border transition-all hover:shadow-md">
                                {/* Collapsed Header */}
                                <button
                                    onClick={() => setExpandedId(isExpanded ? null : term.id)}
                                    className="w-full text-left p-3.5 flex items-center justify-between gap-2"
                                >
                                    <div className="min-w-0">
                                        <p className="text-sm font-semibold text-foreground">
                                            {term.full_name ? `${term.name} (${term.full_name})` : term.name}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-0.5 truncate">
                                            {term.short_description}
                                        </p>
                                    </div>
                                    <ChevronDown
                                        className={`w-4 h-4 text-muted-foreground shrink-0 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                                    />
                                </button>

                                {/* Expanded Details */}
                                {isExpanded && (
                                    <div className="px-3.5 pb-4 pt-0 space-y-3 border-t border-border/50">
                                        {/* Icon + Full Name */}
                                        <div className="flex items-center gap-2.5 pt-3">
                                            <div className="w-9 h-9 rounded-md bg-accent/10 flex items-center justify-center shrink-0">
                                                <BookOpen className="w-4.5 h-4.5 text-accent" />
                                            </div>
                                            <p className="text-sm font-bold text-foreground">
                                                {term.full_name ? `${term.name} (${term.full_name})` : term.name}
                                            </p>
                                        </div>

                                        {/* Definition */}
                                        <p className="text-sm text-foreground/85 leading-relaxed">
                                            {term.definition}
                                        </p>

                                        {/* Example Box */}
                                        {term.example && (
                                            <div className="rounded-lg border-l-4 border-[hsl(var(--warning))] bg-[hsl(var(--warning))]/5 p-3">
                                                <p className="text-xs font-semibold text-[hsl(var(--warning))] flex items-center gap-1.5">
                                                    {term.example.icon} {term.example.title}:
                                                </p>
                                                <p className="text-xs text-foreground/80 mt-1 leading-relaxed italic">
                                                    {term.example.text}
                                                </p>
                                            </div>
                                        )}

                                        {/* Your Value + Location */}
                                        <div className="flex items-center justify-between text-[11px] text-muted-foreground/60 font-medium">
                                            {term.your_value && (
                                                <span>Your value: <span className="text-foreground font-semibold">{term.your_value}</span></span>
                                            )}
                                            <span>
                                                {term.location.section} · Page {term.location.page}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

// ==========================================================================
// Skeleton
// ==========================================================================

function FinancialTermsSkeleton() {
    return (
        <div className="space-y-4">
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-4 w-40" />
            <div className="space-y-2.5">
                {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="rounded-lg border border-border p-3.5 space-y-2">
                        <Skeleton className="h-4 w-48" />
                        <Skeleton className="h-3 w-full" />
                    </div>
                ))}
            </div>
        </div>
    );
}

export default FinancialTermsTab;
