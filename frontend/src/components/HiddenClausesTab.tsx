import { LoanAnalysis } from "@/lib/mock-data";
import { ChevronRight, Scale, Repeat, Banknote, CreditCard, MapPin } from "lucide-react";

interface HiddenClausesTabProps {
  clauses: LoanAnalysis["hiddenClauses"];
  onClauseClick: (clauseRef: string, page: number) => void;
}

const categoryIcons: Record<string, typeof Scale> = {
  "Rate Adjustment": Repeat,
  "Compounding": Banknote,
  "Auto-Debit": CreditCard,
  "Late Fees": Banknote,
  "Jurisdiction": MapPin,
};

const HiddenClausesTab = ({ clauses, onClauseClick }: HiddenClausesTabProps) => {
  return (
    <div className="space-y-3">
      {clauses.map((clause) => {
        const Icon = categoryIcons[clause.category] || Scale;
        return (
          <button
            key={clause.id}
            onClick={() => onClauseClick(clause.clauseRef, clause.page)}
            className="w-full text-left rounded-lg border border-border bg-card p-3.5 transition-all hover:shadow-md hover:border-accent/30 group"
          >
            <div className="flex items-start gap-2.5">
              <div className="w-8 h-8 rounded-md bg-accent/10 flex items-center justify-center shrink-0 group-hover:bg-accent/20 transition-colors">
                <Icon className="w-4 h-4 text-accent" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] text-accent font-medium">{clause.category}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <p className="text-sm font-semibold text-foreground mt-0.5">{clause.title}</p>
                <p className="text-xs text-muted-foreground leading-relaxed mt-1">{clause.detail}</p>
                <p className="text-[11px] text-muted-foreground/60 mt-1.5 font-medium">{clause.clauseRef} · Page {clause.page}</p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default HiddenClausesTab;
