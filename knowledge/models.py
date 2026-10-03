"""
knowledge/models.py — Data models for Policy RAG / Knowledge Layer.
"""

from pydantic import BaseModel, Field


class PolicyChunk(BaseModel):
    """Structured model representing a searchable policy document chunk."""

    policy_id: str
    category: str
    title: str
    content: str
    source: str
    relevance_score: float = 0.0


class PolicyContext(BaseModel):
    """Structured retrieval result context returned to support agents."""

    query: str
    matched_policies: list[PolicyChunk] = Field(default_factory=list)
    top_policy: PolicyChunk | None = None
    retrieval_confidence: float = 0.0
    requires_policy_review: bool = False
