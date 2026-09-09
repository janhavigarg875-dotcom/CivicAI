# CivicAI — Implementation Plan

## Top-Level Overview

**Goal:** Build CivicAI, an AI-powered sustainability assistant for campus students and city/community citizens. The system helps users with Water, Air, and Waste management issues by providing information and guidance first, escalating to simulated complaint registration only when the user confirms the problem is unresolved.

**Scope:**
- React + TypeScript single-page application (frontend)
- Python FastAPI backend (API + orchestration)
- IBM watsonx.ai LLM integration (`ibm/granite-3-8b-instruct` — Granite 3.1, multitenant, immediately available)
- Lightweight local RAG pipeline (FAISS or ChromaDB + sentence-transformers)
- SQLite database for complaint persistence
- Multi-turn conversation state management
- Complaint workflow with human confirmation gate
- Responsible AI safeguards throughout

**Non-Goals:**
- IBM watsonx Orchestrate
- Real authority system integrations (simulated only)
- User authentication / multi-user accounts (out of scope for this phase)
- Production deployment / cloud hosting

**SDG Alignment:** SDG 11 (primary), SDG 6, SDG 12, SDG 13 (supporting)

---

## Architecture Summary

```
civicai/
├── frontend/          # React + TypeScript SPA (Vite)
├── backend/           # FastAPI Python application
│   ├── api/           # Route handlers
│   ├── core/          # Config, constants, enums
│   ├── services/      # LLM, RAG, classifier, complaint
│   ├── models/        # SQLAlchemy ORM models
│   ├── schemas/       # Pydantic request/response schemas
│   ├── db/            # Database setup + migrations
│   └── knowledge_base/ # Curated Markdown/JSON documents
└── docs/              # Architecture notes, ADRs
```

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffolding & Folder Structure

**Status:** `[x] done`

**Intent:**
Establish the full monorepo folder structure for both frontend and backend so that all subsequent sub-tasks have a clean, agreed-upon home for their files. This avoids structural conflicts later.

**Expected Outcomes:**
- `frontend/` scaffold created via Vite (React + TypeScript template)
- `backend/` scaffold created with FastAPI, SQLAlchemy, and core dependency files
- Root-level `README.md`, `.gitignore`, and `docker-compose.yml` (optional/local dev)
- Both apps run locally with a "hello world" health check

**Todo List:**
1. Create root `civicai/` workspace structure with `frontend/`, `backend/`, `docs/` directories
2. Scaffold frontend: `npm create vite@latest frontend -- --template react-ts`
3. Install frontend deps: `react-router-dom`, `axios`, `tailwindcss`, `lucide-react`
4. Scaffold backend: create `backend/` with `main.py`, `requirements.txt`, and sub-package folders (`api/`, `core/`, `services/`, `models/`, `schemas/`, `db/`, `knowledge_base/`)
5. Add backend deps to `requirements.txt`: `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `python-dotenv`, `httpx`, `faiss-cpu` (or `chromadb`), `sentence-transformers`, `ibm-watsonx-ai`
6. Add `backend/.env.example` with `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `MODEL_ID`
7. Add root `.gitignore` covering `node_modules/`, `__pycache__/`, `*.db`, `.env`
8. Write root `README.md` with project description, setup steps, and SDG alignment note
9. Verify `uvicorn main:app --reload` starts backend and `npm run dev` starts frontend

**Relevant Context:**
- All subsequent sub-tasks depend on this structure being in place.
- The `knowledge_base/` folder will hold Markdown/JSON docs consumed by Sub-Task 4 (RAG).
- The `.env` pattern established here is used by Sub-Task 3 (LLM integration).

---

### Sub-Task 2 — Core Enums, Schemas & Data Models

**Status:** `[x] done`

**Intent:**
Define the shared vocabulary of the system — enums for intent, category, and scope — and the Pydantic schemas for API request/response contracts. Also define the SQLAlchemy ORM model for complaints. This sub-task creates the "language" all other components speak.

**Expected Outcomes:**
- `backend/core/enums.py` with `IntentType`, `CategoryType`, `ScopeType` enums
- `backend/schemas/` with `ChatRequest`, `ChatResponse`, `ClassificationResult`, `ComplaintRequest`, `ComplaintResponse`, `ComplaintStatusResponse` Pydantic models
- `backend/models/complaint.py` SQLAlchemy ORM model with all complaint fields
- `backend/db/database.py` with SQLite engine, session factory, and `Base` declarative base
- Database table created on startup via `Base.metadata.create_all()`

**Todo List:**
1. Create `backend/core/enums.py`:
   - `IntentType`: `INFORMATION`, `GUIDANCE`, `SOLUTION`, `COMPLAINT`, `COMPLAINT_STATUS`
   - `CategoryType`: `WATER`, `AIR`, `WASTE`
   - `ScopeType`: `CAMPUS`, `CITY`
2. Create `backend/db/database.py` with SQLite engine (`civicai.db`), `SessionLocal`, and `Base`
3. Create `backend/models/complaint.py` SQLAlchemy model with fields: `id` (UUID string), `category` (enum string), `scope` (enum string), `issue_summary` (text), `location` (text), `duration` (text), `description` (text), `previous_action` (text), `status` (default `OPEN`), `created_at` (datetime), `routed_to` (text — simulated authority)
4. Create `backend/schemas/chat.py` with `ChatRequest` (session_id, message), `ClassificationResult` (intent, category, scope, confidence), `ChatResponse` (session_id, message, classification, requires_confirmation, complaint_draft)
5. Create `backend/schemas/complaint.py` with `ComplaintRequest` (all detail fields + confirmed bool), `ComplaintResponse` (id, routed_to, status, message), `ComplaintStatusResponse`
6. Wire `Base.metadata.create_all()` in `main.py` startup event

**Relevant Context:**
- `IntentType`, `CategoryType`, `ScopeType` are used by the classifier (Sub-Task 3), the conversation manager (Sub-Task 5), and the complaint workflow (Sub-Task 6).
- The `routed_to` field is derived from `scope`: CAMPUS → "Campus Management / Maintenance", CITY → "Municipal / Civic Authority".

---

### Sub-Task 3 — IBM watsonx.ai LLM Service

**Status:** `[x] done`

**Intent:**
Build the LLM service layer that wraps IBM watsonx.ai API calls. This service handles prompt construction, model invocation, and response parsing. It is the single place where LLM calls are made, making it easy to swap models or add guardrails.

**Expected Outcomes:**
- `backend/services/llm_service.py` with a `WatsonxLLMService` class
- Methods: `classify_intent(user_message, conversation_history) -> ClassificationResult` and `generate_response(user_message, context_chunks, conversation_history, classification) -> str`
- Prompts are structured, role-based, and include explicit Responsible AI instructions (no invented facts, transparency about being AI, privacy-safe)
- Config loaded from `.env` via `backend/core/config.py`
- Graceful error handling (API timeout, auth failure) returns user-friendly fallback messages

**Todo List:**
1. Create `backend/core/config.py` using `pydantic-settings` or `python-dotenv` to load `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `MODEL_ID` from `.env`
2. Create `backend/services/llm_service.py` with `WatsonxLLMService` class using `ibm-watsonx-ai` SDK
3. Implement `classify_intent()` — sends a classification prompt and parses JSON output with `intent`, `category`, `scope` fields
4. Implement `generate_response()` — sends a grounded response prompt that includes: system instructions (RAI guardrails), retrieved KB context chunks, conversation history, and user message
5. Write system prompt template in `backend/core/prompts.py`:
   - Role: "You are CivicAI, an AI sustainability assistant..."
   - Constraints: only answer from provided context, do not invent facts, state when you are unsure, be transparent you are an AI, never submit real complaints
   - Instruction sequence: provide information/guidance first, then ask "Has the problem been resolved?", only offer complaint registration if user says no or explicitly asks
6. Add model parameters: `max_new_tokens`, `temperature`, `decoding_method` (greedy for classification, sampling for generation)
7. Add `try/except` with logging for API errors; return a safe fallback string on failure

**Relevant Context:**
- Classification output feeds the conversation state manager (Sub-Task 5) and complaint workflow (Sub-Task 6).
- The system prompt in `prompts.py` is the primary Responsible AI enforcement point.
- Default model: `ibm/granite-3-8b-instruct` (Granite 3.1 Instruct — confirmed active on multitenant hardware per IBM watsonx.ai docs). Configurable via `MODEL_ID` env var so it can be swapped to `ibm/granite-3-3-8b-instruct` (deploy-on-demand) or any other supported model without code changes.

---

### Sub-Task 4 — Knowledge Base & RAG Pipeline

**Status:** `[x] done`

**Intent:**
Build the local RAG pipeline that retrieves relevant environmental guidance from a curated knowledge base before passing context to the LLM. This grounds the LLM's answers in real, factual content and is a core Responsible AI safeguard against hallucination.

**Expected Outcomes:**
- `backend/knowledge_base/` contains curated Markdown documents for Water, Air, and Waste — both Campus and City scopes
- `backend/services/rag_service.py` with a `RAGService` class
- Documents chunked, embedded (`sentence-transformers/all-MiniLM-L6-v2`), and indexed in a FAISS or ChromaDB vector store
- `retrieve(query, category, scope, top_k=3) -> list[str]` method returns the most relevant text chunks
- Index built on startup from the Markdown files; optionally persisted to disk

**Todo List:**
1. Create knowledge base documents in `backend/knowledge_base/`:
   - `water_campus.md` — campus water issues (leaking pipes, water wastage, drinking water quality, conservation tips)
   - `water_city.md` — city water issues (supply disruption, flooding, river pollution, municipal reporting)
   - `air_campus.md` — campus air quality (HVAC issues, lab ventilation, indoor air quality, idling vehicles)
   - `air_city.md` — city air pollution (traffic emissions, industrial smoke, AQI awareness, reporting channels)
   - `waste_campus.md` — campus waste (segregation, bin overflow, e-waste, composting programs)
   - `waste_city.md` — city waste (collection schedules, illegal dumping, recycling, civic reporting)
2. Create `backend/services/rag_service.py` with `RAGService` class
3. Implement `_load_and_chunk_documents()` — reads all Markdown files, splits by paragraph/section into chunks of ~300 tokens, attaches metadata (`category`, `scope`, `source_file`)
4. Implement `_build_index()` — embeds chunks using `sentence-transformers` and indexes with FAISS (`IndexFlatL2`) or ChromaDB collection
5. Implement `retrieve(query, category, scope, top_k)` — embeds query, filters by `category`+`scope` metadata, returns top_k chunk texts
6. Optionally persist FAISS index to `backend/knowledge_base/index/` to avoid rebuild on every restart
7. Initialize `RAGService` singleton at app startup in `main.py`

**Relevant Context:**
- Retrieved chunks are passed to `WatsonxLLMService.generate_response()` as `context_chunks` (Sub-Task 3).
- The metadata filter (`category`, `scope`) requires that the classification result from Sub-Task 3 is available before retrieval.
- `sentence-transformers/all-MiniLM-L6-v2` is fast, local, and sufficient for this knowledge base size.

---

### Sub-Task 5 — Conversation State Manager & Chat API

**Status:** `[x] done`

**Intent:**
Build the conversation state machine that tracks multi-turn sessions — knowing whether the user is in the "guidance phase", the "resolution check phase", or the "complaint registration phase". This is the orchestration hub that connects the classifier, RAG, and LLM into a coherent dialogue flow.

**Expected Outcomes:**
- `backend/services/conversation_service.py` with `ConversationService` class managing in-memory session state
- Session state tracks: `session_id`, `history` (list of messages), `current_phase`, `last_classification`, `complaint_draft`
- `POST /api/chat` endpoint in `backend/api/chat.py` that correctly advances conversation phase based on user input and returns appropriate responses
- Correct phase transitions: `GUIDANCE` → ask resolution question → `COMPLAINT_OFFER` → collect details → `COMPLAINT_CONFIRM` → (if confirmed) submit complaint → `COMPLETE`
- The assistant never registers a complaint without user explicitly confirming

**Todo List:**
1. Define conversation phases as an enum in `backend/core/enums.py`: `GUIDANCE`, `RESOLUTION_CHECK`, `COMPLAINT_OFFER`, `DETAIL_COLLECTION`, `COMPLAINT_CONFIRM`, `COMPLETE`
2. Create `backend/services/conversation_service.py`:
   - `SessionState` dataclass: `session_id`, `history`, `phase`, `classification`, `complaint_draft` dict, `resolution_asked` bool
   - `get_or_create_session(session_id)` — returns existing or new session
   - `process_message(session_id, user_message) -> ChatResponse` — orchestrates the full turn
3. Inside `process_message()`:
   - If phase is `GUIDANCE` or new: call `LLMService.classify_intent()`, call `RAGService.retrieve()`, call `LLMService.generate_response()`, append to history, transition to `RESOLUTION_CHECK`
   - If phase is `RESOLUTION_CHECK`: detect if user says "no"/"not resolved"/"still have issue" → transition to `COMPLAINT_OFFER`; if "yes"/"resolved" → transition to `COMPLETE`
   - If phase is `COMPLAINT_OFFER`: confirm user wants to register → transition to `DETAIL_COLLECTION`, ask for location, duration, description, previous action one-by-one or as a form
   - If phase is `DETAIL_COLLECTION`: accumulate `complaint_draft` fields, when all collected transition to `COMPLAINT_CONFIRM`, show draft summary and ask for confirmation
   - If phase is `COMPLAINT_CONFIRM`: if user confirms → call `ComplaintService.register()`, return complaint ID; if user cancels → return to `GUIDANCE`
4. Create `backend/api/chat.py` with `POST /api/chat` route using FastAPI router; inject `ConversationService` dependency
5. Create `backend/api/router.py` to register all route modules; include in `main.py`

**Relevant Context:**
- `ComplaintService.register()` is defined in Sub-Task 6.
- The `complaint_draft` dict maps to the `ComplaintRequest` schema from Sub-Task 2.
- The "never submit without confirmation" gate lives in the `COMPLAINT_CONFIRM` phase check.
- In-memory session state is sufficient for this phase; sessions are keyed by `session_id` UUID generated client-side.

---

### Sub-Task 6 — Complaint Workflow & Complaint API

**Status:** `[x] done`

**Intent:**
Build the complaint registration service and REST API endpoints. This handles persisting confirmed complaints to SQLite, generating simulated complaint IDs, routing to the correct simulated authority, and supporting status lookup. The simulated nature must be clearly communicated to the user.

**Expected Outcomes:**
- `backend/services/complaint_service.py` with `ComplaintService` class
- `POST /api/complaints` endpoint to register a confirmed complaint
- `GET /api/complaints/{complaint_id}` endpoint for status lookup
- Complaint ID format: `CIV-<SCOPE>-<YYYYMMDD>-<5-digit-random>` (e.g. `CIV-CAMPUS-20240115-48291`)
- Response always includes a transparency disclaimer: "This is a simulated complaint ID. No real authority has been notified."
- `routed_to` field set based on scope: CAMPUS → "Campus Management / Maintenance", CITY → "Municipal / Civic Authority"

**Todo List:**
1. Create `backend/services/complaint_service.py` with `ComplaintService` class
2. Implement `register(complaint_request: ComplaintRequest, db: Session) -> ComplaintResponse`:
   - Generate complaint ID using `CIV-<SCOPE>-<YYYYMMDD>-<RANDOM>` format
   - Set `routed_to` based on `scope`
   - Persist `Complaint` ORM object to SQLite
   - Return `ComplaintResponse` with ID, `routed_to`, status `OPEN`, and transparency disclaimer message
3. Implement `get_status(complaint_id: str, db: Session) -> ComplaintStatusResponse`:
   - Query SQLite by `id`
   - Return status or 404 if not found
4. Create `backend/api/complaints.py` with:
   - `POST /api/complaints` — calls `ComplaintService.register()`
   - `GET /api/complaints/{complaint_id}` — calls `ComplaintService.get_status()`
5. Add SQLAlchemy `get_db()` dependency for session injection in both routes
6. Register complaint router in `backend/api/router.py`

**Relevant Context:**
- The `ComplaintRequest` and `ComplaintResponse` schemas are defined in Sub-Task 2.
- `ComplaintService.register()` is called by `ConversationService.process_message()` in Sub-Task 5 after user confirmation.
- The disclaimer message is a required Responsible AI transparency measure.

---

### Sub-Task 7 — Frontend: Chat UI

**Status:** `[x] done`

**Intent:**
Build the React TypeScript chat interface — the primary user surface. The UI must clearly communicate the assistant's identity (AI, not human), display guidance and complaint flows naturally, show the complaint confirmation step explicitly, and present the SDG mission context.

**Expected Outcomes:**
- `frontend/src/components/ChatWindow.tsx` — main chat interface with message thread and input
- `frontend/src/components/MessageBubble.tsx` — renders user and assistant messages with appropriate styling
- `frontend/src/components/ComplaintConfirmModal.tsx` — modal showing complaint draft for user confirmation before submission
- `frontend/src/components/CategoryBadge.tsx` — displays detected category (WATER/AIR/WASTE) and scope (CAMPUS/CITY)
- `frontend/src/services/api.ts` — typed Axios API client for `/api/chat` and `/api/complaints`
- `frontend/src/hooks/useChat.ts` — custom hook managing session state, message list, and API calls
- The header clearly states "CivicAI — AI Sustainability Assistant" and includes an AI transparency notice

**Todo List:**
1. Set up Tailwind CSS in the Vite project (`tailwind.config.js`, add to `index.css`)
2. Create `frontend/src/types/index.ts` with TypeScript interfaces mirroring backend schemas: `ChatMessage`, `ChatResponse`, `ClassificationResult`, `ComplaintDraft`, `ComplaintResponse`
3. Create `frontend/src/services/api.ts` with Axios instance (base URL from `VITE_API_URL` env var) and typed functions: `sendMessage(sessionId, message)`, `getComplaintStatus(complaintId)`
4. Create `frontend/src/hooks/useChat.ts`:
   - State: `messages`, `sessionId` (UUID, generated once), `isLoading`, `complaintDraft`, `showConfirmModal`
   - `sendMessage(text)` — calls API, appends user + assistant messages, sets `complaintDraft` if returned
   - `confirmComplaint()` — calls `POST /api/complaints`, appends confirmation message
5. Create `frontend/src/components/MessageBubble.tsx` — user messages right-aligned, assistant messages left-aligned with CivicAI avatar icon; render `CategoryBadge` on assistant messages that have a classification
6. Create `frontend/src/components/CategoryBadge.tsx` — small colored pill showing category (blue=WATER, gray=AIR, green=WASTE) and scope
7. Create `frontend/src/components/ComplaintConfirmModal.tsx` — shows all complaint draft fields, "Submit Complaint" and "Cancel" buttons, includes transparency disclaimer text in red/amber
8. Create `frontend/src/components/ChatWindow.tsx` — composes all sub-components, renders message list, input bar, and modal
9. Create `frontend/src/App.tsx` — renders app header with SDG badges and `ChatWindow`
10. Add `frontend/.env.example` with `VITE_API_URL=http://localhost:8000`

**Relevant Context:**
- The `ComplaintConfirmModal` is the UI enforcement of the "never submit without confirmation" Responsible AI rule.
- `CategoryBadge` uses data from `ChatResponse.classification` (Sub-Task 2 schema).
- Session ID is generated client-side as a UUID (`crypto.randomUUID()`) and passed in every chat request.

---

### Sub-Task 8 — Responsible AI Safeguards

**Status:** `[x] done`

**Intent:**
Implement the full set of Responsible AI safeguards as explicit, reviewable code — not just prompt instructions. This sub-task adds the guardrail layer, transparency notices, privacy handling, and fairness checks that make CivicAI trustworthy.

**Expected Outcomes:**
- `backend/services/guardrail_service.py` — input/output filter that rejects out-of-scope requests, strips PII from stored complaints, and flags low-confidence classifications
- System prompt in `prompts.py` finalised with full RAI instructions
- Frontend displays a persistent AI transparency banner
- Complaint storage never logs raw conversation text — only structured fields
- All API responses include a `disclaimer` field confirming simulated nature when relevant

**Todo List:**
1. Create `backend/services/guardrail_service.py`:
   - `is_in_scope(classification: ClassificationResult) -> bool` — returns True only if category is WATER/AIR/WASTE and confidence is above threshold
   - `sanitize_complaint_text(text: str) -> str` — regex-based removal of phone numbers, email addresses, and national ID patterns before storage
   - `check_output_safety(response_text: str) -> str` — scan for phrases that falsely claim a real complaint was submitted or that a real authority was contacted; replace with a safe fallback if detected
2. Update `ConversationService.process_message()` to call `is_in_scope()` and return a polite out-of-scope message if False
3. Update `ComplaintService.register()` to call `sanitize_complaint_text()` on `description` and `previous_action` fields before persisting
4. Update `WatsonxLLMService.generate_response()` to call `check_output_safety()` on LLM output before returning
5. Finalize `backend/core/prompts.py` system prompt with these explicit RAI rules:
   - "You are CivicAI, an AI assistant. You are not a human."
   - "Only provide information grounded in the context provided. Do not invent facts."
   - "If you are unsure, say so clearly."
   - "Never claim that a real complaint has been submitted or that a real authority has been notified."
   - "Do not ask for or store personal identifying information beyond location."
   - "Treat all users equally regardless of their described location or community."
6. Add a persistent `AITransparencyBanner` component in the frontend header: "CivicAI is an AI assistant. Responses are for guidance only. Complaints are simulated and not sent to real authorities."
7. Document all RAI decisions in `docs/responsible-ai.md`

**Relevant Context:**
- `guardrail_service.py` is called by both `ConversationService` (Sub-Task 5) and `ComplaintService` (Sub-Task 6).
- The `check_output_safety()` function is the last line of defense before LLM text reaches the user.
- The `AITransparencyBanner` addresses the transparency and human oversight principles.

---

### Sub-Task 9 — Testing Strategy

**Status:** `[x] done`

**Intent:**
Write the test suite covering unit tests for core services, integration tests for the API, and a set of manual E2E test scripts. This validates correctness and ensures the Responsible AI safeguards and complaint workflow behave exactly as specified.

**Expected Outcomes:**
- `backend/tests/` with unit tests for `LLMService` (mocked), `RAGService`, `ConversationService`, `ComplaintService`, and `GuardrailService`
- `backend/tests/test_api.py` with FastAPI `TestClient` integration tests for `/api/chat` and `/api/complaints`
- `docs/e2e-test-scenarios.md` with manual test scripts covering all intent types, both scopes, complaint registration flow, and RAI edge cases
- All unit and integration tests pass with `pytest`

**Todo List:**
1. Create `backend/tests/__init__.py` and `backend/tests/conftest.py` with a test SQLite database fixture and mocked `WatsonxLLMService`
2. Write `backend/tests/test_classifier.py` — test that `classify_intent()` correctly parses mock LLM JSON output for all intent/category/scope combinations
3. Write `backend/tests/test_rag_service.py` — test `retrieve()` returns relevant chunks for sample queries; test metadata filtering by category and scope
4. Write `backend/tests/test_conversation_service.py`:
   - Test full GUIDANCE → RESOLUTION_CHECK → COMPLAINT_OFFER → DETAIL_COLLECTION → COMPLAINT_CONFIRM → COMPLETE phase transitions
   - Test that complaint is NOT submitted without user confirmation
   - Test out-of-scope input returns graceful message
5. Write `backend/tests/test_complaint_service.py` — test complaint ID format, `routed_to` assignment, persistence, and status retrieval
6. Write `backend/tests/test_guardrails.py` — test PII sanitization, output safety check, and scope filtering
7. Write `backend/tests/test_api.py` with `TestClient` integration tests:
   - `POST /api/chat` returns correct structure
   - `POST /api/complaints` returns complaint ID with disclaimer
   - `GET /api/complaints/{id}` returns correct status
8. Create `docs/e2e-test-scenarios.md` with 10 manual scenarios covering: water campus guidance, air city complaint full flow, waste campus resolved (no complaint), out-of-scope rejection, complaint status check, repeated complaint attempt without confirmation

**Relevant Context:**
- Mock `WatsonxLLMService` in all tests to avoid real API calls and costs.
- Use `pytest-asyncio` if async endpoints are used.
- The phase-transition test in `test_conversation_service.py` is the most critical test — it validates the core Responsible AI workflow guarantee.

---

## Data Flow Summary

```
User Input
  → POST /api/chat
    → ConversationService.process_message()
      → GuardrailService.is_in_scope()         [RAI gate 1]
      → LLMService.classify_intent()            [intent + category + scope]
      → RAGService.retrieve()                   [grounded context chunks]
      → LLMService.generate_response()          [grounded LLM response]
      → GuardrailService.check_output_safety()  [RAI gate 2]
    → ChatResponse (with classification + optional complaint_draft)
  ← Frontend displays response

User confirms complaint
  → POST /api/complaints
    → ComplaintService.register()
      → GuardrailService.sanitize_complaint_text()  [RAI gate 3]
      → SQLite persist
      → return CIV-XXXXX-XXXXX (simulated ID)
    ← ComplaintResponse with disclaimer
```

---

## Responsible AI Principles Mapping

| Principle | Implementation |
|---|---|
| Privacy | PII sanitization before storage; no raw conversation logs stored |
| Transparency | AI banner in UI; disclaimer on all complaint responses; system prompt states AI identity |
| Fairness | Uniform treatment regardless of location; same guidance quality for campus/city |
| Human Oversight | Complaint confirmation gate; user can cancel at any point; no auto-submission |
| No Invented Facts | RAG grounding; output safety check; system prompt prohibition |

---

## SDG Alignment

| SDG | Relevance |
|---|---|
| SDG 11 — Sustainable Cities and Communities | Core mission: empowering citizens to report and resolve urban sustainability issues |
| SDG 6 — Clean Water and Sanitation | Water management category: guidance on water quality, conservation, and supply issues |
| SDG 12 — Responsible Consumption and Production | Waste management category: guidance on segregation, recycling, and reducing waste |
| SDG 13 — Climate Action | Air pollution category: guidance on emissions, AQI awareness, and pollution reduction |
