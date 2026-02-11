export interface LoanAnalysis {
  summary: {
    loanAmount: string;
    interestType: string;
    interestRate: string;
    tenure: string;
    emi: string;
    totalPayable: string;
    prepaymentTerms: string;
    plainExplanation: string;
  };
  riskScore: number;
  redFlags: {
    id: string;
    severity: "high" | "medium" | "low";
    title: string;
    explanation: string;
    clauseRef: string;
    page: number;
  }[];
  hiddenClauses: {
    id: string;
    category: string;
    title: string;
    detail: string;
    clauseRef: string;
    page: number;
  }[];
}

export const mockAnalysis: LoanAnalysis = {
  summary: {
    loanAmount: "₹45,00,000",
    interestType: "Floating Rate",
    interestRate: "8.75% p.a.",
    tenure: "20 years (240 months)",
    emi: "₹39,782",
    totalPayable: "₹95,47,680",
    prepaymentTerms: "2% penalty on outstanding principal for first 3 years, nil thereafter",
    plainExplanation:
      "You're borrowing ₹45 lakhs at a floating interest rate of 8.75%. This means your rate can change based on the RBI repo rate. Over 20 years, you'll pay back nearly ₹95.5 lakhs — more than double what you borrowed. The monthly EMI is about ₹39,782. If you want to repay early in the first 3 years, you'll pay a 2% penalty on the remaining amount.",
  },
  riskScore: 62,
  redFlags: [
    {
      id: "rf1",
      severity: "high",
      title: "Unilateral Interest Rate Revision",
      explanation:
        "The lender reserves the right to revise the interest rate at any time without prior written notice, beyond the standard repo rate linkage.",
      clauseRef: "Section 4.2(b)",
      page: 3,
    },
    {
      id: "rf2",
      severity: "high",
      title: "Cross-Default Clause",
      explanation:
        "Default on any other loan with any financial institution can trigger default on this loan, enabling immediate full repayment demand.",
      clauseRef: "Section 12.1",
      page: 8,
    },
    {
      id: "rf3",
      severity: "medium",
      title: "Processing Fee Non-Refundable",
      explanation:
        "The processing fee of ₹11,250 is non-refundable even if the loan is not disbursed or cancelled by the borrower.",
      clauseRef: "Section 2.4",
      page: 2,
    },
    {
      id: "rf4",
      severity: "medium",
      title: "Insurance Mandate",
      explanation:
        "Borrower is required to maintain life insurance with the lender as nominee for the entire tenure. Failure to do so can trigger default.",
      clauseRef: "Section 7.3",
      page: 5,
    },
    {
      id: "rf5",
      severity: "low",
      title: "Communication Address Changes",
      explanation:
        "Borrower must notify address changes within 7 days. Communications sent to last known address are deemed received.",
      clauseRef: "Section 15.2",
      page: 10,
    },
  ],
  hiddenClauses: [
    {
      id: "hc1",
      category: "Rate Adjustment",
      title: "Variable Rate Reset Frequency",
      detail:
        "Interest rate is reset quarterly, not annually. This means you'll see rate changes every 3 months, which can cause frequent EMI fluctuations.",
      clauseRef: "Section 4.3",
      page: 3,
    },
    {
      id: "hc2",
      category: "Compounding",
      title: "Monthly Compounding on Overdue",
      detail:
        "Overdue amounts are subject to monthly compounding at the penal rate of 2% above the applicable interest rate.",
      clauseRef: "Section 6.1(a)",
      page: 4,
    },
    {
      id: "hc3",
      category: "Auto-Debit",
      title: "Standing Instruction Irrevocable",
      detail:
        "The auto-debit mandate (ECS/NACH) provided is irrevocable for the entire loan tenure. Borrower cannot cancel without lender's written consent.",
      clauseRef: "Section 8.2",
      page: 6,
    },
    {
      id: "hc4",
      category: "Late Fees",
      title: "Cascading Late Payment Charges",
      detail:
        "Late payment charges of ₹500 + 18% GST per instance, plus penal interest of 2% p.a. on the overdue EMI amount from due date.",
      clauseRef: "Section 6.2",
      page: 4,
    },
    {
      id: "hc5",
      category: "Jurisdiction",
      title: "Exclusive Jurisdiction Clause",
      detail:
        "All disputes are subject to exclusive jurisdiction of courts in Mumbai only, regardless of borrower's residence.",
      clauseRef: "Section 18.1",
      page: 12,
    },
  ],
};

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  clauseRef?: string;
  page?: number;
}
