"""
backend/test_policy_rag.py — Unit & Integration tests for Policy RAG / Knowledge Layer.

Run:
    .venv\\Scripts\\python.exe -m pytest backend/test_policy_rag.py -v
"""

from pathlib import Path
from knowledge.models import PolicyChunk, PolicyContext
from knowledge.retriever import PolicyKnowledgeBase, PolicyRetriever, POLICIES_DIR, CONFIDENCE_THRESHOLD


def test_policy_rag_suite():
    print("\n=================================================")
    print("  SupportFlow AI — Policy RAG Layer Tests")
    print("=================================================\n")

    # 1. Policy files load successfully
    kb = PolicyKnowledgeBase()
    assert len(kb.chunks) > 0, "Policy chunks should be loaded"

    # 2. All 6 policy categories are available
    loaded_categories = {chunk.category for chunk in kb.chunks}
    expected_categories = {"refund", "return", "replacement", "delivery", "payment", "account"}
    assert expected_categories.issubset(loaded_categories), f"Missing categories. Found: {loaded_categories}"

    # 3. Refund query retrieves refund policy
    ctx_ref = PolicyRetriever.retrieve_policy("I want a refund for my cancelled order")
    assert ctx_ref.requires_policy_review is False
    assert ctx_ref.top_policy is not None
    assert ctx_ref.top_policy.category == "refund"
    assert ctx_ref.top_policy.source == "refund_policy.txt"

    # 4. Return query retrieves return policy
    ctx_ret = PolicyRetriever.retrieve_policy("I want to return my delivered product within return window")
    assert ctx_ret.requires_policy_review is False
    assert ctx_ret.top_policy is not None
    assert ctx_ret.top_policy.category == "return"
    assert ctx_ret.top_policy.source == "return_policy.txt"

    # 5. Replacement query retrieves replacement policy
    ctx_rep = PolicyRetriever.retrieve_policy("My delivered product is damaged and I want another replacement")
    assert ctx_rep.requires_policy_review is False
    assert ctx_rep.top_policy is not None
    assert ctx_rep.top_policy.category == "replacement"
    assert ctx_rep.top_policy.source == "replacement_policy.txt"

    # 6. Delivery query retrieves delivery policy
    ctx_del = PolicyRetriever.retrieve_policy("My package is late and tracking status is delayed")
    assert ctx_del.requires_policy_review is False
    assert ctx_del.top_policy is not None
    assert ctx_del.top_policy.category == "delivery"
    assert ctx_del.top_policy.source == "delivery_policy.txt"

    # 7. Payment query retrieves payment policy
    ctx_pay = PolicyRetriever.retrieve_policy("Payment failed but money was debited from my bank account")
    assert ctx_pay.requires_policy_review is False
    assert ctx_pay.top_policy is not None
    assert ctx_pay.top_policy.category == "payment"
    assert ctx_pay.top_policy.source == "payment_policy.txt"

    # 8. Account query retrieves account policy
    ctx_acc = PolicyRetriever.retrieve_policy("I cannot access my registered customer email account")
    assert ctx_acc.requires_policy_review is False
    assert ctx_acc.top_policy is not None
    assert ctx_acc.top_policy.category == "account"
    assert ctx_acc.top_policy.source == "account_policy.txt"

    # 9. Results contain relevance scores
    assert ctx_ref.retrieval_confidence > 0.0
    assert ctx_ref.top_policy.relevance_score > 0.0

    # 10. Results are deterministically ordered
    ctx_multi = PolicyRetriever.retrieve_policy("refund policy cancellation", top_k=3)
    scores = [c.relevance_score for c in ctx_multi.matched_policies]
    assert scores == sorted(scores, reverse=True), "Scores must be descending"

    # 11. Empty query is handled safely
    ctx_empty = PolicyRetriever.retrieve_policy("   ")
    assert ctx_empty.requires_policy_review is True
    assert ctx_empty.top_policy is None
    assert ctx_empty.retrieval_confidence == 0.0

    # 12 & 13. Unknown/unrelated query does not fabricate policy and sets requires_policy_review
    ctx_weather = PolicyRetriever.retrieve_policy("What is the weather today?")
    assert ctx_weather.requires_policy_review is True
    assert ctx_weather.top_policy is None
    assert ctx_weather.retrieval_confidence < CONFIDENCE_THRESHOLD

    # 14. top_k works correctly
    ctx_top2 = PolicyRetriever.retrieve_policy("delivered order return replacement refund", top_k=2)
    assert len(ctx_top2.matched_policies) <= 2

    # 15. Original policy files remain unchanged
    policy_files = [f for f in POLICIES_DIR.glob("*.txt")]
    assert len(policy_files) == 6

    print("\n=================================================")
    print("  Policy RAG Layer Tests Passed: 15/15")
    print("=================================================\n")


if __name__ == "__main__":
    test_policy_rag_suite()
