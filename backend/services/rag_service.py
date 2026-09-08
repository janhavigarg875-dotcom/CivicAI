"""
RAGService — local retrieval-augmented generation pipeline.

Loads the 6 curated Markdown knowledge base documents, chunks them,
embeds them with sentence-transformers, and indexes them in FAISS.

Public API:
    rag_service.retrieve(query, category, scope, top_k) -> list[str]

Design notes:
- Each chunk carries metadata (category, scope, source) stored in parallel lists.
- FAISS IndexFlatL2 is used — exact search, no approximation, sufficient for
  a small KB (< 1000 chunks).
- The index is built once at import time (module-level singleton) and can
  optionally be persisted to disk to avoid rebuilding on every restart.
- The embedding model is loaded lazily on first retrieve() call so that unit
  tests that never call retrieve() don't incur the download cost.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Knowledge base document registry
# ---------------------------------------------------------------------------
_KB_DIR = Path(__file__).parent.parent / "knowledge_base"

# Each entry maps a filename to its (category, scope) metadata
_KB_FILES: list[tuple[str, str, str]] = [
    ("water_campus.md", "WATER", "CAMPUS"),
    ("water_city.md",   "WATER", "CITY"),
    ("air_campus.md",   "AIR",   "CAMPUS"),
    ("air_city.md",     "AIR",   "CITY"),
    ("waste_campus.md", "WASTE", "CAMPUS"),
    ("waste_city.md",   "WASTE", "CITY"),
]

# Approximate target chunk size (in characters)
_CHUNK_SIZE = 800
# Overlap between consecutive chunks (in characters)
_CHUNK_OVERLAP = 100

# Embedding model — small, fast, good quality
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Optional path to persist / load the FAISS index
_INDEX_DIR = _KB_DIR / "index"


@dataclass
class _Chunk:
    text: str
    category: str   # WATER | AIR | WASTE
    scope: str      # CAMPUS | CITY
    source: str     # filename


# ---------------------------------------------------------------------------
# RAGService
# ---------------------------------------------------------------------------
class RAGService:
    """
    Local FAISS-backed retrieval service for the CivicAI knowledge base.
    """

    def __init__(self) -> None:
        self._chunks: list[_Chunk] = []
        self._embeddings: Optional[np.ndarray] = None  # shape (N, D)
        self._index = None          # faiss.Index — typed as Any to avoid import at module level
        self._embed_model = None    # SentenceTransformer — lazy loaded
        self._ready = False

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def build(self) -> None:
        """
        Load documents, chunk, embed, and build FAISS index.
        Call once at application startup.
        """
        logger.info("RAGService: loading knowledge base from %s", _KB_DIR)
        self._chunks = self._load_and_chunk_documents()
        logger.info("RAGService: %d chunks loaded", len(self._chunks))

        model = self._get_embed_model()
        texts = [c.text for c in self._chunks]
        self._embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        logger.info("RAGService: embeddings computed, shape=%s", self._embeddings.shape)

        self._index = self._build_faiss_index(self._embeddings)
        self._ready = True
        logger.info("RAGService: FAISS index ready")

    def retrieve(
        self,
        query: str,
        category: Optional[str] = None,
        scope: Optional[str] = None,
        top_k: int = 4,
    ) -> list[str]:
        """
        Return the top_k most relevant chunk texts for the query.

        If category and/or scope are provided, retrieval is performed
        against the full index first, then results are filtered to only
        chunks that match the requested category/scope. If fewer than
        top_k filtered results are found, the unfiltered top results
        are included as a fallback so the LLM always has some context.
        """
        if not self._ready:
            logger.warning("RAGService.retrieve() called before build(); returning empty list")
            return []

        model = self._get_embed_model()
        query_vec = model.encode([query], convert_to_numpy=True)  # shape (1, D)

        # Search a larger pool so filtering still leaves enough results
        search_k = min(top_k * 6, len(self._chunks))
        distances, indices = self._index.search(query_vec, search_k)

        candidates: list[tuple[float, _Chunk]] = [
            (float(distances[0][i]), self._chunks[idx])
            for i, idx in enumerate(indices[0])
            if idx >= 0
        ]

        # Apply metadata filter
        filtered = [
            (dist, chunk) for dist, chunk in candidates
            if (category is None or chunk.category == category)
            and (scope is None or chunk.scope == scope)
        ]

        # Fallback: if filtering left too few results, supplement with unfiltered
        if len(filtered) < top_k:
            seen_texts = {c.text for _, c in filtered}
            for dist, chunk in candidates:
                if chunk.text not in seen_texts:
                    filtered.append((dist, chunk))
                    seen_texts.add(chunk.text)
                if len(filtered) >= top_k:
                    break

        # Sort by distance (ascending = most similar) and return text
        filtered.sort(key=lambda x: x[0])
        return [chunk.text for _, chunk in filtered[:top_k]]

    # ------------------------------------------------------------------
    # Private: document loading and chunking
    # ------------------------------------------------------------------
    def _load_and_chunk_documents(self) -> list[_Chunk]:
        chunks: list[_Chunk] = []
        for filename, category, scope in _KB_FILES:
            path = _KB_DIR / filename
            if not path.exists():
                logger.warning("Knowledge base file not found: %s", path)
                continue
            text = path.read_text(encoding="utf-8")
            file_chunks = self._chunk_text(text)
            for chunk_text in file_chunks:
                chunks.append(_Chunk(text=chunk_text, category=category, scope=scope, source=filename))
        return chunks

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        """
        Split text into overlapping chunks.

        Strategy:
        1. Split on Markdown headings (##, ###) and blank lines first to
           respect document structure.
        2. If a section is still longer than _CHUNK_SIZE, split it further
           by sentence boundaries.
        3. Apply a sliding window with _CHUNK_OVERLAP to maintain context.
        """
        # Split on double newlines (paragraph boundaries)
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            # Skip very short paragraphs (headings alone, etc.) — attach them to next
            if len(para) < 40 and not current:
                current = para + "\n\n"
                continue

            candidate = (current + "\n\n" + para).strip() if current else para

            if len(candidate) <= _CHUNK_SIZE:
                current = candidate
            else:
                # Flush current chunk
                if current:
                    chunks.append(current.strip())
                # If the paragraph itself is large, split it by sentence
                if len(para) > _CHUNK_SIZE:
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    sent_buf = ""
                    for sent in sentences:
                        if len(sent_buf) + len(sent) + 1 <= _CHUNK_SIZE:
                            sent_buf = (sent_buf + " " + sent).strip()
                        else:
                            if sent_buf:
                                chunks.append(sent_buf)
                            sent_buf = sent
                    current = sent_buf
                else:
                    current = para

        if current:
            chunks.append(current.strip())

        # Apply overlap: prepend tail of previous chunk to next chunk
        if _CHUNK_OVERLAP > 0 and len(chunks) > 1:
            overlapped: list[str] = [chunks[0]]
            for i in range(1, len(chunks)):
                tail = chunks[i - 1][-_CHUNK_OVERLAP:]
                overlapped.append(tail + " " + chunks[i])
            return overlapped

        return chunks

    # ------------------------------------------------------------------
    # Private: embedding model
    # ------------------------------------------------------------------
    def _get_embed_model(self):
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("RAGService: loading embedding model %s", _EMBED_MODEL_NAME)
            self._embed_model = SentenceTransformer(_EMBED_MODEL_NAME)
        return self._embed_model

    # ------------------------------------------------------------------
    # Private: FAISS index construction
    # ------------------------------------------------------------------
    @staticmethod
    def _build_faiss_index(embeddings: np.ndarray):
        import faiss  # imported here to keep it optional at module load
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        # FAISS requires float32
        index.add(embeddings.astype(np.float32))
        return index


# ---------------------------------------------------------------------------
# Module-level singleton — imported by ConversationService
# ---------------------------------------------------------------------------
rag_service = RAGService()
