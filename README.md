# Loanova — AI-Powered Loan Assistance System

Loanova is a small demonstration system for a loan-assistance workflow built with FastAPI, LangChain, LangGraph, PostgreSQL + pgvector, and OpenAI embeddings. It focuses on safe, grounded retrieval of synthetic loan knowledge and a preliminary qualification flow.

This project is intentionally designed as a demo MVP. It does not approve loans, determine actual eligibility, or issue binding financial offers. It can answer questions using a synthetic knowledge base, collect preliminary data, and route users to human follow-up when needed.

## Why this project exists

The goal is to demonstrate a production-minded AI workflow for a lending assistant while staying within the boundaries of a safe, fictional assessment environment.

Key challenges addressed in the current MVP:

- Grounded retrieval over a loan knowledge base using pgvector
- Safe refusal when a user asks for exact rates, fees, approvals, or eligibility details that are not available in the synthetic dataset
- Citation-aware responses with source metadata
- Structured qualification flow using LangGraph state transitions
- Human escalation and missing-field handling
- Dockerized local development setup with PostgreSQL persistence

## Project objectives

- Provide a safe, grounded answer layer for loan-related questions using structured knowledge retrieval
- Preserve a clear separation between demo guidance and real lending decisions
- Demonstrate LangChain + LangGraph architecture in a realistic AI workflow
- Keep the system easy to run locally and easy to review in an assessment context

## Assessment scope and verified coverage

This repository is a verified MVP for the business-loan subset of the assessment. It implements the core of Question 1 and Question 2 as a grounded voice assistant and a traceable knowledge base, with a local Dockerized demo for the business-loan workflow.

Assessment-readiness note: the Q1–Q4 code paths are implemented and covered by the repo’s regression suite, but Q4 remains a replay/local-simulation pipeline and real multilingual browser/audio validation still requires manual browser verification. The repository does not claim a production telephony backend, real ASR service, or recorded live call artifacts unless they are generated and added manually.

Verified in this codebase:

- Q1: grounded loan question handling, unsupported-financial refusal, qualification flow, human escalation, and browser-based conversation UI
- Q2: synthetic knowledge ingestion, vector indexing, retrieval, citation-aware answers, and source tracking
- Q3: localized English/Filipino/Taglish and Indonesian language detection with safe, grounded responses and localized greetings/fallbacks
- Q4: chunked live-audio replay, signal extraction, nudge generation, latency reporting, and false-positive controls for call coaching scenarios

See the actual local KB retrieval audit in [docs/q2_retrieval_evaluation.md](docs/q2_retrieval_evaluation.md).

For a compact browser-call test pack aligned to the current implementation and the assessment checklist, see [docs/call_test_plan.md](docs/call_test_plan.md).

Important limitation: the Q4 implementation is a replay-based local pipeline for demonstration and testing. It does not capture real microphone audio from a live browser or phone call, and it does not claim production-grade ASR or a real-time streaming backend. The repo clearly separates simulated/local pipeline behavior from real provider-backed streaming.

## Architecture overview

```mermaid
flowchart LR
    User[Client / API consumer / UI] --> FastAPI[FastAPI app\nbackend/app/main.py]
    FastAPI --> KB[Knowledge base layer\nbackend/app/kb/kb.py]
    FastAPI --> Graph[LangGraph qualification flow\nbackend/app/agents/loan_graph.py]
    KB --> VStore[(PostgreSQL + pgvector\nknowledge_chunks)]
    KB --> OpenAI[OpenAI Embeddings + Chat API]
    Graph --> State[Typed state\nmissing fields / objection / escalation]
    Graph --> Human[Human follow-up path]
    Data[loan_knowledge.json\ndata/raw/loan_knowledge.json] --> KB
```

## Technology stack

- FastAPI: API layer and route handlers
- LangChain + LangChain OpenAI: embeddings and LLM orchestration
- LangGraph: loan qualification workflow with typed state transitions
- PostgreSQL + pgvector: vector storage and retrieval
- Pydantic: request/response validation
- Docker Compose: local service orchestration for PostgreSQL and backend
- pytest: regression testing
- Streamlit: simple browser-based conversation interface for the existing voice-agent API

## Component responsibilities

- `backend/app/main.py`: FastAPI application, lifecycle startup, and routes
- `backend/app/db/db.py`: PostgreSQL connection management and vector extension initialization
- `backend/app/kb/kb.py`: knowledge ingestion, chunking, OpenAI embedding, pgvector retrieval, safe answer generation, and citations
- `backend/app/agents/loan_graph.py`: LangGraph qualification workflow and routing logic
- `backend/app/agents/loan_state.py`: typed state for the loan workflow
- `backend/app/agents/prompts.py`: instructional prompt text for safer assistant behavior
- `data/raw/loan_knowledge.json`: synthetic loan knowledge used by the system
- `docker-compose.yml`: PostgreSQL and backend container orchestration
- `frontend/streamlit_app.py`: browser-based conversation UI for the `/voice/conversation` API
- `frontend/requirements.txt`: frontend-only dependencies for the Streamlit app
- `tests/test_ai_assessment.py`: regression tests covering retrieval, citations, fallbacks, and workflow logic

## Repository structure

```text
.
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── agents/
│       │   ├── loan_graph.py
│       │   ├── loan_state.py
│       │   └── prompts.py
│       ├── db/
│       │   └── db.py
│       └── kb/
│           └── kb.py
├── data/
│   └── raw/
│       └── loan_knowledge.json
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── streamlit_app.py
├── tests/
│   └── test_ai_assessment.py
└── venv/
```

## Prerequisites (macOS)

Before running the project locally, ensure you have:

- macOS with a terminal shell
- Python 3.12+ (the Docker image uses Python 3.12 slim)
- Docker Desktop installed and running
- An OpenAI API key with access to the configured embeddings and chat model
- Git

## Q2 document ingestion and retrieval (verified)

The repo supports two ingestion paths:

1. JSON ingestion using the existing KB helper:

```bash
PYTHONPATH=backend python - <<'PY'
from app.kb.kb import ingest_json
result = ingest_json('data/raw/loan_knowledge.json')
print(result)
PY
```

2. Direct document upload to the backend API for supported text-like files and PDFs. The current implementation accepts `.txt`, `.md`, `.csv`, `.json`, and `.pdf` uploads, cleans obvious PII, chunks the content, embeds it, indexes it in pgvector, and makes it available to the Q1 knowledge-grounded voice flow.

```bash
curl -X POST http://localhost:8000/kb/ingest/file \
  -F "file=@./data/raw/loan_knowledge.json" \
  -F "title=Loan knowledge upload" \
  -F "category=product" \
  -F "source=uploaded://loan-knowledge"
```

Then search or answer using the existing KB routes:

```bash
curl -sS -X POST http://localhost:8000/kb/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the demo business loan intended for?"}'

curl -sS -X POST http://localhost:8000/kb/answer \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the demo business loan intended for?"}'
```

This is a minimal ingestion path for the assessment repo: the documents are parsed and indexed, then the voice agent retrieves them through the same `retrieve()`/`answer_question()` flow already used by the Q1 assistant.

## Local setup

1. Clone the repository:

```bash
git clone https://github.com/nishantsauravjha/Loanova.git
cd Loanova
```

2. Create a local environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install Python dependencies:

```bash
pip install -r backend/requirements.txt
```

4. Create a local environment file from the example:

```bash
cp .env.example .env
```

5. Edit `.env` and set your values. Keep the file local-only and do not commit secrets.

Example values:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
DATABASE_URL=postgresql://app:app_password@db:5432/assessment
```

## Docker setup

This project includes Docker Compose support for PostgreSQL, the backend service, and the Streamlit conversation UI.

Start the full stack:

```bash
docker compose up -d --build
```

This starts the PostgreSQL container, the FastAPI backend, and the frontend UI. The database is persisted with a Docker volume named `pgdata`.

To inspect backend logs:

```bash
docker compose logs --tail=60 backend
```

To inspect the frontend logs:

```bash
docker compose logs --tail=60 frontend
```

To check backend health:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The conversation frontend is available at:

```text
http://localhost:8501
```

### Verified startup flow

```bash
docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:8501/
```

If the Streamlit UI does not connect to the backend in a browser, make sure the app is running in Docker Compose and that `LOANOVA_API_URL` points to the backend service name from the container (`http://backend:8000`) or the host machine (`http://localhost:8000`) depending on where the app is started. The backend is the source of truth for the voice contract.

## Frontend conversation UI

<img width="2936" height="1460" alt="image" src="https://github.com/user-attachments/assets/89223a03-4181-41d8-8d27-572d284a4e86" />

<img width="2928" height="1476" alt="image" src="https://github.com/user-attachments/assets/a27e9396-ec4a-40ab-b099-49dc4bf62e7a" />


The Streamlit frontend in [frontend/streamlit_app.py](frontend/streamlit_app.py) connects to the existing `/voice/conversation` API and shows:

- user and assistant messages in a chat layout
- loading state while the backend answer is being generated
- visible citations and evidence when the response includes them
- a reset button for a fresh conversation
- error documentation when the backend is unavailable or rejects the request

The supported calling method for this assessment is the browser voice UI in [frontend/streamlit_app.py](frontend/streamlit_app.py). It uses the browser’s Web Speech API for transcription and speech synthesis at http://localhost:8501, not a public PSTN/VoIP telephony number. The app can be used for real browser-based testing when the local machine has a compatible browser and microphone permissions. Actual call recordings, transcripts, and outcomes must be captured manually and stored as evidence in the repo or a local testing folder.

This is not a real telephony deployment: there is no phone number, IVR stack, or production call routing in the project.

## Q4 live insight pipeline (chunked replay mode)

Loanova includes a local Q4-style insight layer in [backend/app/audio/insights.py](backend/app/audio/insights.py). It is designed to work with streamed or replayed audio chunks, extract call signals, and generate short nudge messages without breaking the grounded Q1/Q2 workflow.

### Implemented behaviors

- Real-time-style transcript assembly from audio chunks or replayed transcripts
- Signal extraction for missed cross-sell, compliance gaps, rising frustration, payment difficulties, and callback needs
- Confidence thresholds and duplicate suppression to avoid noisy or repetitive nudges
- Latency summaries with p50/p95 timing estimates for ASR, signal extraction, LLM, and delivery
- False-positive controls for ambiguous or noisy transcripts
- Optional integration with the existing voice agent via `conversation_state["live_insights"]` and the `/voice/live-insights` API

### Important limitations

- This is not a real live microphone + ASR deployment. It uses chunked replay/transcript inputs in a local demo mode.
- The current implementation does not claim real-time browser audio capture or a live call center integration.
- The latency numbers are local simulation estimates, not externally measured production metrics.
- A production deployment should replace the local replay logic with a real streaming ASR provider, a latency collector, and a persistent nudge store.

### Example request

```bash
curl -sS -X POST http://localhost:8000/voice/live-insights \
  -H 'Content-Type: application/json' \
  -d '{
    "call_id": "demo-call-001",
    "mode": "replay",
    "audio_chunks": [
      {"chunk_id": "c1", "timestamp_ms": 0, "duration_ms": 1200, "transcript": "Customer: I also have a second vehicle."},
      {"chunk_id": "c2", "timestamp_ms": 1200, "duration_ms": 1200, "transcript": "Agent: We should confirm the disclosure before proceeding."}
    ]
  }'
```

Example response fields:

```json
{
  "call_id": "demo-call-001",
  "status": "live_insights",
  "transcript": "Customer: I also have a second vehicle. Agent: We should confirm the disclosure before proceeding.",
  "signals": [
    {"category": "missed_cross_sell", "confidence": 0.94},
    {"category": "compliance_gap", "confidence": 0.77}
  ],
  "nudges": [
    {"category": "missed_cross_sell", "priority": 4, "message": "Suggest the multi-vehicle or add-on offer while the customer is still interested."}
  ],
  "latency": {
    "p50_ms": 343.0,
    "p95_ms": 522.0
  }
}
```

### Demonstrated metrics

The local pipeline reports representative latency values for the replay path on this machine. These are intentionally labeled as local estimates and not production SLA guarantees.

- ASR replay pipeline: approximately 80-150 ms per chunk summary
- Signal extraction: approximately 90-200 ms depending on transcript length
- LLM / rationale step: approximately 150-400 ms in local replay mode
- Delivery: approximately 50-100 ms for local nudge dispatch

### False-positive handling

The nudge engine is intentionally conservative:

- confidence below 0.55 is dropped
- duplicates are suppressed by category and dedupe key
- ambiguous text such as `uh`, `hmm`, or `not clear` is ignored unless a strong compliance or purchase signal is present

## API documentation

The current API is implemented in [backend/app/main.py](backend/app/main.py). The major routes are:

### Health check

```http
GET /health
```

Example:

```bash
curl http://localhost:8000/health
```

Response:

```json
{"status":"ok"}
```

### Knowledge ingestion

```http
POST /kb/ingest
```

This loads the synthetic knowledge from `data/raw/loan_knowledge.json` into the vector store and the PostgreSQL `knowledge_chunks` table.

Example:

```bash
curl -X POST http://localhost:8000/kb/ingest
```

Example response:

```json
{"ingested_records": 3, "ingested_chunks": 12}
```

### Knowledge search

```http
POST /kb/search
```

Request body:

```json
{"question":"What is the business loan for?"}
```

Response shape:

```json
{
  "results": [
    {
      "record_id": "loan_001",
      "title": "Business Loan Overview",
      "content": "The demo business loan is intended for small businesses seeking funds for working capital, equipment, or business expansion.",
      "category": "product",
      "source": "demo://loan-product-overview",
      "version": "1.0",
      "pii": false,
      "similarity": 0.87
    }
  ]
}
```

### Knowledge answer

```http
POST /kb/answer
```

Request body:

```json
{"question":"What is the APR?"}
```

Supported safety behavior: if a relevant record says exact rates and fees are unavailable, the system returns a safe fallback instead of inventing numbers.

Example response:

```json
{
  "answer": "The requested loan rates, fees, eligibility, or approvals are unavailable in the demo knowledge base. This system supports synthetic, non-binding guidance only and can collect preliminary details or arrange a human follow-up.\n\nCitations: [loan_004] Interest Rates and Fees (demo://rates-and-fees)",
  "sources": [
    {
      "record_id": "loan_004",
      "title": "Interest Rates and Fees",
      "source": "demo://rates-and-fees",
      "similarity": 0.91,
      "category": "faq"
    }
  ],
  "grounded": false
}
```

### Voice conversation agent

```http
POST /voice/conversation
```

Request body:

```json
{
  "message": "I need a loan for inventory growth.",
  "conversation_state": {}
}
```

Response shape:

```json
{
  "status": "missing_fields",
  "answer": "I need a few preliminary details before I can continue: business type, time in operation, monthly revenue, requested loan amount, and use of funds. This is a synthetic demo workflow and does not imply approval.",
  "missing_fields": ["business_type", "time_in_operation", "monthly_revenue", "requested_amount"],
  "sources": [],
  "grounded": false,
  "escalated": false
}
```

### Qualification workflow

```http
POST /agent/qualification
```

The request shape is defined by the `QualificationRequest` model in [backend/app/agents/loan_graph.py](backend/app/agents/loan_graph.py).

Example request:

```json
{
  "question": "I need a business loan.",
  "business_type": "restaurant",
  "time_in_operation": "2 years",
  "monthly_revenue": "75000",
  "requested_amount": "50000",
  "use_of_funds": "inventory"
}
```

If a field is missing, the workflow returns a structured missing-fields response rather than a guarantee.

Example response:

```json
{
  "status": "missing_fields",
  "missing_fields": ["business_type", "requested_amount"],
  "answer": "I need a few preliminary details before I can continue: business type, requested loan amount. This is a synthetic demo workflow and does not imply approval."
}
```

## Running tests

From the project root:

```bash
source venv/bin/activate
python -m pytest -q
```

The current suite checks the answer flow, citations, unsupported-rate safety behavior, the qualification workflow, and the frontend-to-backend conversation integration.

## Demo workflow

A simple end-to-end flow looks like this:

1. Start the full stack with Docker Compose.
2. Open the Streamlit interface at http://localhost:8501.
3. Ask a simple product or policy question in the chat UI.
4. Call `/kb/ingest` if you want to refresh the synthetic knowledge base.
5. Use the text input to ask about the product, a qualification detail, or a callback request.
6. If the user asks for a callback or escalates, the workflow responds with human follow-up guidance rather than making promises.

Example:

```bash
docker compose up -d --build

curl -X POST http://localhost:8000/kb/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the business loan for?"}'

curl -X POST http://localhost:8000/voice/conversation \
  -H 'Content-Type: application/json' \
  -d '{"message":"I need a business loan for inventory growth.","conversation_state":{}}'
```

## Safety boundaries and known limitations

This is a demonstration system and not a live lending system.

Current limitations and guardrails:

- Synthetic knowledge only; no real underwriting or approval logic
- No actual eligibility determination or binding financial offer generation
- No guarantee of callback scheduling unless a separate operational workflow exists
- Requires a valid OpenAI API key and a running PostgreSQL service with pgvector enabled
- The Streamlit frontend is a scaffold and is not a complete production UI in this repo
- The system intentionally refuses to invent loan rates, fees, approvals, or legal commitments when the knowledge base does not support them

The assistant must be explicit that it is operating in a fictional assessment context and not making real lending decisions.

## Future improvements

- Add a richer frontend for applicant intake and workflow monitoring
- Add persistent admin tools for knowledge ingestion and version tracking
- Add stricter operational logging and audit trails
- Expand the qualification workflow with risk rules and explicit handoff states
- Add integration tests for Dockerized API flows and database-backed retrieval

## Summary

Loanova is a realistic demonstration of an AI-powered loan assistance workflow built around grounded retrieval, safe AI behavior, and structured agent flow. It is designed to help teams review and assess how a responsible loan assistant can provide helpful preliminary guidance without crossing into unauthorized or binding financial decisions.
