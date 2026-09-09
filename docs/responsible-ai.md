# CivicAI — Responsible AI Decisions

This document records the Responsible AI (RAI) design decisions made in CivicAI. It maps each principle to specific implementation choices so that the safeguards are auditable and transparent to developers, reviewers, and users.

---

## Principles and Implementation

### 1. Transparency

**Principle:** Users must always know they are talking to an AI, not a human. They must understand what the system can and cannot do.

**Implementation:**
- The `SYSTEM_PROMPT` in [`backend/core/prompts.py`](../backend/core/prompts.py) explicitly states: *"You are CivicAI, an AI assistant. You are not a human."*
- The frontend [`AITransparencyBanner`](../frontend/src/components/AITransparencyBanner.tsx) is rendered persistently at the top of the chat interface on every page load. It cannot be dismissed.
- Every complaint response from [`ComplaintService.register()`](../backend/services/complaint_service.py) includes a mandatory disclaimer: *"This is a simulated complaint record. No real complaint has been submitted and no real authority has been notified."*
- The [`ComplaintConfirmModal`](../frontend/src/components/ComplaintConfirmModal.tsx) shows the disclaimer in a prominent red box before the user confirms.
- The `phase` field in every `ChatResponse` is returned to the frontend, making the conversation state machine's current state visible.

---

### 2. Privacy

**Principle:** Users should not be required to share personal identifying information. Any PII inadvertently included in complaint text must not be persisted.

**Implementation:**
- The `SYSTEM_PROMPT` instructs the model: *"Do not ask for or encourage sharing of personal identifying information beyond location/area."*
- [`GuardrailService.sanitize_complaint_text()`](../backend/services/guardrail_service.py) applies regex-based PII removal to the `description` and `previous_action` fields before they are written to the SQLite database (RAI Gate 3).
- Patterns removed include: Indian mobile numbers, international phone numbers, email addresses, Aadhaar (12-digit), PAN card, and passport-like identifiers.
- Raw conversation history is held **only in memory** (the `ConversationService` in-memory dict). No conversation transcript is persisted to any database.

---

### 3. Fairness

**Principle:** All users must receive equal quality of guidance regardless of their location, community identity, or the nature of their described issue.

**Implementation:**
- The `SYSTEM_PROMPT` includes: *"Treat all users equally regardless of their described location, community, or background."* and *"Provide equally helpful guidance whether the issue is on campus or in the city."*
- The RAG pipeline retrieves context for both CAMPUS and CITY scopes with identical logic — there is no scope that receives fewer or lower-quality knowledge base documents.
- The complaint ID generation and routing logic applies identically to CAMPUS and CITY issues.
- No demographic, geographic, or identity information is used to filter or rank responses.

---

### 4. Human Oversight

**Principle:** No automated action should be taken without explicit user confirmation. Users must retain control at every step.

**Implementation:**
- The conversation phase machine requires the user to pass through `COMPLAINT_OFFER` → `DETAIL_COLLECTION` → `COMPLAINT_CONFIRM` before any complaint is registered.
- **The `COMPLAINT_CONFIRM` phase is the enforcement gate:** `ComplaintService.register()` raises a `ValueError` if called with `confirmed=False`. The `POST /api/complaints` endpoint returns HTTP 400 if `confirmed` is not `True`.
- The user can cancel at any phase by saying "no" or "cancel" — the system always offers this option.
- The `ComplaintConfirmModal` in the frontend shows the full complaint draft with a disclaimer before the user can click "Submit Complaint".
- `ComplaintService.register()` is only reachable from the `__SUBMIT_COMPLAINT__` sentinel path in `chat.py`, which itself is only triggered after the `COMPLAINT_CONFIRM` phase yields the sentinel — preventing any bypass of the confirmation step.

---

### 5. No Invented Facts (Grounding)

**Principle:** The assistant must never invent facts, statistics, regulatory details, authority contacts, or solutions not supported by the knowledge base.

**Implementation:**
- The RAG pipeline in [`RAGService.retrieve()`](../backend/services/rag_service.py) retrieves the top-k most relevant chunks from the curated knowledge base before every LLM call. These chunks are injected into the system message as `=== RELEVANT KNOWLEDGE BASE CONTEXT ===`.
- The `SYSTEM_PROMPT` explicitly prohibits hallucination: *"Only provide information and guidance that is grounded in the context provided to you. Do NOT invent facts, statistics, regulations, or authority contacts."* and *"If you are unsure or the context does not cover the question, say so clearly and honestly."*
- [`GuardrailService.check_output_safety()`](../backend/services/guardrail_service.py) scans every LLM output for phrases that falsely claim real authorities were notified or real actions were taken (RAI Gate 2). Detected phrases trigger appending of the `_SAFE_REPLACEMENT` disclaimer.
- The classification prompt uses `response_format` with a JSON schema to ensure structured, parseable output rather than free-form text that could include invented metadata.

---

## RAI Gate Architecture

The three gates form a layered defence:

```
User Message
    │
    ▼
[Gate 1] GuardrailService.is_in_scope()
    │   Rejects non-Water/Air/Waste messages before any LLM call
    │
    ▼
LLM Call → generate_response()
    │
    ▼
[Gate 2] GuardrailService.check_output_safety()
    │   Scans output for false claims about real authority notification
    │
    ▼
Conversation Phase Machine (human confirmation required)
    │
    ▼
[Gate 3] GuardrailService.sanitize_complaint_text()
    │   Strips PII from free-text fields before SQLite persistence
    │
    ▼
ComplaintService.register() — only reachable if confirmed=True
```

---

## SDG Alignment

| SDG | How CivicAI Contributes |
|---|---|
| **SDG 11** — Sustainable Cities and Communities | Core mission: AI-assisted civic engagement for urban environmental issue reporting and resolution |
| **SDG 6** — Clean Water and Sanitation | Water management knowledge base + complaint routing for water quality and supply issues |
| **SDG 12** — Responsible Consumption and Production | Waste management guidance: segregation, e-waste, composting, and reduction of single-use plastics |
| **SDG 13** — Climate Action | Air quality guidance: AQI awareness, emission source reporting, and community action recommendations |

---

## Known Limitations

- **Complaint simulation only:** CivicAI does not integrate with any real authority system. All complaint IDs are simulated and no notification is sent to any municipal or campus body.
- **In-memory sessions:** Session state is not persisted across server restarts. Users would need to start a new conversation after a backend restart.
- **LLM grounding is best-effort:** While the RAG pipeline and system prompt strongly discourage hallucination, the LLM can still produce inaccurate output. Users should verify critical information with official sources.
- **Knowledge base is static:** The 6 Markdown documents represent general best-practice guidance and are not updated in real time with local regulatory changes.
- **English only:** The current knowledge base and prompts are in English only.
