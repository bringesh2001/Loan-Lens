import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Eye } from "lucide-react";
import PdfViewer from "@/components/PdfViewer";
import RiskScore from "@/components/RiskScore";
import SummaryTab from "@/components/SummaryTab";
import RedFlagsTab from "@/components/RedFlagsTab";
import HiddenClausesTab from "@/components/HiddenClausesTab";
import ChatTab from "@/components/ChatTab";
import { mockAnalysis } from "@/lib/mock-data";

interface DashboardProps {
  fileName: string;
  onBack: () => void;
}

const Dashboard = ({ fileName, onBack }: DashboardProps) => {
  const [highlightedClause, setHighlightedClause] = useState<string | null>(null);
  const [highlightedPage, setHighlightedPage] = useState<number | null>(null);
  const [simpleMode, setSimpleMode] = useState(true);
  const analysis = mockAnalysis;

  const handleClauseClick = (clauseRef: string, page: number) => {
    setHighlightedClause(clauseRef);
    setHighlightedPage(page);
  };

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <div className="h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            ← Back
          </button>
          <div className="h-5 w-px bg-border" />
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-accent" />
            <span className="text-sm font-semibold text-foreground">Loan Lens</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">Simple</span>
          <Switch checked={!simpleMode} onCheckedChange={(v) => setSimpleMode(!v)} />
          <span className="text-xs text-muted-foreground">Legal</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* PDF Viewer */}
        <div className="lg:w-[62%] w-full h-[50vh] lg:h-full border-b lg:border-b-0 lg:border-r border-border">
          <PdfViewer
            fileName={fileName}
            highlightedClause={highlightedClause}
            highlightedPage={highlightedPage}
          />
        </div>

        {/* Insights Panel */}
        <div className="lg:w-[38%] w-full flex-1 lg:h-full overflow-auto bg-card">
          <div className="p-5">
            {/* Risk Score */}
            <div className="flex items-center justify-center mb-5 pb-5 border-b border-border">
              <RiskScore score={analysis.riskScore} />
            </div>

            {/* Tabs */}
            <Tabs defaultValue="summary" className="w-full">
              <TabsList className="w-full grid grid-cols-4 mb-4">
                <TabsTrigger value="summary" className="text-xs">Summary</TabsTrigger>
                <TabsTrigger value="redflags" className="text-xs">
                  Red Flags
                  <span className="ml-1 bg-destructive/20 text-destructive text-[10px] rounded-full px-1.5">
                    {analysis.redFlags.filter(f => f.severity === "high").length}
                  </span>
                </TabsTrigger>
                <TabsTrigger value="hidden" className="text-xs">Hidden</TabsTrigger>
                <TabsTrigger value="chat" className="text-xs">Chat</TabsTrigger>
              </TabsList>

              <TabsContent value="summary">
                <SummaryTab summary={analysis.summary} simpleMode={simpleMode} />
              </TabsContent>
              <TabsContent value="redflags">
                <RedFlagsTab redFlags={analysis.redFlags} onClauseClick={handleClauseClick} />
              </TabsContent>
              <TabsContent value="hidden">
                <HiddenClausesTab clauses={analysis.hiddenClauses} onClauseClick={handleClauseClick} />
              </TabsContent>
              <TabsContent value="chat">
                <ChatTab onClauseClick={handleClauseClick} />
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
