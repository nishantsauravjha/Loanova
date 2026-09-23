# Q2 Retrieval Evaluation

This evaluation uses the synthetic demo knowledge base in the repo and the existing retrieval path in `backend/app/kb/kb.py`.

Important: the dataset is intentionally synthetic/demo content for assessment work. It is not a production loan policy database and it does not contain real customer data. The same repository code path is used by the Q1 voice agent via `process_voice_turn()` -> `answer_question()` -> `retrieve()`, so the retrieval layer is directly integrated with the live conversational interface.

## Knowledge-base pipeline summary

The Q2 pipeline in this repo covers the required retrieval lifecycle:

- Document cleaning: whitespace normalization and obvious PII redaction in `prepare_records_for_ingestion()`.
- Deduplication: duplicate records are collapsed before indexing using a canonical `(record_id, title, category, source, content)` key.
- Metadata + taxonomy: every record keeps `record_id`, `title`, `category`, `source`, `version`, and `pii` metadata.
- Chunking + versioning: the records are chunked with `RecursiveCharacterTextSplitter` and stored with `version` metadata in the Postgres table.
- Vector indexing + retrieval: `PGVector` stores embeddings to `loan_knowledge_demo` and retrieval returns ranked records with similarity scores.
- Source citations: answers include source metadata and `[record_id]` citations for grounded responses.
- Retrieval evaluation: the repo includes actual local hits for five representative queries below.

## Reproduction

Run from the project root with the Docker PostgreSQL service available:

```bash
set -a && source .env && set +a
export DATABASE_URL="postgresql://app:app_password@localhost:5433/assessment"
source venv/bin/activate
PYTHONPATH=backend python - <<'PY'
from app.kb import kb
kb.ingest_json('data/raw/loan_knowledge.json')
for q in [
    'What is the demo business loan intended for?',
    'What documents might a lender request?',
    'What information should I provide for preliminary qualification?',
    'What are the approved interest rates and fees?',
    "I’m worried I might not qualify. What should the assistant do?",
]:
    print(q)
    for hit in kb.retrieve(q, limit=3):
        print(hit['record_id'], hit['title'], hit['source'], hit['content'])
    print('---')
PY
```

## Actual retrieval results

| Category | Exact user question | Actual retrieved chunk/record | Source reference | Brief relevance explanation | Verdict |
| --- | --- | --- | --- | --- | --- |
| Product | What is the demo business loan intended for? | `loan_001` — "Business Loan Overview" — "The demo business loan is intended for small businesses seeking funds for working capital, equipment, or business expansion. The assistant must explain that this is a fictional demonstration product and not an actual lending offer." | `demo://loan-product-overview` | This is the direct product definition and exactly matches the question. | correct |
| Policy | What documents might a lender request? | `loan_003` — "Application Documentation" — "Illustrative documents that a lender might request include business registration details, identity documents, bank statements, and financial records. Actual requirements depend on the lender. The demo assistant must not claim these documents are sufficient for approval." | `demo://documentation-policy` | This is the best match for document requirements and includes the required safety language about not guaranteeing approval. | correct |
| Qualification | What information should I provide for preliminary qualification? | `loan_002` — "Illustrative Qualification Criteria" — "For this fictional demo, a lead should provide business type, time in operation, approximate monthly revenue, requested loan amount, and intended use of funds. Collecting these details is preliminary qualification only and does not constitute approval." | `demo://qualification-rules` | This is the correct qualification checklist, but it was not the top-ranked hit for this phrasing because a related objection record also ranked highly. | partially correct |
| FAQ | What are the approved interest rates and fees? | `loan_004` — "Interest Rates and Fees" — "The demo knowledge base contains no approved interest rates, processing fees, repayment schedules, or final loan offers. The assistant must state that these details are unavailable rather than inventing numbers." | `demo://rates-and-fees` | This directly answers the FAQ by stating the information is unavailable, which is the intended safe behavior for unsupported financial details. | correct |
| Objection handling | I’m worried I might not qualify. What should the assistant do? | `loan_005` — "Objection: Concern About Eligibility" — "If a caller is unsure whether their business qualifies, acknowledge the concern and explain that the assistant can collect preliminary details. Do not guarantee eligibility or approval. Offer human follow-up if requested." | `demo://eligibility-objection` | This is the strongest match and gives the correct objection-handling guidance. | correct |

## Evaluation notes

- The real retrieval run succeeded only after the local PostgreSQL service was started with Docker and the `DATABASE_URL` was pointed at `localhost:5433`.
- The knowledge base was ingested from `data/raw/loan_knowledge.json` using the existing `kb.ingest_json()` flow.
- Retrieval is intentionally safe: unsupported financing questions are expected to resolve to the "rates and fees unavailable" record rather than inventing values.
- The evaluation results above are the actual outputs from the repo’s current retrieval implementation, without fabricated records or success claims.
