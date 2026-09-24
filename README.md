# SupportFlow AI

**Multi-Agent Customer Support Resolution System**

---

## 1. Overview

SupportFlow AI is an agentic AI prototype that resolves e-commerce customer support issues using a multi-agent architecture.

Instead of a single monolithic model, the system uses a **Coordinator Agent** that understands the customer request, routes it to the correct **Specialist Agent**, calls a **deterministic database tool**, observes the result, and **replans** if the issue requires more than one specialist to resolve.

Supported support categories:

| Category | Example Request |
|---|---|
| **Orders** | "Where is my order ORD005?" |
| **Payments** | "Was my payment successful for ORD005?" |
| **Delivery** | "Track my package for ORD009" |
| **Accounts** | "What email is registered for C101?" |

---

## 2. Problem Statement

This project addresses **PS-08 — Customer Support Resolution Agent** from the college hackathon.

The problem requires building a system that:

1. Receives a customer support request in natural language
2. **Understands** the core problem
3. **Selects** an appropriate action or tool
4. **Uses** the tool to retrieve real information
5. **Decides** whether another action is needed
6. Produces a **final, grounded response**

SupportFlow AI implements this loop end-to-end using a Coordinator + Specialist architecture backed by a real PostgreSQL database.

---

## 3. Key Features

- **Multi-agent architecture** — Coordinator routes to one or more Specialists
- **Coordinator / Supervisor Agent** — orchestrates the full workflow
- **Four Specialist Agents** — Order, Payment, Delivery, Account
- **Deterministic database tools** — all data lookups use PostgreSQL, not LLM imagination
- **Automatic replanning** — Coordinator observes results and decides if a second Specialist is needed
- **Workflow trace** — every step is recorded and displayed in the UI
- **PostgreSQL persistence** — real seeded e-commerce data (customers, orders, payments, deliveries)
- **Streamlit dashboard** — visualises the multi-agent workflow in real time
- **Gemini AI integration (optional)** — natural-language final responses when `GEMINI_API_KEY` is set
- **Offline fallback** — system works fully without any API key using deterministic response templates

---

## 4. Architecture

```
Customer Message
        │
        ▼
┌───────────────────┐
│  Coordinator      │  ← Intent detection + routing
│  Agent            │
└────────┬──────────┘
         │
    ┌────▼─────────────────────────────────┐
    │  Specialist Agent (one or more)       │
    │                                       │
    │  📦 Order Agent                       │
    │  💳 Payment Agent                     │
    │  🚚 Delivery Agent                    │
    │  👤 Account Agent                     │
    └────────────┬──────────────────────────┘
                 │
         ┌───────▼────────┐
         │ Deterministic  │  ← No LLM involved here
         │ Tool (Python)  │
         └───────┬────────┘
                 │
         ┌───────▼────────┐
         │  PostgreSQL    │
         │  Database      │
         └───────┬────────┘
                 │
         ┌───────▼────────┐
         │  Observation   │  ← Coordinator reads the result
         └───────┬────────┘
                 │
       ┌─────────▼──────────┐
       │  Replan if needed  │  ← Call another Specialist?
       └─────────┬──────────┘
                 │
         ┌───────▼────────┐
         │ Final Response │  ← Gemini or deterministic template
         └────────────────┘
```

Maximum **3 specialist calls** per request to prevent runaway loops.

---

## 5. Agent Responsibilities

| Agent | Responsibility | Allowed Tools |
|---|---|---|
| **Order Agent** | Order lookup and cancellation | `check_order`, `cancel_order` |
| **Payment Agent** | Payment status and refund eligibility | `check_payment`, `check_refund_eligibility` |
| **Delivery Agent** | Delivery tracking | `check_delivery` |
| **Account Agent** | Customer profile lookup | `check_account` |

Each agent is given access **only** to its own tools — cross-agent tool access is not permitted.

---

## 6. Agentic Workflow

```
Understand → Route → Tool → Observe → Replan → Resolve
```

### Example A — Payment + Order (multi-agent with replanning)

> *"My payment was successful but my iPhone 15 order ORD005 is still pending."*

```
Coordinator         detects: payment + order intents
    ↓
Payment Agent       calls: check_payment(ORD005)
    ↓
Coordinator         observes: payment SUCCESS
                    replans:  order status still needed
    ↓
Order Agent         calls: check_order(ORD005)
    ↓
Coordinator         builds combined final response
```

### Example B — Cancel + Refund (multi-agent with replanning)

> *"Cancel my order ORD007 and check whether I can get a refund."*

```
Coordinator         detects: order + payment intents
    ↓
Order Agent         calls: cancel_order(ORD007)
    ↓
Coordinator         observes: order CANCELLED
                    replans:  refund check needed
    ↓
Payment Agent       calls: check_refund_eligibility(ORD007)
    ↓
Coordinator         builds combined final response
```

### Example C — Delivery (single agent)

> *"Where is my package for ORD009?"*

```
Coordinator     detects: delivery intent
    ↓
Delivery Agent  calls: check_delivery(ORD009)
    ↓
Coordinator     builds final response (status: DELAYED)
```

---

## 7. Tools

All tools are **deterministic Python functions** that query PostgreSQL directly.
The LLM **never** invents order statuses, payment amounts, or delivery dates.

| Tool | Description |
|---|---|
| `check_order(order_id, db)` | Returns order status, quantity, total, timestamps |
| `cancel_order(order_id, db)` | Cancels the order if status allows; returns result |
| `check_payment(order_id, db)` | Returns payment status, amount, method |
| `check_refund_eligibility(order_id, db)` | Checks business rules: must be CANCELLED + REFUNDED payment |
| `check_delivery(order_id, db)` | Returns delivery status, tracking ID, expected date |
| `check_account(customer_id, db)` | Returns customer name, email, phone, account status |

---

## 8. Tech Stack

| Component | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Database | PostgreSQL 18 |
| ORM | SQLAlchemy 2.x (typed `Mapped` style) |
| DB Driver | psycopg 3 |
| Configuration | pydantic-settings (`.env` file) |
| Frontend | Streamlit 1.64 |
| AI (optional) | Google Gemini 1.5 Flash via `google-generativeai` |
| Language | Python 3.12+ |

---

## 9. Project Structure

```
ai-customer-support-agent/
│
├── backend/
│   ├── config.py          # Loads settings from .env
│   ├── database.py        # SQLAlchemy engine, SessionLocal, Base
│   ├── main.py            # FastAPI app + /health + /db-health
│   ├── seed_data.py       # Seeds 5 customers, 10 products, 10 orders…
│   ├── models/
│   │   ├── customer.py
│   │   ├── product.py
│   │   ├── order.py
│   │   ├── payment.py
│   │   └── delivery.py
│   ├── test_tools.py      # Tool integration tests (26 tests)
│   ├── test_agents.py     # Specialist agent tests (43 tests)
│   └── test_coordinator.py # Coordinator tests (31 tests)
│
├── agents/
│   ├── llm_provider.py    # Gemini wrapper with offline fallback
│   ├── coordinator.py     # Orchestrator: routing + replanning
│   ├── order_agent.py
│   ├── payment_agent.py
│   ├── delivery_agent.py
│   ├── account_agent.py
│   └── __init__.py
│
├── tools/
│   ├── order_tool.py
│   ├── payment_tool.py
│   ├── delivery_tool.py
│   ├── account_tool.py
│   └── __init__.py
│
├── frontend/
│   ├── app.py             # Streamlit main application
│   └── components.py      # Reusable UI render functions
│
├── .env.example           # Template — copy to .env
├── requirements.txt
└── README.md
```

---

## 10. Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 18 running locally
- A database named `ai_customer_support` created

```sql
CREATE DATABASE ai_customer_support;
```

### Install

```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Configure environment

```powershell
# Copy the example file
Copy-Item .env.example .env
```

Edit `.env` with your values:

```
DATABASE_URL=postgresql+psycopg://postgres:yourpassword@localhost:5432/ai_customer_support
GEMINI_API_KEY=your_gemini_api_key_here
```

> **Note:** `GEMINI_API_KEY` is optional. The system runs fully offline without it.
> Never commit your `.env` file to source control.

### Seed demo data

```powershell
.\.venv\Scripts\python.exe -m backend.seed_data
```

This inserts 5 customers, 10 products, 10 orders, 10 payments, and 8 deliveries.
The script is safe to rerun (idempotent).

---

## 11. Run

### Backend (FastAPI)

```powershell
.\.venv\Scripts\uvicorn.exe backend.main:app --reload
```

Health checks:
- `GET http://localhost:8000/health` → `{"status": "ok"}`
- `GET http://localhost:8000/db-health` → `{"database": "connected"}`

### Frontend (Streamlit)

```powershell
.\.venv\Scripts\streamlit.exe run frontend/app.py
```

Open **http://localhost:8501** in your browser.

---

## 12. Testing

Run all test suites from the project root:

```powershell
# Deterministic tool tests
.\.venv\Scripts\python.exe -m backend.test_tools

# Specialist agent tests
.\.venv\Scripts\python.exe -m backend.test_agents

# Coordinator tests
.\.venv\Scripts\python.exe -m backend.test_coordinator
```

### Verified results

| Suite | Tests | Result |
|---|---|---|
| `test_tools.py` | 26 | ✅ 26/26 PASS |
| `test_agents.py` | 43 | ✅ 43/43 PASS |
| `test_coordinator.py` | 31 | ✅ 31/31 PASS |
| **Total** | **100** | **✅ 100/100 PASS** |

---

## 13. Demo Scenarios

Three pre-built scenarios are available as one-click buttons in the Streamlit UI:

### Scenario 1 — Payment + Order (multi-agent + replanning)
```
Input:   "My payment was successful but my iPhone 15 order ORD005 is still pending."
Agents:  PaymentAgent → [replan] → OrderAgent
Steps:   5 workflow steps including 1 replanning step
```

### Scenario 2 — Cancel + Refund (multi-agent + replanning)
```
Input:   "Cancel my order ORD007 and check whether I can get a refund."
Agents:  OrderAgent → [replan] → PaymentAgent
Steps:   5 workflow steps including 1 replanning step
```

### Scenario 3 — Delivery Tracking (single agent)
```
Input:   "Where is my package for ORD009?"
Agents:  DeliveryAgent
Steps:   3 workflow steps, status: DELAYED
```

---

## 14. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string (`postgresql+psycopg://...`) |
| `GEMINI_API_KEY` | ⬜ Optional | Gemini AI key for natural-language responses |

**Never commit your actual `.env` to source control.**
The `.gitignore` should include `.env`.

---

## 15. Development

The project is developed incrementally with milestone-based Git commits, one task per commit:

- Task 1: FastAPI + PostgreSQL connection
- Task 2: SQLAlchemy database models
- Task 3: Demo data seeding
- Task 4: Deterministic support tools
- Task 5: Specialist agents
- Task 6: Coordinator agent
- Task 7: Streamlit dashboard

Repository: [github.com/himanshichouhan25/supportflow-ai](https://github.com/himanshichouhan25/supportflow-ai)

---

## 16. Future Improvements

The following features are **not implemented** in the current MVP but could be added:

- **Knowledge base / RAG** — product manuals, policy documents
- **Ticket creation** — persist unresolved issues to a support queue
- **Conversation history** — multi-turn chat memory
- **More support categories** — returns, warranties, billing disputes
- **Production integrations** — real order management systems, payment gateways
- **Authentication** — customer login and session management
- **Evaluation harness** — automated scoring of response quality

---

> _SupportFlow AI is a hackathon prototype using fictional demo data.
> It is not affiliated with any real e-commerce platform._
