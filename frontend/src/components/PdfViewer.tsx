import { FileText, ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

interface PdfViewerProps {
  fileName: string;
  highlightedClause?: string | null;
  highlightedPage?: number | null;
}

const PdfViewer = ({ fileName, highlightedClause, highlightedPage }: PdfViewerProps) => {
  const [zoom, setZoom] = useState(100);
  const [page, setPage] = useState(1);
  const totalPages = 14;

  const currentPage = highlightedPage ?? page;

  return (
    <div className="flex flex-col h-full bg-muted/30">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <FileText className="w-4 h-4" />
          <span className="truncate max-w-[200px] font-medium">{fileName}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setZoom(z => Math.max(50, z - 25))}>
            <ZoomOut className="w-4 h-4" />
          </Button>
          <span className="text-xs text-muted-foreground w-12 text-center">{zoom}%</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setZoom(z => Math.min(200, z + 25))}>
            <ZoomIn className="w-4 h-4" />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setPage(p => Math.max(1, p - 1))}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-xs text-muted-foreground">
            {currentPage} / {totalPages}
          </span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* PDF Content (simulated) */}
      <div className="flex-1 overflow-auto p-6">
        <div
          className="mx-auto bg-card rounded-lg shadow-lg border border-border p-8 max-w-2xl"
          style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
        >
          <div className="space-y-4 text-sm text-foreground/80 leading-relaxed">
            <div className="text-center mb-8">
              <h2 className="text-lg font-bold text-foreground">HOME LOAN AGREEMENT</h2>
              <p className="text-xs text-muted-foreground mt-1">Agreement No: HL/2024/045789</p>
            </div>

            <p>
              This Home Loan Agreement ("Agreement") is entered into on this 15th day of January, 2024,
              by and between the Lender and the Borrower(s) whose details are set forth herein.
            </p>

            {highlightedClause && (
              <div className="relative">
                <div className="absolute -left-4 top-0 bottom-0 w-1 bg-accent rounded-full" />
                <div className="bg-accent/10 border border-accent/30 rounded-lg p-4 transition-all duration-500">
                  <p className="text-xs font-semibold text-accent mb-1">{highlightedClause}</p>
                  <p className="text-sm">
                    The Lender reserves the right to modify, amend, or revise the applicable interest rate
                    at its sole discretion based on prevailing market conditions, changes in regulatory
                    benchmarks, or internal policy revisions. Such modifications may be effected without
                    prior written notice to the Borrower(s).
                  </p>
                </div>
              </div>
            )}

            <p>
              <strong>Section 1: Loan Details</strong>
              <br />
              1.1 The Lender agrees to extend a home loan facility of INR 45,00,000 (Indian Rupees
              Forty-Five Lakhs Only) to the Borrower, subject to the terms and conditions detailed herein.
            </p>

            <p>
              1.2 The loan shall be disbursed in tranches or as a lump sum at the discretion of the Lender,
              upon completion of all documentation and verification requirements.
            </p>

            <p>
              <strong>Section 2: Interest and Repayment</strong>
              <br />
              2.1 The applicable rate of interest shall be 8.75% per annum on a floating rate basis,
              linked to the Lender's benchmark lending rate (RLLR/EBLR).
            </p>

            <p>
              2.2 The Equated Monthly Installment (EMI) shall be INR 39,782 payable on the 5th of every
              calendar month through auto-debit from the designated bank account.
            </p>

            <p>
              2.3 The loan tenure shall be 240 months (20 years) from the date of first disbursement.
            </p>

            <p className="text-muted-foreground text-xs italic mt-8 text-center">
              — Simulated PDF preview • Page {currentPage} of {totalPages} —
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PdfViewer;
