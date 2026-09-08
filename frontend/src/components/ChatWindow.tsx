import { useState, useRef, useCallback } from "react";
import { Send } from "lucide-react";
import { useChat } from "../hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { AITransparencyBanner } from "./AITransparencyBanner";
import { ComplaintConfirmModal } from "./ComplaintConfirmModal";
import { PhaseIndicator, TypingIndicator, ScrollAnchor } from "./ChatHelpers";
import type { CategoryType, ScopeType } from "../types";

const WELCOME_SUGGESTIONS = [
  "There is a water leak near my dorm room",
  "The air quality near our campus is very bad due to construction",
  "Garbage bins in Block C have been overflowing for 3 days",
  "The tap water in my building looks brownish",
];

export function ChatWindow() {
  const {
    messages,
    isLoading,
    phase,
    pendingDraft,
    requiresConfirmation,
    send,
    clearDraft,
    error,
  } = useChat();

  const [input, setInput] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    await send(text);
  }, [input, isLoading, send]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // When the backend returns requires_confirmation, open modal
  const handleOpenModal = () => setIsModalOpen(true);

  const handleModalConfirm = async () => {
    setIsSubmitting(true);
    // Send "Yes, confirm" which triggers the COMPLAINT_CONFIRM phase handler
    await send("Yes, confirm submission");
    setIsSubmitting(false);
    setIsModalOpen(false);
    clearDraft();
  };

  const handleModalCancel = async () => {
    setIsModalOpen(false);
    await send("No, cancel");
    clearDraft();
  };

  // Get classification from last assistant message
  const lastAssistantMsg = [...messages].reverse().find((m) => m.role === "assistant");
  const lastCategory = lastAssistantMsg?.classification?.category as CategoryType | null;
  const lastScope = lastAssistantMsg?.classification?.scope as ScopeType | null;

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full bg-gray-50">

      {/* Transparency banner */}
      <div className="px-4 pt-3 pb-1">
        <AITransparencyBanner />
      </div>

      {/* Phase indicator bar */}
      <div className="px-4 py-1.5 flex items-center justify-between border-b border-gray-100 bg-white">
        <PhaseIndicator phase={phase} />
        {error && (
          <span className="text-xs text-red-600 font-medium">{error}</span>
        )}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full py-12 text-center">
            <div className="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center mb-4">
              <span className="text-2xl">🌱</span>
            </div>
            <h3 className="text-base font-semibold text-gray-700 mb-1">
              Welcome to CivicAI
            </h3>
            <p className="text-sm text-gray-500 mb-6 max-w-xs">
              Describe your water, air, or waste concern and I'll provide guidance.
            </p>
            <div className="grid grid-cols-1 gap-2 w-full max-w-sm">
              {WELCOME_SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setInput(s);
                    inputRef.current?.focus();
                  }}
                  className="text-left text-sm px-3 py-2 rounded-lg border border-gray-200 bg-white hover:bg-blue-50 hover:border-blue-300 text-gray-700 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        <TypingIndicator visible={isLoading} />
        <ScrollAnchor deps={[messages.length, isLoading]} />
      </div>

      {/* Complaint confirmation prompt — shown inline if requires_confirmation and draft is present */}
      {requiresConfirmation && pendingDraft && !isModalOpen && (
        <div className="mx-4 mb-2 p-3 bg-orange-50 border border-orange-200 rounded-lg flex items-center justify-between gap-3">
          <p className="text-sm text-orange-800 font-medium">
            Ready to review and confirm your complaint?
          </p>
          <button
            onClick={handleOpenModal}
            className="flex-shrink-0 text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 px-3 py-1.5 rounded-lg transition-colors"
          >
            Review
          </button>
        </div>
      )}

      {/* Input bar */}
      <div className="px-4 pb-4 pt-2 border-t border-gray-100 bg-white">
        <div className="flex items-end gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Describe your environmental concern…"
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed"
            style={{ maxHeight: "120px" }}
            aria-label="Message input"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            aria-label="Send message"
            className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 flex items-center justify-center transition-colors"
          >
            <Send size={15} className="text-white" />
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1.5 text-center">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>

      {/* Complaint confirmation modal */}
      {isModalOpen && pendingDraft && (
        <ComplaintConfirmModal
          draft={pendingDraft}
          category={lastCategory}
          scope={lastScope}
          onConfirm={handleModalConfirm}
          onCancel={handleModalCancel}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
}
