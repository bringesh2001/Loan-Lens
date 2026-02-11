import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/lib/mock-data";

interface ChatTabProps {
  onClauseClick: (clauseRef: string, page: number) => void;
}

const initialMessages: ChatMessage[] = [
  {
    id: "1",
    role: "assistant",
    content:
      "I've analyzed your loan document. Feel free to ask me anything about the terms, fees, or clauses. I can also highlight specific sections in the document for you.",
  },
];

const mockResponses: Record<string, { content: string; clauseRef?: string; page?: number }> = {
  default: {
    content:
      "Based on your loan document, the most critical concern is the unilateral interest rate revision clause (Section 4.2b). This allows the lender to change your rate without notice, beyond normal repo rate changes. I'd recommend negotiating this clause or getting it capped in writing.",
  },
  prepayment: {
    content:
      "Your prepayment terms state a 2% penalty on outstanding principal for the first 3 years. After that, there's no penalty. If you're planning to prepay, waiting until after Year 3 could save you significant money.",
    clauseRef: "Section 2.4",
    page: 2,
  },
  interest: {
    content:
      "Your loan has a floating interest rate of 8.75% p.a. linked to the lender's EBLR. Importantly, the rate resets quarterly, not annually—meaning your EMI can change every 3 months. This is defined in Section 4.3.",
    clauseRef: "Section 4.3",
    page: 3,
  },
};

const ChatTab = ({ onClauseClick }: ChatTabProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const sendMessage = () => {
    if (!input.trim()) return;
    const userMsg: ChatMessage = { id: Date.now().toString(), role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    setTimeout(() => {
      const lowerInput = input.toLowerCase();
      const response = lowerInput.includes("prepay")
        ? mockResponses.prepayment
        : lowerInput.includes("interest") || lowerInput.includes("rate")
        ? mockResponses.interest
        : mockResponses.default;

      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.content,
        clauseRef: response.clauseRef,
        page: response.page,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsTyping(false);
    }, 1200);
  };

  return (
    <div className="flex flex-col h-[400px]">
      <div className="flex-1 overflow-auto space-y-3 pr-1">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground"
              }`}
            >
              {msg.content}
              {msg.clauseRef && (
                <button
                  onClick={() => onClauseClick(msg.clauseRef!, msg.page!)}
                  className="block mt-2 text-[11px] text-accent underline underline-offset-2 hover:opacity-80"
                >
                  View {msg.clauseRef} in document →
                </button>
              )}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-xl px-4 py-3 text-sm text-muted-foreground">
              <span className="animate-pulse">Analyzing document...</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Ask about your loan..."
          className="flex-1 bg-muted rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30 text-foreground placeholder:text-muted-foreground"
        />
        <Button size="icon" className="h-9 w-9 shrink-0" onClick={sendMessage} disabled={!input.trim()}>
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};

export default ChatTab;
