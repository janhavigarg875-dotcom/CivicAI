import { useState, useCallback, useRef } from "react";
import type { ChatMessage, ChatResponse, ConversationPhase } from "../types";
import { sendMessage } from "../services/api";

function generateId(): string {
  return crypto.randomUUID();
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  phase: ConversationPhase | null;
  pendingDraft: Record<string, string> | null;
  requiresConfirmation: boolean;
  sessionId: string;
  send: (text: string) => Promise<void>;
  clearDraft: () => void;
  error: string | null;
}

export function useChat(): UseChatReturn {
  const sessionId = useRef<string>(generateId()).current;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [phase, setPhase] = useState<ConversationPhase | null>("GUIDANCE");
  const [pendingDraft, setPendingDraft] = useState<Record<string, string> | null>(null);
  const [requiresConfirmation, setRequiresConfirmation] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const appendMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;
      setError(null);

      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: text.trim(),
        timestamp: new Date(),
      };
      appendMessage(userMsg);
      setIsLoading(true);

      try {
        const response: ChatResponse = await sendMessage(sessionId, text.trim());

        const assistantMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: response.message,
          classification: response.classification,
          timestamp: new Date(),
        };
        appendMessage(assistantMsg);

        if (response.phase) setPhase(response.phase as ConversationPhase);
        setRequiresConfirmation(response.requires_confirmation ?? false);
        setPendingDraft(response.complaint_draft ?? null);
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "An unexpected error occurred.";
        setError(msg);
        const errMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content:
            "Sorry, I'm having trouble connecting right now. Please try again in a moment.",
          timestamp: new Date(),
        };
        appendMessage(errMsg);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, isLoading, appendMessage]
  );

  const clearDraft = useCallback(() => {
    setPendingDraft(null);
    setRequiresConfirmation(false);
  }, []);

  return {
    messages,
    isLoading,
    phase,
    pendingDraft,
    requiresConfirmation,
    sessionId,
    send,
    clearDraft,
    error,
  };
}
