# Final assessment checklist

## Priority 1 — Must complete before submission

1. Confirm the current regression suite is passing and record the exact command and result.
   - Command: `pytest tests/test_ai_assessment.py -q`
   - Current result: 42 passed, 1 warning in 0.98s

2. Capture real browser recordings and transcripts for Q1 / Q3 if you intend to claim actual voice validation.
   - Use the browser UI at http://localhost:8501
   - Save timestamped audio and transcript files locally
   - Do not fabricate results or present scripted prompts as real calls

3. Validate multilingual browser behavior in Chrome for the documented Filipino / Taglish / Indonesian scenarios.
   - Confirm ASR recognition, TTS playback, and locale selection
   - Record language-specific observations, not just backend pass/fail status

4. Keep Q4 honest as replay/local-simulation evidence unless you actually implement live microphone streaming and provider-backed ASR.
   - The code currently reports chunked replay mode and measured local latency estimates
   - Do not claim production or live-call metrics without real runtime evidence

5. Ensure the final submission package clearly distinguishes code-tested evidence from manual browser validation.
   - Tests and repo checks are evidence-backed
   - Manual call evidence must be collected and labeled separately

## Priority 2 — Strongly recommended evidence package

1. Add any missing browser screenshots or short screen-recording clips showing the voice UI, language selection, and backend responses.
2. Save a small comparison matrix for Q3 language examples with the actual recognized text and voice output observed in the browser.
3. Keep a short note for each recorded call covering:
   - browser locale and selected voice
   - ASR recognized text
   - TTS playback outcome
   - backend request/response and any errors
   - known limitations or misrecognition

## Priority 3 — Documentation hygiene

1. Keep the repo README aligned with the actual implementation status.
2. Keep the Q4 evaluation report explicit that the metrics are replay-simulation estimates.
3. Keep .env secrets local-only and avoid committing API keys or provider credentials.

## Status summary

- Q1: implemented and tested
- Q2: implemented and tested
- Q3: implemented and tested at code level; real multilingual browser validation remains manual
- Q4: implemented and tested as replay/local simulation; live microphone/telephony remains unimplemented

## Final submission warning

Do not present synthetic fixtures, scripted prompts, or undocumented browser behavior as real production call evidence. The repo supports a demo-safe assessment flow; real browser-validation artifacts are still the personal responsibility of the submitter.
