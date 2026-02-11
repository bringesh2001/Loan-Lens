import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useDocument } from "@/context/DocumentContext";
import { sendChatMessage } from "@/lib/api";
import { toast } from "sonner";
import type { ChatMessage, ChatReference } from "@/lib/types";

// ==========================================================================
// Props
// ==========================================================================

interface ChatTabProps {
  onClauseClick: (clauseRef: string, page: number, section: string, snippet?: string) => void;
}

// ==========================================================================
// Component
// ==========================================================================

const ChatTab = ({ onClauseClick }: ChatTabProps) => {
  const { documentId, conversationId, setConversationId } = useDocument();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "I've analyzed your loan document. Feel free to ask me anything about the terms, fees, or clauses. I can also highlight specific sections in the document for you.",
    },
  ]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const mutation = useMutation({
    mutationFn: (message: string) =>
      sendChatMessage(documentId!, message, conversationId),
    onSuccess: (response) => {
      // Store conversationId in context
      setConversationId(response.conversation_id);

      // Append AI response
      const assistantMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: response.response,
        references: response.references,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Highlight referenced clauses
      if (response.references?.length > 0) {
        const ref = response.references[0];
        onClauseClick(ref.section, ref.page, ref.section);
      }
    },
    onError: (error) => {
      toast.error("Chat Error", {
        description: error instanceof Error ? error.message : "Failed to get response",
      });
      // Remove optimistic "thinking" state — user can retry
    },
  });

  const handleSend = () => {
    const text = input.trim();
    if (!text || mutation.isPending) return;

    // Append user message immediately
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    mutation.mutate(text);
  };

  return (
    <div className="flex flex-col h-[400px]">
      <div ref={scrollRef} className="flex-1 overflow-auto space-y-3 pr-1">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${msg.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-foreground"
                }`}
            >
              {msg.content}
              {msg.references && msg.references.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.references.map((ref: ChatReference, i: number) => (
                    <button
                      key={i}
                      onClick={() => onClauseClick(ref.section, ref.page, ref.section)}
                      className="block text-[11px] text-accent underline underline-offset-2 hover:opacity-80"
                    >
                      View {ref.section} (Page {ref.page}) in document →
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {mutation.isPending && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-xl px-4 py-3 text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Analyzing document...</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask about your loan..."
          disabled={mutation.isPending}
          className="flex-1 bg-muted rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30 text-foreground placeholder:text-muted-foreground disabled:opacity-50"
        />
        <Button
          size="icon"
          className="h-9 w-9 shrink-0"
          onClick={handleSend}
          disabled={!input.trim() || mutation.isPending}
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};

export default ChatTab;
