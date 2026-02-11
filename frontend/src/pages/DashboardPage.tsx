import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useDocument } from "@/context/DocumentContext";
import { getSummary, DocumentExpiredError } from "@/lib/api";
import Dashboard from "@/components/Dashboard";
import { Button } from "@/components/ui/button";
import { FileX, Upload } from "lucide-react";

const DashboardPage = () => {
    const { documentId } = useParams<{ documentId: string }>();
    const navigate = useNavigate();
    const { setDocumentId, clearDocument } = useDocument();

    // Sync route param into context
    useEffect(() => {
        if (documentId) {
            setDocumentId(documentId);
        }
    }, [documentId, setDocumentId]);

    // Probe the backend to detect if document still exists
    const { error } = useQuery({
        queryKey: ["document-probe", documentId],
        queryFn: () => getSummary(documentId!),
        enabled: !!documentId,
        retry: false,
        refetchOnWindowFocus: false,
        // Only probe once — summary tab handles ongoing polling
        staleTime: Infinity,
    });

    // Centralized document-expired handling
    useEffect(() => {
        if (error instanceof DocumentExpiredError) {
            clearDocument();
        }
    }, [error, clearDocument]);

    if (!documentId) {
        return <DocumentGonePage onUpload={() => navigate("/")} />;
    }

    if (error instanceof DocumentExpiredError) {
        return <DocumentGonePage onUpload={() => navigate("/")} />;
    }

    return <Dashboard />;
};

// ==========================================================================
// Document Gone Full-Page
// ==========================================================================

function DocumentGonePage({ onUpload }: { onUpload: () => void }) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="max-w-md mx-auto text-center px-6">
                <div className="w-16 h-16 rounded-2xl bg-destructive/10 flex items-center justify-center mx-auto mb-6">
                    <FileX className="w-8 h-8 text-destructive" />
                </div>
                <h1 className="text-2xl font-bold text-foreground mb-2">
                    Document Not Found
                </h1>
                <p className="text-muted-foreground mb-6 leading-relaxed">
                    This document is no longer available. The server may have restarted,
                    clearing all in-memory data. Please upload your document again.
                </p>
                <Button onClick={onUpload} size="lg" className="gap-2">
                    <Upload className="w-4 h-4" />
                    Upload Again
                </Button>
            </div>
        </div>
    );
}

export default DashboardPage;
