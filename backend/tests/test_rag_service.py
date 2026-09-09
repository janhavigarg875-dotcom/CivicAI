"""
Tests for RAGService — chunk loading, metadata filtering, and retrieval fallback.
No real FAISS index is used in all tests; a small in-memory index is built from
synthetic documents to keep tests fast and independent of the real KB files.
"""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np


class TestRAGChunking:
    """Unit tests for the text chunking logic."""

    def test_short_text_produces_single_chunk(self):
        from services.rag_service import RAGService
        svc = RAGService()
        text = "This is a short paragraph about water leaks on campus."
        chunks = svc._chunk_text(text)
        assert len(chunks) >= 1
        assert "water leaks" in chunks[0]

    def test_long_text_produces_multiple_chunks(self):
        from services.rag_service import RAGService
        svc = RAGService()
        # Build a text clearly larger than _CHUNK_SIZE (800 chars)
        paragraph = "Water leaks should be reported immediately to campus facilities. " * 5
        text = "\n\n".join([paragraph] * 6)
        chunks = svc._chunk_text(text)
        assert len(chunks) >= 2

    def test_chunks_are_non_empty(self):
        from services.rag_service import RAGService
        svc = RAGService()
        text = "Paragraph one about water.\n\nParagraph two about air.\n\nParagraph three about waste."
        chunks = svc._chunk_text(text)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_empty_text_produces_no_chunks(self):
        from services.rag_service import RAGService
        svc = RAGService()
        chunks = svc._chunk_text("")
        assert chunks == []


class TestRAGRetrieval:
    """Integration-style tests for retrieve() using a real mini FAISS index."""

    @pytest.fixture(autouse=True)
    def build_mini_index(self):
        """Build a tiny RAG index from synthetic documents."""
        from services.rag_service import RAGService, _Chunk
        import faiss

        self.svc = RAGService()
        # Synthetic chunks with known category/scope
        self.svc._chunks = [
            _Chunk("Water leak in bathroom pipe needs repair", "WATER", "CAMPUS", "water_campus.md"),
            _Chunk("Report water supply outage to municipal helpline", "WATER", "CITY", "water_city.md"),
            _Chunk("HVAC ventilation failure causes poor indoor air quality", "AIR", "CAMPUS", "air_campus.md"),
            _Chunk("Traffic emissions cause high AQI in the city", "AIR", "CITY", "air_city.md"),
            _Chunk("Overflowing bins should be reported to housekeeping", "WASTE", "CAMPUS", "waste_campus.md"),
            _Chunk("Illegal dumping near residential area violates regulations", "WASTE", "CITY", "waste_city.md"),
        ]
        # Build a real embedding + FAISS index on these 6 chunks
        model = self.svc._get_embed_model()
        texts = [c.text for c in self.svc._chunks]
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        self.svc._embeddings = embeddings
        self.svc._index = self.svc._build_faiss_index(embeddings)
        self.svc._ready = True

    def test_retrieve_returns_list(self):
        results = self.svc.retrieve("water leak in dorm", top_k=2)
        assert isinstance(results, list)
        assert len(results) == 2

    def test_retrieve_water_campus_filter(self):
        results = self.svc.retrieve(
            "water pipe leaking", category="WATER", scope="CAMPUS", top_k=1
        )
        assert len(results) >= 1
        assert "water" in results[0].lower() or "pipe" in results[0].lower()

    def test_retrieve_air_city_filter(self):
        results = self.svc.retrieve(
            "city air pollution from cars", category="AIR", scope="CITY", top_k=1
        )
        assert len(results) >= 1
        assert "aqi" in results[0].lower() or "traffic" in results[0].lower() or "emissions" in results[0].lower()

    def test_retrieve_with_no_filter_returns_best_match(self):
        # No category/scope filter — should still return results
        results = self.svc.retrieve("overflowing garbage bins", top_k=2)
        assert len(results) >= 1

    def test_retrieve_fallback_when_filter_too_narrow(self):
        # AIR/CITY filter on a waste query — should fall back to unfiltered results
        results = self.svc.retrieve(
            "illegal dumping of waste", category="AIR", scope="CITY", top_k=3
        )
        assert len(results) >= 1  # fallback ensures something is always returned

    def test_retrieve_before_build_returns_empty(self):
        from services.rag_service import RAGService
        unbuilt = RAGService()
        results = unbuilt.retrieve("anything")
        assert results == []
