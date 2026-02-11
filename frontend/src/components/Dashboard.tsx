import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Eye } from "lucide-react";
import { useDocument } from "@/context/DocumentContext";
import PdfViewer from "@/components/PdfViewer";
import SummaryTab from "@/components/SummaryTab";
import RedFlagsTab from "@/components/RedFlagsTab";
import HiddenClausesTab from "@/components/HiddenClausesTab";
import FinancialTermsTab from "@/components/FinancialTermsTab";
import ChatTab from "@/components/ChatTab";

// TODO: Implement risk score when backend supports endpoint

// ==========================================================================
// Component
// ==========================================================================

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState("summary");
  const navigate = useNavigate();
  const { documentId, setHighlightTarget } = useDocument();

  const handleClauseClick = (_clauseRef: string, page: number, section: string) => {
    setHighlightTarget({ page, section, timestamp: Date.now() });
  };

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <div className="h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/")}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            ← Back
          </button>
          <div className="h-5 w-px bg-border" />
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-accent" />
            <span className="text-sm font-semibold text-foreground">Loan Lens</span>
          </div>
        </div>
        <div className="text-xs text-muted-foreground font-mono">
          {documentId?.slice(0, 16)}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* PDF Viewer */}
        <div className="lg:w-[62%] w-full h-[50vh] lg:h-full border-b lg:border-b-0 lg:border-r border-border">
          <PdfViewer />
        </div>

        {/* Insights Panel */}
        <div className="lg:w-[38%] w-full flex-1 lg:h-full overflow-auto bg-card">
          <div className="p-5">
            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="w-full grid grid-cols-5 mb-4">
                <TabsTrigger value="summary" className="text-xs">Summary</TabsTrigger>
                <TabsTrigger value="redflags" className="text-xs">Red Flags</TabsTrigger>
                <TabsTrigger value="hidden" className="text-xs">Hidden</TabsTrigger>
                <TabsTrigger value="terms" className="text-xs">Terms</TabsTrigger>
                <TabsTrigger value="chat" className="text-xs">Chat</TabsTrigger>
              </TabsList>

              <TabsContent value="summary">
                <SummaryTab />
              </TabsContent>
              <TabsContent value="redflags">
                <RedFlagsTab activeTab={activeTab} onClauseClick={handleClauseClick} />
              </TabsContent>
              <TabsContent value="hidden">
                <HiddenClausesTab activeTab={activeTab} onClauseClick={handleClauseClick} />
              </TabsContent>
              <TabsContent value="terms">
                <FinancialTermsTab activeTab={activeTab} />
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
