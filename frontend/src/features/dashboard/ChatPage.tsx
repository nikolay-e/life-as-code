import { useEffect, useRef, useState } from "react";
import { useChat } from "../../hooks/useChat";
import { Card, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { LoadingState } from "../../components/ui/loading-state";
import { format, parseISO } from "date-fns";
import { MessageCircle, Send, Trash2, Bot, User, Loader2 } from "lucide-react";
import type { ChatMessage } from "../../types/api";

function MessageBubble({ message }: Readonly<{ message: ChatMessage }>) {
  const isUser = message.role === "user";
  const timeStr = (() => {
    try {
      return format(parseISO(message.created_at), "HH:mm");
    } catch {
      return "";
    }
  })();

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={`max-w-[80%] space-y-1 ${isUser ? "items-end" : "items-start"} flex flex-col`}
      >
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm ${
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : "bg-muted text-foreground rounded-tl-sm"
          }`}
        >
          <p className="whitespace-pre-wrap break-words">
            {message.text_preview ?? ""}
          </p>
        </div>
        <p className="text-[10px] text-muted-foreground px-1">{timeStr}</p>
      </div>
    </div>
  );
}

export function ChatPage() {
  const {
    messages,
    isLoading,
    isSending,
    error,
    loadHistory,
    sendMessage,
    clearHistory,
  } = useChat();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput("");
    await sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] max-h-[800px]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <MessageCircle className="h-7 w-7" />
            Health Assistant
          </h1>
          <p className="text-muted-foreground mt-1">
            Ask questions about your health data
          </p>
        </div>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void clearHistory()}
            className="text-muted-foreground"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Clear
          </Button>
        )}
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardContent
          className="flex-1 overflow-y-auto p-4 space-y-4"
          style={{ minHeight: 0 }}
        >
          {isLoading ? (
            <LoadingState message="Loading conversation..." />
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-3 text-muted-foreground">
              <Bot className="h-12 w-12 opacity-30" />
              <div>
                <p className="font-medium">Start a conversation</p>
                <p className="text-sm">
                  Ask about your HRV, sleep, training, or anything
                  health-related
                </p>
              </div>
            </div>
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}
          {isSending && (
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                <Bot className="h-4 w-4" />
              </div>
              <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-2.5">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </CardContent>

        <div className="border-t p-3">
          {error && (
            <p className="text-xs text-destructive mb-2 px-1">{error}</p>
          )}
          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your health data... (Enter to send, Shift+Enter for newline)"
              className="flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring min-h-[40px] max-h-[120px]"
              rows={1}
              disabled={isSending}
            />
            <Button
              size="sm"
              onClick={() => void handleSend()}
              disabled={!input.trim() || isSending}
              className="h-10 w-10 p-0 flex-shrink-0"
              aria-label={isSending ? "Sending message" : "Send message"}
            >
              {isSending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
