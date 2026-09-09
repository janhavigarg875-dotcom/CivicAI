import { useEffect, useRef } from "react";
import type { ConversationPhase } from "../types";

const PHASE_CONFIG: Partial<Record<ConversationPhase, { label: string; color: string }>> = {
  GUIDANCE:          { label: "Providing guidance",       color: "text-blue-600" },
  RESOLUTION_CHECK:  { label: "Checking resolution",      color: "text-indigo-600" },
  COMPLAINT_OFFER:   { label: "Complaint option",         color: "text-orange-600" },
  DETAIL_COLLECTION: { label: "Collecting details",       color: "text-orange-600" },
  COMPLAINT_CONFIRM: { label: "Awaiting confirmation",    color: "text-red-600" },
  COMPLETE:          { label: "Session complete",         color: "text-green-600" },
};

interface PhaseIndicatorProps {
  phase: ConversationPhase | null;
}

export function PhaseIndicator({ phase }: PhaseIndicatorProps) {
  if (!phase) return null;
  const cfg = phase ? PHASE_CONFIG[phase] : null;
  if (!cfg) return null;

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className={`font-medium ${cfg.color}`}>{cfg.label}</span>
    </div>
  );
}

interface TypingIndicatorProps {
  visible: boolean;
}

export function TypingIndicator({ visible }: TypingIndicatorProps) {
  if (!visible) return null;
  return (
    <div className="flex justify-start mb-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center mr-2">
        <span className="text-white text-xs font-bold">CA</span>
      </div>
      <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1">
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}

interface ScrollAnchorProps {
  deps: unknown[];
}

export function ScrollAnchor({ deps }: ScrollAnchorProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: "smooth" });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return <div ref={ref} />;
}
