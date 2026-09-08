// Shared TypeScript types mirroring backend Pydantic schemas

export type IntentType =
  | "INFORMATION"
  | "GUIDANCE"
  | "SOLUTION"
  | "COMPLAINT"
  | "COMPLAINT_STATUS";

export type CategoryType = "WATER" | "AIR" | "WASTE";
export type ScopeType = "CAMPUS" | "CITY";
export type ComplaintStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";

export type ConversationPhase =
  | "GUIDANCE"
  | "RESOLUTION_CHECK"
  | "COMPLAINT_OFFER"
  | "DETAIL_COLLECTION"
  | "COMPLAINT_CONFIRM"
  | "COMPLETE";

export interface ClassificationResult {
  intent: IntentType;
  category: CategoryType | null;
  scope: ScopeType | null;
  confidence: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  classification?: ClassificationResult | null;
  timestamp: Date;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  classification: ClassificationResult | null;
  requires_confirmation: boolean;
  complaint_draft: Record<string, string> | null;
  phase: ConversationPhase | null;
}

export interface ComplaintRequest {
  session_id: string;
  category: CategoryType;
  scope: ScopeType;
  issue_summary: string;
  location: string;
  duration?: string;
  description?: string;
  previous_action?: string;
  confirmed: true;
}

export interface ComplaintResponse {
  id: string;
  category: string;
  scope: string;
  routed_to: string;
  status: ComplaintStatus;
  created_at: string;
  message: string;
}

export interface ComplaintStatusResponse {
  id: string;
  category: string;
  scope: string;
  issue_summary: string;
  location: string;
  routed_to: string;
  status: ComplaintStatus;
  created_at: string;
  disclaimer: string;
}
