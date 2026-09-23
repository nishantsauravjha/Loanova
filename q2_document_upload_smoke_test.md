# Q2-to-Q1 integration smoke test

## 1) Create unique test document

Command:

```bash
cd /Users/nishantsaurav/ai-engineer-assessment
python - <<'PY'
from pathlib import Path
p = Path('/tmp/aurora_growth_policy.txt')
p.write_text('The Aurora Growth Loan covers only inventory restocking and seasonal equipment purchases for qualifying retailers. This is a fictional demo policy for assessment testing only.\n', encoding='utf-8')
print('text_ready', p.exists(), p.stat().st_size)
PY
```

Observed result:

```text
text_ready True 176
```

## 2) Upload document through the actual API

Command:

```bash
curl -sS -X POST http://localhost:8000/kb/ingest/file \
  -F "file=@/tmp/aurora_growth_policy.txt" \
  -F "title=Aurora Growth Loan Policy" \
  -F "category=policy" \
  -F "source=uploaded://aurora-growth-policy"
```

Observed result:

```json
{"ingested_records":1,"ingested_chunks":1}
```

## 3) Retrieval returns the exact fact with source metadata

Command:

```bash
curl -sS -X POST http://localhost:8000/kb/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does the Aurora Growth Loan cover?"}'
```

Observed result:

```json
{"results":[{"record_id":"tmpxzpt9l0","title":"Aurora Growth Loan Policy","content":"The Aurora Growth Loan covers only inventory restocking and seasonal equipment purchases for qualifying retailers. This is a fictional demo policy for assessment testing only.","category":"policy","source":"uploaded://aurora-growth-policy","version":"1.0","pii":false,"similarity":0.7879847682693238},{"record_id":"tmpkt47uz0s","title":"Readable PDF validation","content":"The PDF loan policy supports working capital and equipment funding for small businesses. Contact [email redacted] for details.","category":"product","source":"uploaded://real-pdf-validation","version":"1.0","pii":true,"similarity":0.4267026846577169},{"record_id":"tmpx7cqwrq2","title":"PDF upload smoke test","content":"The demo business loan supports working capital and equipment funding for small businesses. Contact [email redacted] for details. This is a fictional demo product and not an actual loan offer.","category":"product","source":"uploaded://smoke-pdf","version":"1.0","pii":true,"similarity":0.3859486591671011},{"record_id":"tmpd6m40_sf","title":"Text upload smoke test","content":"The demo business loan supports working capital and equipment funding for small businesses. Contact [email redacted] for details. This is a fictional demo product and not an actual loan offer.","category":"product","source":"uploaded://smoke-text","version":"1.0","pii":true,"similarity":0.38593327795528864}]}
```

## 4) Q1 voice agent answers using uploaded content and cites the source

Command:

```bash
curl -sS -X POST http://localhost:8000/voice/conversation \
  -H 'Content-Type: application/json' \
  -d '{"message":"What does the Aurora Growth Loan cover?","conversation_state":{}}'
```

Observed result:

```json
{"status":"knowledge_answer","answer":"The Aurora Growth Loan covers inventory restocking and seasonal equipment purchases for qualifying retailers [tmpxzpt9l0].\n\nCitations: [tmpxzpt9l0] Aurora Growth Loan Policy (uploaded://aurora-growth-policy), [tmpkt47uz0s] Readable PDF validation (uploaded://real-pdf-validation), [tmpx7cqwrq2] PDF upload smoke test (uploaded://smoke-pdf), [tmpd6m40_sf] Text upload smoke test (uploaded://smoke-text)","sources":[{"record_id":"tmpxzpt9l0","title":"Aurora Growth Loan Policy","source":"uploaded://aurora-growth-policy","similarity":0.7879805594377817,"category":"policy"},{"record_id":"tmpkt47uz0s","title":"Readable PDF validation","source":"uploaded://real-pdf-validation","similarity":0.4266808641542327,"category":"product"},{"record_id":"tmpx7cqwrq2","title":"PDF upload smoke test","source":"uploaded://smoke-pdf","similarity":0.38592887527704023,"category":"product"},{"record_id":"tmpd6m40_sf","title":"Text upload smoke test","source":"uploaded://smoke-text","similarity":0.3859134306040899,"category":"product"}],"grounded":true,"escalated":false}
```

## 5) Result

No errors were observed during this Q2-to-Q1 integration smoke test. The uploaded document was ingested, retrieved by its exact factual content, and used by the Q1 voice agent to answer the question without inventing additional policy details.
