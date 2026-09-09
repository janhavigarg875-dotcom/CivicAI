from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from db.database import Base, engine
from services.rag_service import rag_service

# Import all models so SQLAlchemy registers them before create_all
import models.complaint  # noqa: F401

app = FastAPI(
    title="CivicAI",
    description="AI-powered sustainability assistant for campus and city citizens.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000","https://civicai-production-213a.up.railway.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    rag_service.build()
    print("CivicAI backend started. Database tables ensured. RAG index ready.")


app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "CivicAI"}
