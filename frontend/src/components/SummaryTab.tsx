import { LoanAnalysis } from "@/lib/mock-data";
import { DollarSign, Percent, Calendar, TrendingUp, FileText, CreditCard } from "lucide-react";

interface SummaryTabProps {
  summary: LoanAnalysis["summary"];
  simpleMode: boolean;
}

const SummaryTab = ({ summary, simpleMode }: SummaryTabProps) => {
  const items = [
    { icon: DollarSign, label: "Loan Amount", value: summary.loanAmount },
    { icon: TrendingUp, label: "Interest Type", value: summary.interestType },
    { icon: Percent, label: "Interest Rate", value: summary.interestRate },
    { icon: Calendar, label: "Tenure", value: summary.tenure },
    { icon: CreditCard, label: "Monthly EMI", value: summary.emi },
    { icon: DollarSign, label: "Total Payable", value: summary.totalPayable },
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

      <div className="bg-muted/50 rounded-lg p-3">
        <div className="flex items-center gap-1.5 mb-1">
          <FileText className="w-3.5 h-3.5 text-accent" />
          <span className="text-[11px] text-muted-foreground font-medium">Prepayment Terms</span>
        </div>
        <p className="text-sm text-foreground">{summary.prepaymentTerms}</p>
      </div>

      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          {simpleMode ? "In Plain English" : "Legal Summary"}
        </h4>
        <p className="text-sm text-foreground/80 leading-relaxed">
          {simpleMode
            ? summary.plainExplanation
            : "The Borrower is bound by a floating rate home loan facility of INR 45,00,000 at 8.75% p.a. linked to EBLR, with 240 equated monthly installments of INR 39,782. Prepayment carries a 2% foreclosure charge on outstanding principal for the initial 36-month period, with nil charges thereafter as per RBI guidelines."}
        </p>
      </div>
    </div>
  );
};

export default SummaryTab;
