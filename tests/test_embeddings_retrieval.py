"""
Unit tests for Reference-Permitted Embedding Services and Vector Retrieval.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import math
import pytest
from src.core.embeddings import DomainEquivalentEmbeddingService, EmbeddingServiceFactory


def test_embedding_factory_returns_permitted_options():
    svc = EmbeddingServiceFactory.create(provider="domain_equivalent")
    assert isinstance(svc, DomainEquivalentEmbeddingService)
    assert svc.dimension == 128


def test_vector_normalization_and_dimension():
    svc = DomainEquivalentEmbeddingService(dimension=128)
    texts = [
        "ISO 14229 Service 0x10 Diagnostic Session Control Default Session",
        "Service 0x27 Security Access Request Seed Send Key"
    ]
    vectors = svc.embed_texts(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 128
    assert len(vectors[1]) == 128

    # L2 norm must be 1.0 (unit vector)
    norm0 = math.sqrt(sum(x * x for x in vectors[0]))
    norm1 = math.sqrt(sum(x * x for x in vectors[1]))
    assert pytest.approx(norm0, 0.001) == 1.0
    assert pytest.approx(norm1, 0.001) == 1.0


def test_semantic_cosine_similarity():
    svc = DomainEquivalentEmbeddingService(dimension=128)
    
    query_vec = svc.embed_query("diagnostic session control default")
    match_vec = svc.embed_query("ISO 14229 Service 0x10 Diagnostic Session Control")
    unrelated_vec = svc.embed_query("chassis steering wheel mechanical bolt torque")

    # Dot product of normalized vectors = cosine similarity
    sim_match = sum(q * m for q, m in zip(query_vec, match_vec))
    sim_unrelated = sum(q * u for q, u in zip(query_vec, unrelated_vec))

    # Relevant domain text must score significantly higher than unrelated text
    assert sim_match > sim_unrelated
