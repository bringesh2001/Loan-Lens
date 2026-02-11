import { useState, useCallback } from "react";
import { Upload, Shield, FileText, ChevronRight, Sparkles, Lock, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import heroBg from "@/assets/hero-bg.jpg";

interface LandingPageProps {
  onFileUpload: (file: File) => void;
}

const LandingPage = ({ onFileUpload }: LandingPageProps) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(e.type === "dragenter" || e.type === "dragover");
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file?.type === "application/pdf") onFileUpload(file);
  }, [onFileUpload]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileUpload(file);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Eye className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold text-foreground tracking-tight">Loan Lens</span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm">How it works</Button>
            <Button size="sm">Get Started</Button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-20 flex-1 flex flex-col items-center justify-center overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-[0.07]"
          style={{ backgroundImage: `url(${heroBg})` }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-background via-background/95 to-background" />

        <div className="relative z-10 max-w-3xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 text-accent text-sm font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            AI-Powered Loan Analysis
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-foreground tracking-tight leading-[1.1] mb-5">
            Understand your loan
            <br />
            <span className="text-accent">before you sign</span>
          </h1>

          <p className="text-lg text-muted-foreground max-w-xl mx-auto mb-10">
            Upload any loan document and get instant AI analysis. We highlight hidden fees, risky clauses, and break down complex terms into plain language.
          </p>

          {/* Upload Area */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`relative mx-auto max-w-lg rounded-2xl border-2 border-dashed p-10 transition-all duration-300 cursor-pointer group ${
              isDragging
                ? "border-accent bg-accent/5 scale-[1.02]"
                : "border-border hover:border-accent/50 hover:bg-muted/50"
            }`}
          >
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileInput}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="flex flex-col items-center gap-4">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${
                isDragging ? "bg-accent/20" : "bg-muted group-hover:bg-accent/10"
              }`}>
                <Upload className={`w-7 h-7 transition-colors ${isDragging ? "text-accent" : "text-muted-foreground group-hover:text-accent"}`} />
              </div>
              <div>
                <p className="text-base font-semibold text-foreground mb-1">
                  Drop your loan PDF here
                </p>
                <p className="text-sm text-muted-foreground">
                  or click to browse · PDF up to 20MB
                </p>
              </div>
              <Button variant="outline" size="sm" className="pointer-events-none">
                <FileText className="w-4 h-4 mr-2" />
                Select PDF
              </Button>
            </div>
          </div>

          {/* Trust badges */}
          <div className="flex flex-wrap items-center justify-center gap-6 mt-8 text-sm text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5" />
              <span>End-to-end encrypted</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" />
              <span>Never shared with third parties</span>
            </div>
            <div className="flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" />
              <span>Auto-deleted after 24 hours</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 border-t border-border/50">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: Sparkles,
                title: "AI Summary",
                desc: "Get a plain-language breakdown of key loan terms, EMI, total payable amount, and prepayment options.",
              },
              {
                icon: Shield,
                title: "Red Flag Detection",
                desc: "Automatically detect risky clauses, hidden fees, and unfavorable terms before you commit.",
              },
              {
                icon: Eye,
                title: "Clause Highlights",
                desc: "Click any flagged item to see the exact clause highlighted in your original document.",
              },
            ].map((f) => (
              <div
                key={f.title}
                className="glass-card rounded-xl p-6 group hover:shadow-xl transition-all duration-300"
              >
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center mb-4 group-hover:bg-accent/20 transition-colors">
                  <f.icon className="w-5 h-5 text-accent" />
                </div>
                <h3 className="font-semibold text-foreground mb-2">{f.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
