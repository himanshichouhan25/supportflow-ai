# SupportFlow AI — Policy Knowledge / RAG Layer

## 1. What is RAG in SupportFlow AI?
Retrieval-Augmented Generation (RAG) is a pattern that enables AI support agents to query authoritative internal knowledge documents (such as refund, return, delivery, replacement, payment, and account policies) before making resolution decisions.

## 2. Why SupportFlow AI Needs Policy Retrieval
Support policies define business rules (such as 30-day return windows, order status requirements, duplicate protection, and escalation criteria). Policy RAG provides deterministic, grounded rules to specialist agents so responses adhere to real company policy without hallucinating or fabricating rules.

## 3. Policy Document Storage & Structure
Policies are stored as plain text documents under the `knowledge/policies/` directory:
- `refund_policy.txt`: Cancellation requirements, eligibility, duplicate refund rules, escalation.
- `return_policy.txt`: Delivered-order requirement, return window, duplicate return prevention.
- `replacement_policy.txt`: Defect/damage criteria, active replacement checks, dispatch rules.
- `delivery_policy.txt`: Tracking status meanings, carrier delay policies, escalation triggers.
- `payment_policy.txt`: Payment gateway settlement rules, failed payment reversals.
- `account_policy.txt`: Customer ownership rules, security verification procedures.

## 4. How Policies Are Loaded & Chunked
The `PolicyKnowledgeBase` class scans the fixed `knowledge/policies/` directory on initialization:
1. Opens each `.txt` file safely.
2. Parses markdown section headers (`## Section Header`) into individual `PolicyChunk` objects.
3. Assigns metadata (`policy_id`, `category`, `title`, `content`, `source`).

## 5. How Retrieval & Scoring Work
When an agent or component calls `PolicyRetriever.retrieve_policy(query, top_k=3)`:
1. **Tokenization**: Normalizes query terms into lowercase alphanumeric tokens, filtering stop words.
2. **Term & Keyword Matching**: Evaluates query tokens against policy titles, headers, and section contents.
3. **Category Context Boosting**: If the query contains domain-specific intent terms (e.g. `refund`, `return`, `replacement`, `delivery`, `payment`, `account`), relevant policy categories receive context boosts.
4. **Relevance Score**: Computes a normalized relevance score between `0.0` and `1.0` for each chunk.
5. **Deterministic Sorting**: Orders results by `relevance_score` descending, breaking ties deterministically by `policy_id`.

## 6. Confidence Threshold & Low Confidence Behavior
- **Confidence Threshold**: Defined at `0.15`.
- **High Confidence**: If the top ranked chunk has `relevance_score >= 0.15`, `top_policy` is populated, `retrieval_confidence` is set to the score, and `requires_policy_review = False`.
- **Low Confidence / Unrelated Query**: If the top score is below `0.15` (or for unrelated queries like *"What is the weather today?"*), `requires_policy_review = True`, `top_policy = None`, and the system safely signals that policy coverage is insufficient rather than fabricating a false decision.

## 7. How Agents Will Consume PolicyContext
In future agent integrations, specialist agents and the Orchestrator can call:
```python
from knowledge import PolicyRetriever

context = PolicyRetriever.retrieve_policy("I want a refund for my cancelled order")
if not context.requires_policy_review and context.top_policy:
    # Ground decision using context.top_policy.content
```
This guarantees all agent decisions remain grounded in official company policy.
