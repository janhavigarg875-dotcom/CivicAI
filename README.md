# CivicAI — AI Sustainability Assistant

CivicAI is an AI-powered sustainability assistant built for campus students and city/community citizens. It helps users navigate Water, Air, and Waste management issues by providing grounded guidance and — when a problem remains unresolved — facilitating a **simulated** complaint registration process. The system aligns with **SDG 11** (Sustainable Cities and Communities) as its primary goal, with supporting alignment to **SDG 6** (Clean Water and Sanitation), **SDG 12** (Responsible Consumption and Production), and **SDG 13** (Climate Action). All LLM interactions are powered by IBM watsonx.ai using the `ibm/granite-4-h-small` model.

> **Responsible AI Notice:** Complaint submissions are simulated. No real authorities are contacted. The assistant is transparent about its AI identity at all times.

---

## Prerequisites

| Tool | Minimum Version |
|------|----------------|
| Node.js | 18.x or later |
| Python | 3.11 or later |
| pip | 23.x or later |

---

## Project Structure

```
CivicAI/
├── frontend/          # React + TypeScript SPA (Vite + Tailwind)
├── backend/           # FastAPI Python application
│   ├── api/           # Route handlers
│   ├── core/          # Config, constants, enums
│   ├── services/      # LLM, RAG, classifier, complaint services
│   ├── models/        # SQLAlchemy ORM models
│   ├── schemas/       # Pydantic request/response schemas
│   ├── db/            # Database setup
│   └── knowledge_base/ # Curated Markdown/JSON documents
└── docs/              # Architecture notes and ADRs
```

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd CivicAI
```

### 2. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your environment file from the example
cp .env.example .env
# Edit .env and fill in your IBM watsonx.ai credentials
```

### 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Create your environment file from the example
cp .env.example .env
# Edit .env if you need a non-default API URL
```

---

## Running the Application

### Start the backend

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.  
Health check: `GET http://localhost:8000/health` → `{"status": "ok", "service": "CivicAI"}`  
Interactive docs: `http://localhost:8000/docs`

### Start the frontend

```bash
cd frontend
npm run dev
```

The app will be available at `http://localhost:5173`.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `WATSONX_API_KEY` | Your IBM watsonx.ai API key |
| `WATSONX_PROJECT_ID` | Your IBM watsonx.ai project ID |
| `WATSONX_URL` | watsonx.ai endpoint (default: `https://us-south.ml.cloud.ibm.com`) |
| `MODEL_ID` | LLM model ID (default: `ibm/granite-3-8b-instruct`) |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend base URL (default: `http://localhost:8000`) |

> **Important:** Never commit your `.env` files. They are listed in `.gitignore`.  
> Always copy `.env.example` → `.env` and fill in your credentials.

---

## SDG Alignment

| SDG | Relevance |
|-----|-----------|
| **SDG 11** — Sustainable Cities and Communities | Core mission: empowering citizens to report and resolve urban sustainability issues |
| **SDG 6** — Clean Water and Sanitation | Water management category: guidance on water quality, conservation, and supply issues |
| **SDG 12** — Responsible Consumption and Production | Waste management category: guidance on segregation, recycling, and reducing waste |
| **SDG 13** — Climate Action | Air pollution category: guidance on emissions, AQI awareness, and pollution reduction |

---

## License

MIT
