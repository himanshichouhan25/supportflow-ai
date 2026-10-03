"""
knowledge/retriever.py — Deterministic Policy Retriever for SupportFlow AI RAG Layer.
"""

import os
import re
import math
from pathlib import Path
from typing import Any

from knowledge.models import PolicyChunk, PolicyContext

# Fixed application configuration for policy directory to prevent path traversal
BASE_DIR = Path(__file__).resolve().parent
POLICIES_DIR = BASE_DIR / "policies"
CONFIDENCE_THRESHOLD = 0.15

# Category keyword mappings for context boosting
CATEGORY_KEYWORDS = {
    "refund": {"refund", "refunds", "refunded", "cancellation", "cancelled", "cancel", "money back"},
    "return": {"return", "returns", "returned", "sendback", "returning", "send back", "tags"},
    "replacement": {"replace", "replacement", "replacements", "exchange", "substitute", "defect", "defective", "damaged"},
    "delivery": {"delivery", "deliveries", "deliver", "delivered", "shipping", "shipped", "package", "tracking", "late", "delay", "delayed", "courier"},
    "payment": {"payment", "payments", "paid", "pay", "transaction", "upi", "card", "deducted", "debited", "charge", "charged", "bank", "gateway"},
    "account": {"account", "profile", "email", "phone", "password", "security", "customer", "access"},
}

# Stop words to ignore during scoring
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should",
    "can", "could", "for", "to", "in", "on", "at", "by", "from", "with",
    "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "to", "of", "and", "or", "not", "no", "but",
    "my", "i", "me", "my", "want", "need", "get", "please", "help", "this", "it"
}


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lower-case alphanumeric terms, ignoring stop words."""
    words = re.findall(r"\b[a-z0-9]+\b", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


class PolicyKnowledgeBase:
    """Policy Knowledge Base loader and deterministic TF-IDF search engine."""

    def __init__(self, policies_dir: Path | str | None = None) -> None:
        self.policies_dir = Path(policies_dir) if policies_dir else POLICIES_DIR
        self.chunks: list[PolicyChunk] = []
        self._load_policies()

    def _load_policies(self) -> None:
        """Scan policies directory and chunk markdown/txt policy documents safely."""
        self.chunks.clear()

        if not self.policies_dir.exists() or not self.policies_dir.is_dir():
            return

        for filename in sorted(os.listdir(self.policies_dir)):
            if not filename.endswith(".txt"):
                continue

            filepath = self.policies_dir / filename
            category = filename.replace("_policy.txt", "").replace(".txt", "").lower()

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # Split file into sections by markdown header '## '
            sections = re.split(r"\n(?=##\s+)", content)
            file_title = filename

            for idx, section in enumerate(sections):
                section_str = section.strip()
                if not section_str:
                    continue

                lines = section_str.splitlines()
                header = lines[0].replace("#", "").strip() if lines else f"Section {idx + 1}"
                chunk_id = f"{category}_chunk_{idx + 1}"

                self.chunks.append(
                    PolicyChunk(
                        policy_id=chunk_id,
                        category=category,
                        title=header,
                        content=section_str,
                        source=filename,
                        relevance_score=0.0,
                    )
                )

    def search(self, query: str, top_k: int = 3) -> PolicyContext:
        """
        Search policy knowledge base deterministically for a user query.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return PolicyContext(
                query=query,
                matched_policies=[],
                top_policy=None,
                retrieval_confidence=0.0,
                requires_policy_review=True,
            )

        query_tokens = _tokenize(cleaned_query)
        lower_query = cleaned_query.lower()

        if not query_tokens:
            return PolicyContext(
                query=query,
                matched_policies=[],
                top_policy=None,
                retrieval_confidence=0.0,
                requires_policy_review=True,
            )

        scored_chunks: list[tuple[float, PolicyChunk]] = []

        for chunk in self.chunks:
            score = self._compute_similarity(lower_query, query_tokens, chunk)
            if score > 0.0:
                # Create duplicate chunk instance with assigned relevance score
                chunk_copy = chunk.model_copy()
                chunk_copy.relevance_score = round(score, 4)
                scored_chunks.append((score, chunk_copy))

        # Sort by relevance score descending, then by policy_id ascending for determinism
        scored_chunks.sort(key=lambda item: (-item[0], item[1].policy_id))

        top_matches = [chunk for _, chunk in scored_chunks[:top_k]]
        top_score = top_matches[0].relevance_score if top_matches else 0.0

        requires_review = top_score < CONFIDENCE_THRESHOLD or len(top_matches) == 0

        return PolicyContext(
            query=query,
            matched_policies=top_matches,
            top_policy=top_matches[0] if (top_matches and not requires_review) else None,
            retrieval_confidence=top_score,
            requires_policy_review=requires_review,
        )

    def _compute_similarity(self, lower_query: str, query_tokens: list[str], chunk: PolicyChunk) -> float:
        """Calculate deterministic relevance score for a chunk against query terms."""
        chunk_text = f"{chunk.title} {chunk.content}".lower()
        chunk_tokens = _tokenize(chunk_text)

        if not chunk_tokens:
            return 0.0

        # Term overlap & Term Frequency
        term_matches = 0
        total_query_tokens = len(query_tokens)

        for q_term in query_tokens:
            if q_term in chunk_text:
                term_matches += chunk_text.count(q_term)

        base_score = term_matches / (len(chunk_tokens) + 10)

        # Title bonus
        title_boost = 0.0
        for q_term in query_tokens:
            if q_term in chunk.title.lower():
                title_boost += 0.2

        # Category keyword boost
        category_boost = 0.0
        cat_keywords = CATEGORY_KEYWORDS.get(chunk.category, set())
        for kw in cat_keywords:
            if kw in lower_query:
                category_boost += 0.35

        total_score = base_score + title_boost + category_boost

        # Cap score normalized between 0.0 and 1.0
        return min(1.0, max(0.0, total_score))


class PolicyRetriever:
    """Convenience Wrapper for Policy Knowledge Retrieval."""

    _instance: PolicyKnowledgeBase | None = None

    @classmethod
    def get_instance(cls) -> PolicyKnowledgeBase:

        if cls._instance is None:
            cls._instance = PolicyKnowledgeBase()
        return cls._instance

    @classmethod
    def retrieve_policy(cls, query: str, top_k: int = 3) -> PolicyContext:
        """Static retrieval interface."""
        return cls.get_instance().search(query, top_k=top_k)
