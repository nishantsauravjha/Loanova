# Loanova Assessment Gap Audit

## Scope and audit basis

This audit uses the repository’s actual implementation, configuration, tests, and docs as evidence. The assessment requirement is treated as the set of Q1–Q4 behaviors described in the repo docs and tests, not as a claim from the README alone.

The project includes working code across the API, knowledge layer, localization, voice flow, replay insights, and Streamlit UI. The main remaining gaps concern evidence quality and the boundary between replay/local simulation versus true live telephony or browser audio capture.

## Executive summary

Status summary:

- Q1: Implemented and covered by tests.
- Q2: Implemented and covered by tests.
- Q3: Implemented and covered by tests.
- Q4: Partially implemented and tested as replay/local simulation only; not a real microphone/telephony pipeline.
- Frontend UI: implemented and functional for browser interface, but it is still a demo UI rather than a real telephony product surface.
- Documentation: good but some claims need clearer boundary language between demo implementation and production-grade ASR/TTS.

## 1) Q1 — Grounded loan-question assistant and qualification flow

Status: Implemented and tested.

### Requirement
A loan assistant should:
- answer general product questions from a trusted knowledge base,
- refuse unsupported financial details,
- collect preliminary qualification information safely,
- escalate to a human when appropriate,
- preserve the demo-safe boundary (no fake approvals or APR/fee construction).

### Evidence
- `backend/app/voice/agent.py`
  - `process_voice_turn()`
  - `_is_unsupported_financial_question()`
  - `_looks_like_qualification_intent()`
  - `_build_qualification_payload()`
  - `_resolve_language()`
- `backend/app/agents/loan_graph.py`
  - `run_qualification_workflow()`
  - `check_missing_fields()`
  - `handle_missing_fields()`
  - `handle_objection()`
  - `handle_escalation()`
  - `assess_qualification()`
- `backend/app/main.py`
  - `/voice/conversation` and `/agent/qualification` routes
- `frontend/streamlit_app.py`
  - browser chat + voice UI calling the backend API
- `tests/test_ai_assessment.py`
  - `test_voice_agent_avoids_inventing_financial_claims()`
  - `test_voice_agent_handles_missing_information_and_objection()`
  - `test_voice_agent_escalates_human_request()`
  - `test_voice_agent_keeps_english_q1_q2_behavior_untouched()`
  - `test_frontend_calls_voice_api_contract()`

### Findings
- The system does prevent unsupported APR/fee/approval claims.
- The qualification flow correctly requests missing fields and routes escalation scenarios.
- The browser frontend calls the API and keeps the conversation flow intact.

### Gaps / next steps
- No real end-to-end voice call recording is in the repo; this is not a production telephony integration.
- The Q1 flow is validated by tests and by repo logic, but not by a real browser capture artifact.

## 2) Q2 — Retrieval over a synthetic knowledge base with citation grounding

Status: Implemented and tested.

### Requirement
A grounded retrieval pipeline should:
- ingest a synthetic loan KB,
- split/prepare documents for vector search,
- search using similarity matching,
- return citations and source metadata,
- keep unsupported financial details out of the answer.

### Evidence
- `backend/app/kb/kb.py`
  - `get_vector_store()`
  - `chunk_text()`
  - `ingest_json()`
  - `retrieve()`
  - `answer_question()`
  - `_serialize_sources()`
  - `_format_citation_text()`
- `docs/q2_retrieval_evaluation.md`
  - provides a real retrieval run showing actual records retrieved from the local DB
- `data/raw/loan_knowledge.json`
  - synthetic loan product, qualification, documentation, and rates/fees records
- `tests/test_ai_assessment.py`
  - `test_vector_store_initializes_with_langchain_postgres_signature()`
  - `test_ingest_json_stores_chunks_and_metadata()`
  - `test_retrieve_returns_citations_and_records()`
  - `test_voice_agent_uses_grounded_kb_for_supported_question()`

### Findings
- Retrieval logic is implemented and likely functions in a real local PostgreSQL + pgvector environment.
- The repo includes a retrieval evaluation document with concrete record IDs and source references.
- The implementation actively refuses unsupported financial detail claims.

### Gaps / next steps
- The retrieval path is demo-safe and works within the synthetic DB, but it is not a production knowledge system and should be described as such.
- A full end-to-end retrieval smoke test with actual pgvector service is still a local environment task, not a fully automated CI guarantee.

## 3) Q3 — Localization and language-aware responses

Status: Implemented and tested.

### Requirement
The assistant should support:
- English,
- Filipino / Tagalog,
- Taglish mixed inputs,
- Indonesian,
- browser-side locale mapping,
- localized greeting/response behavior without losing groundedness.

### Evidence
- `backend/app/localization.py`
  - `detect_language()`
  - `normalize_language_hint()`
  - `browser_locale_for_language()`
  - `localize_response_text()`
- `backend/app/voice/agent.py`
  - `_resolve_language()` and localized qualification handling
- `tests/test_ai_assessment.py`
  - `test_language_detection_handles_tagalog_and_indonesian_markers()`
  - `test_language_selection_aliases_are_explicit_and_stable()`
  - `test_voice_agent_localizes_filipino_greeting_and_query_flow()`
  - `test_voice_agent_supports_explicit_taglish_language_selection_and_mixed_language_input()`
  - `test_voice_agent_localizes_indonesian_unsupported_financial_request()`
- `docs/call_test_plan.md`
  - outlines Q3 prompt scenarios and expected behavior

### Findings
- Locale detection and alias normalization are implemented.
- Filipino, Taglish, and Indonesian flows are represented in both backend logic and tests.
- Browser locale mapping is present in the UI and backend.

### Gaps / next steps
- The localization logic is validated at code/test level, but actual real-browser microphone and TTS perception still need human verification.
- Mixed-language ASR quality remains a real browser-dependent concern, not a guaranteed code guarantee.

## 4) Q4 — Live audio insights, signal extraction, and replay evaluation

Status: Partially implemented and tested; replay/local simulation only.

### Requirement
The repo should support:
- ordered transcript chunk replay,
- signal extraction from transcript content,
- nudge generation with deduplication,
- latency reporting,
- false-positive controls,
- integration with the live insights path while keeping Q1/Q2 grounding intact.

### Evidence
- `backend/app/audio/insights.py`
  - `extract_call_signals()`
  - `generate_nudges()`
  - `evaluate_chunked_replay()`
  - `process_live_audio_stream()`
- `docs/q4_chunked_replay_evaluation.md`
  - explains that this is replay/local simulation, not real ASR or telephony
- `docs/q4_chunked_replay_fixture.json`
  - synthetic ordered transcript fixture
- `tests/test_ai_assessment.py`
  - `test_q4_signal_extraction_identifies_cross_sell_and_compliance_risks()`
  - `test_q4_nudge_engine_suppresses_duplicates_and_low_confidence()`
  - `test_q4_latencies_are_reported_for_real_time_pipeline()`
  - `test_q4_false_positive_controls_block_ambiguous_noise()`
  - `test_voice_agent_integration_keeps_q1_q2_grounding_when_live_insights_are_present()`

### Findings
- The Q4 code is implemented as a synthetic replay pipeline and is covered by tests.
- The code explicitly separates itself from real microphone capture, ASR, or production call-center processing.
- The project intentionally does not claim more than local replay behavior.

### Gaps / next steps
- This is not a real live-audio or live-telephony implementation.
- There is no real browser microphone stream captured or processed end-to-end in the repository.
- There is no real ASR provider integration or real-world call-quality evaluation artifact in the repo.
- The Q4 path should be described as a demo pipeline, not a production call monitoring system.

## 5) Frontend / browser UI and voice panel

Status: Implemented and tested for browser functionality, but still a demo UI.

### Requirement
The browser UI should:
- support chat interaction,
- allow the user to select language and voice,
- use speech recognition and speech synthesis in the browser,
- provide resilient fallback behavior,
- preserve the backend API contract.

### Evidence
- `frontend/streamlit_app.py`
  - `build_voice_component_html()`
  - `get_voice_api_url()`
  - `call_voice_api()`
  - `render_chat_message()`
  - `main()`
- `tests/test_ai_assessment.py`
  - `test_build_voice_component_html_includes_browser_voice_contract()`
  - `test_build_voice_component_html_uses_explicit_voice_selection_and_missing_voice_warning()`
  - `test_frontend_uses_host_browser_backend_url_when_backend_service_name_is_present()`
  - `test_frontend_calls_voice_api_contract()`

### Findings
- The browser voice panel is implemented and tested for presence of selected controls and fallback behaviors.
- It supports language selection, voice selection, and typed fallback.
- The app has a real browser UI contract, but it is still not a full telephony product experience.

### Gaps / next steps
- Real browser TTS/ASR quality still requires manual Chrome verification.
- The UX is polished but still a browser-only demonstration, not a real call-center interface.

## 6) Configuration and environment

Status: Mostly implemented.

### Evidence
- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `backend/requirements.txt`
- `frontend/requirements.txt`
- `.env.example` (if present in the repo)

### Findings
- Local Docker and service wiring are in place for PostgreSQL and the app services.
- Repo-level configuration supports local demo execution.

### Gaps / next steps
- A full reproducible production environment is not the goal of this repo; it is a demo assessment project.
- Actual runtime validation still depends on a working OpenAI key and local Docker environment.

## Assessment status matrix

| Area | Status | Notes |
| --- | --- | --- |
| Q1 product + objection + qualification flow | Implemented | Code and tests cover the main behavior |
| Q2 grounded retrieval + citations | Implemented | Retrieval and evaluation docs are present |
| Q3 localization | Implemented | Localized flows and alias mapping are covered |
| Q4 replay insights | Partially implemented | Validated as replay/local simulation only |
| Browser voice UI | Implemented | Functional for browser demo, not real telephony |
| Real ASR/TTS proof | Missing | Requires manual browser verification |
| Real live call capture | Missing | Not implemented in repo |
| Production-grade call-center stack | Missing | Outside project scope and intentionally not claimed |

## Highest-priority remaining work

1. Manual Chrome validation of the browser TTS/voice-selection behavior and English voice clarity.
2. Keep Q4 honest as replay/local-simulation-only until a real audio pipeline is added.
3. Capture any missing browser-level evidence artifacts (screen recordings, transcript notes, locale observations) to support the assessment narrative.
4. If the goal is a more production-like system, add real ASR/TTS provider integration and a real integration test layer; otherwise, keep the repo clearly scoped to the demo-safe assessment project.

## Final assessment statement

The repository is substantially implemented and test-covered for the core Q1–Q3 requirements and the replay/local Q4 path. The biggest remaining gap is not in the core logic itself; it is the lack of real live-audio or real provider-backed telephony evidence. The codebase is honest about its boundaries, and that honesty is one of its strongest implementation traits.
