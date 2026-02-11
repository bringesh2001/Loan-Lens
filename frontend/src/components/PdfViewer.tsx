import { useRef, useEffect, useState } from "react";
import { useDocument } from "@/context/DocumentContext";
import { FileText, Upload, Navigation } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

// ==========================================================================
// Component
// ==========================================================================

const PdfViewer = () => {
  const { filePreviewUrl, highlightTarget } = useDocument();
  const navigate = useNavigate();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [navIndicator, setNavIndicator] = useState<string | null>(null);

  // ── React to highlight target changes ──────────────────────────────────
  useEffect(() => {
    if (!highlightTarget || !filePreviewUrl || !iframeRef.current) return;

    const { page, section } = highlightTarget;
    const iframe = iframeRef.current;

    // Use contentWindow.location.hash for same-document navigation
    // This avoids reloading the entire blob URL and lets the browser's
    // built-in PDF viewer handle the page jump natively.
    try {
      if (iframe.contentWindow) {
        iframe.contentWindow.location.hash = `page=${page}`;
      }
    } catch {
      // Fallback: set src with page fragment (will reload the PDF)
      iframe.src = `${filePreviewUrl}#page=${page}`;
    }

    // Show navigation indicator
    setNavIndicator(`Navigated to Page ${page} · ${section}`);

    // Auto-dismiss indicator after 4 seconds
    const timer = setTimeout(() => setNavIndicator(null), 4000);
    return () => clearTimeout(timer);
  }, [highlightTarget, filePreviewUrl]);

  // ── No Preview URL (page was refreshed) ───────────────────────────────
  if (!filePreviewUrl) {
    return (
      <div className="flex flex-col h-full bg-muted/30 items-center justify-center p-8">
        <div className="max-w-sm text-center">
          <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">
            PDF Preview Unavailable
          </h3>
          <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
            PDF preview is unavailable due to a page refresh. Your analysis is
            still available, but please re-upload to enable the document viewer
            and clause highlighting.
          </p>
          <Button variant="outline" onClick={() => navigate("/")} className="gap-2">
            <Upload className="w-4 h-4" />
            Re-upload Document
          </Button>
        </div>
      </div>
    );
  }

  // ── PDF Preview via iframe ────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full bg-muted/30 relative">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <FileText className="w-4 h-4" />
          <span className="font-medium">Document Preview</span>
        </div>
      </div>

      {/* Navigation Indicator */}
      {navIndicator && (
        <div
          className="absolute top-14 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 px-4 py-2.5 rounded-lg bg-accent text-accent-foreground text-sm font-medium shadow-lg animate-in fade-in slide-in-from-top-2 duration-300"
        >
          <Navigation className="w-4 h-4" />
          {navIndicator}
        </div>
      )}

      {/* PDF iframe */}
      <div className="flex-1">
        <iframe
          ref={iframeRef}
          src={filePreviewUrl}
          title="PDF Preview"
          className="w-full h-full border-0"
        />
      </div>
    </div>
  );
};

export default PdfViewer;
