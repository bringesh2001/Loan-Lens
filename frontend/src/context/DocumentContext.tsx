import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { CurrencyInfo } from "@/lib/currency";

// ==========================================================================
// Highlight Target
// ==========================================================================

export interface HighlightTarget {
    page: number;
    section: string;
    snippet?: string; // exact text to highlight in the PDF text layer
}

// ==========================================================================
// Types
// ==========================================================================

interface DocumentContextValue {
    documentId: string | null;
    filePreviewUrl: string | null;
    conversationId: string | null;
    highlightTarget: HighlightTarget | null;
    currencyInfo: CurrencyInfo | null;
    setDocumentId: (id: string | null) => void;
    setFilePreviewUrl: (url: string | null) => void;
    setConversationId: (id: string | null) => void;
    setHighlightTarget: (target: HighlightTarget | null) => void;
    setCurrencyInfo: (info: CurrencyInfo | null) => void;
    clearDocument: () => void;
}

// ==========================================================================
// Context
// ==========================================================================

const DocumentContext = createContext<DocumentContextValue | null>(null);

// ==========================================================================
// Provider
// ==========================================================================

export function DocumentProvider({ children }: { children: ReactNode }) {
    const [documentId, setDocumentId] = useState<string | null>(null);
    const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [highlightTarget, setHighlightTarget] = useState<HighlightTarget | null>(null);
    const [currencyInfo, setCurrencyInfo] = useState<CurrencyInfo | null>(null);

    const clearDocument = useCallback(() => {
        if (filePreviewUrl) {
            URL.revokeObjectURL(filePreviewUrl);
        }
        setDocumentId(null);
        setFilePreviewUrl(null);
        setConversationId(null);
        setHighlightTarget(null);
        setCurrencyInfo(null);
    }, [filePreviewUrl]);

    return (
        <DocumentContext.Provider
            value={{
                documentId,
                filePreviewUrl,
                conversationId,
                highlightTarget,
                currencyInfo,
                setDocumentId,
                setFilePreviewUrl,
                setConversationId,
                setHighlightTarget,
                setCurrencyInfo,
                clearDocument,
            }}
        >
            {children}
        </DocumentContext.Provider>
    );
}

// ==========================================================================
// Hook
// ==========================================================================

export function useDocument(): DocumentContextValue {
    const context = useContext(DocumentContext);
    if (!context) {
        throw new Error("useDocument must be used within a DocumentProvider");
    }
    return context;
}
