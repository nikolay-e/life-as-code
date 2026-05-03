import { useState, useCallback } from "react";
import { api } from "../lib/api";
import type { ChatMessage } from "../types/api";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.chat.getMessages(50);
      setMessages(res.messages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load chat history");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const sendMessage = useCallback(async (text: string): Promise<void> => {
    if (!text.trim()) return;
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      text_preview: text,
      model: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsSending(true);
    setError(null);
    try {
      const res = await api.chat.sendMessage(text);
      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        text_preview: res.reply,
        model: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send message");
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
    } finally {
      setIsSending(false);
    }
  }, []);

  const clearHistory = useCallback(async () => {
    try {
      await api.chat.clearHistory();
      setMessages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clear history");
    }
  }, []);

  return {
    messages,
    isLoading,
    isSending,
    error,
    loadHistory,
    sendMessage,
    clearHistory,
  };
}
