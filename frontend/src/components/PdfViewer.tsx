import { useState, useRef, useEffect, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { useDocument } from "@/context/DocumentContext";
import { FileText, Upload, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

// ==========================================================================
// PDF.js Worker Configuration
// ==========================================================================

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "react-pdf/node_modules/pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

// ==========================================================================
// Component
// ==========================================================================

const PdfViewer = () => {
  const { filePreviewUrl, highlightTarget } = useDocument();
  const navigate = useNavigate();

  const [numPages, setNumPages] = useState<number>(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const containerRef = useRef<HTMLDivElement>(null);

  // ── Track container width for responsive page sizing ──────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // ── Jump to page ──────────────────────────────────────────────────────
  const jumpToPage = useCallback((page: number) => {
    pageRefs.current[page]?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, []);

  // ── Highlight clause (jump + yellow flash) ────────────────────────────
  const highlightClause = useCallback(
    (page: number) => {
      jumpToPage(page);
      setHighlightPage(page);
    },
    [jumpToPage],
  );

  // ── Auto-clear highlight after 2.5s ───────────────────────────────────
  useEffect(() => {
    if (highlightPage === null) return;
    const timer = setTimeout(() => setHighlightPage(null), 2500);
    return () => clearTimeout(timer);
  }, [highlightPage]);

  // ── React to highlight target from context ────────────────────────────
  useEffect(() => {
    if (!highlightTarget) return;
    highlightClause(highlightTarget.page);
  }, [highlightTarget, highlightClause]);

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

  // ── PDF Render ────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full bg-muted/30">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card shrink-0">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <FileText className="w-4 h-4" />
          <span className="font-medium">Document Preview</span>
        </div>
        {numPages > 0 && (
          <span className="text-xs text-muted-foreground font-mono">
            {numPages} page{numPages !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Scrollable multi-page PDF */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto px-4 py-4"
      >
        <Document
          file={filePreviewUrl}
          onLoadSuccess={({ numPages: n }) => {
            setNumPages(n);
            setLoadError(null);
          }}
          onLoadError={(error) => {
            setLoadError(error?.message || "Failed to load PDF.");
          }}
          loading={
            <div className="flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-muted-foreground">Loading PDF…</p>
              </div>
            </div>
          }
          error={
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 mx-auto max-w-md">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-destructive">Failed to Load PDF</p>
                  <p className="text-xs text-destructive/80 mt-1">
                    {loadError || "The document could not be rendered. Please try re-uploading."}
                  </p>
                </div>
              </div>
            </div>
          }
        >
          <div className="flex flex-col items-center gap-4">
            {Array.from({ length: numPages }, (_, i) => {
              const pageNum = i + 1;
              const isHighlighted = highlightPage === pageNum;

              return (
                <div
                  key={pageNum}
                  ref={(el) => {
                    pageRefs.current[pageNum] = el;
                  }}
                  className={`relative rounded-lg shadow-md transition-all duration-500 ${isHighlighted
                    ? "ring-4 ring-yellow-400/60 bg-yellow-200/30"
                    : "bg-white"
                    }`}
                >
                  {/* Yellow highlight overlay */}
                  {isHighlighted && (
                    <div className="absolute inset-0 bg-yellow-200/25 rounded-lg pointer-events-none z-10 animate-pulse" />
                  )}

                  <Page
                    pageNumber={pageNum}
                    width={containerWidth > 0 ? containerWidth - 32 : undefined}
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                  />

                  {/* Page number badge */}
                  <div className="absolute bottom-2 right-2 z-20 px-2 py-0.5 rounded bg-foreground/70 text-background text-[10px] font-mono">
                    {pageNum}
                  </div>
                </div>
              );
            })}
          </div>
        </Document>
      </div>
    </div>
  );
};

export default PdfViewer;
