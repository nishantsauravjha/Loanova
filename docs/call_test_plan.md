# Loanova call testing pack

This pack is aligned to the current implementation in [backend/app/voice/agent.py](../backend/app/voice/agent.py), [backend/app/localization.py](../backend/app/localization.py), [frontend/streamlit_app.py](../frontend/streamlit_app.py), and the assessment checks in [tests/test_ai_assessment.py](../tests/test_ai_assessment.py).

Important boundaries:
- This document contains scripted test prompts only. It does not include fabricated transcripts, fake recordings, or any claims that a call was performed.
- The available calling method is the browser voice UI at http://localhost:8501 using the browser speech APIs. There is no public phone number or telephony backend in this repo.
- Required real-call recordings must be captured in the browser using the existing app, not by inventing result data.
- Scripted prompts are for guided testing and reproducible verification; real recordings are required to validate the browser/ASR/TTS experience.

## 1) Required real recordings vs scripted test inputs

### Required real recordings
Use the existing Loanova browser UI at http://localhost:8501 and record actual demo calls only when you are personally testing in the browser.

Required capture for each real call:
- audio file saved locally as a timestamped browser recording
- transcript text saved locally in a matching text or JSON file
- browser locale and selected voice language
- ASR recognized text before/after correction
- TTS playback result and whether the assistant audio was heard
- backend request/response payload, if available from logs
- errors, latency notes, and observations

### Scripted test inputs
The utterances below are examples to read aloud or paste into the browser text input. They are not recordings and should never be presented as actual call results.

## 2) Q1 scenarios

### Q1-A: product / knowledge-base question
Suggested user utterance (scripted only):
"What is this business loan for?"

Expected behavior:
- This is treated as an English product/knowledge question, not a qualification intake.
- The app should answer from the demo knowledge base, not invent a real offer.
- The response should remain grounded and cite the matching knowledge record when present.

Pass/fail checklist:
- [ ] no backend error
- [ ] status follows the knowledge-answer flow
- [ ] answer stays within the demo KB and does not invent APR, fee, approval, or eligibility
- [ ] source metadata is present when supported
- [ ] no qualification fields are requested unnecessarily

Record actual call fields:
- actual transcript text
- selected browser locale / ASR locale
- recognized speech text
- TTS output heard or not heard
- any backend or browser errors
- observations on pace, silence, misrecognition, and clarity

### Q1-B: qualification intake
Suggested user utterance (scripted only):
"I need a business loan for my restaurant. I have been operating for 2 years, monthly revenue is 75,000, I need 50,000, and I want to use it for inventory."

Expected behavior:
- The system recognizes a qualification-intent request and asks for missing fields only when appropriate.
- It should not claim approval or eligibility.
- The flow may ask for missing detail or route to a human follow-up if the user raises a direct escalation or objection.

Pass/fail checklist:
- [ ] message is recognized as a qualification-intent request
- [ ] no fabricated approval statement is made
- [ ] missing-field prompts are specific and limited to the workflow data points
- [ ] backend response remains grounded and safe
- [ ] any conflict or missing-field state is reported clearly

Record actual call fields:
- actual transcript text
- browser/ASR locale
- voice detection or language mode chosen in browser
- clarity of the user’s spoken details
- TTS playback quality
- errors or interruptions
- observations on whether fields were captured correctly

### Q1-C: objection or human escalation
Suggested user utterance (scripted only):
"I do not qualify and I want a human callback right now."

Expected behavior:
- The app should classify this as an objection / escalation path.
- The logic should not invent a formal loan outcome.
- The system should either ask for a minimal follow-up or move to a human callback / escalation flow in a factual, non-deceptive way.

Pass/fail checklist:
- [ ] objection or escalation terms are detected
- [ ] no fake approval decision is produced
- [ ] the assistant remains respectful and safe
- [ ] human callback or escalation path is clearly signaled if the workflow requires it
- [ ] no unsupported financial claim is output

Record actual call fields:
- actual transcript text
- browser locale and selected language
- ASR mistranscription around “callback”, “human”, or “do not qualify”
- TTS behavior during the escalation response
- errors, dropped audio, or failed send
- observations on whether the user’s urgency was carried through clearly

## 3) Q3 localization scenarios

The current implementation detects English, Filipino/Tagalog, Taglish, and Bahasa Indonesia and maps them to browser locales such as en-US, fil-PH, and id-ID. Use these scenarios as real browser prompts to validate locale handling and mixed-language natural speech.

### Q3-A: Filipino product question
Suggested user utterance (scripted only):
"Kamusta, ano ang loan para sa negosyo?"

Expected behavior:
- The app should detect Filipino or Tagalog-heavy input.
- It should respond in a localized greeting/answer style without claiming unsupported financing details.
- The assistant should prefer the grounded demo KB for a product question.

Pass/fail checklist:
- [ ] language is recognized as Filipino or Taglish
- [ ] greeting or localized response appears
- [ ] answer stays grounded to the synthetic KB
- [ ] no unsupported APR/fee claim appears
- [ ] browser locale matches the selected Filipino/Tagalog flow when available

Record actual call fields:
- actual transcript text
- browser locale and ASR locale used
- TTS language or fallback behavior
- any accent or pronunciation issues
- errors or dropped recognition
- observations on greeting and answer localization

### Q3-B: Taglish mixed-language product request
Suggested user utterance (scripted only):
"Magandang araw, I need a business loan for my negosyo and I want to know the product details."

Expected behavior:
- The app should classify the input as Taglish due to natural code-switching.
- It should still preserve the grounded loan product answer instead of moving prematurely into a qualification or approval flow.
- The answer may include a local greeting but must remain factual and demo-safe.

Pass/fail checklist:
- [ ] code-switching is accepted without crashing or misclassifying input
- [ ] language detection is stable for mixed-language text
- [ ] product answer is grounded and safe
- [ ] no invented rates, terms, or approvals are spoken
- [ ] selected locale remains consistent with Filipino/Tagalog behavior

Record actual call fields:
- actual transcript text
- ASR recognized text for the mixed-language phrase
- browser locale and TTS voice selected
- any mismatch between spoken input and recognized text
- errors, fallback, or silent segments
- observations on localization quality

### Q3-C: Bahasa Indonesia product question
Suggested user utterance (scripted only):
"Halo, apakah pinjaman usaha ini untuk modal kerja?"

Expected behavior:
- The app should detect Indonesian and respond with Indonesian-localized, grounded guidance.
- It should answer as a product/knowledge question, not a financial approval decision.

Pass/fail checklist:
- [ ] input is recognized as Indonesian
- [ ] localized greeting or response appears
- [ ] answer stays in the demo knowledge scope
- [ ] no approval or fee claim is produced
- [ ] browser locale matches Indonesian behavior when available

Record actual call fields:
- actual transcript text
- browser locale and ASR locale
- TTS voice and language behavior
- clarity of the Indonesian phrase recognition
- errors or fallback handling
- observations on naturalness and latency

### Q3-D: Bahasa Indonesia unsupported financial request with code-switching
Suggested user utterance (scripted only):
"Halo, berapa APR dan fee untuk pembiayaan ini?"

Expected behavior:
- This is a high-risk unsupported-financial question.
- The app should refuse to invent a rate or approval and should remain grounded in the synthetic demo KB.
- The response should be localized and explicit that the details are unavailable.

Pass/fail checklist:
- [ ] input is recognized as Indonesian or mixed Indonesian/English
- [ ] the assistant does not invent numbers or approval terms
- [ ] response clearly states that APR/fees/approval information is unavailable in the demo KB
- [ ] browser output and TTS remain coherent
- [ ] no backend failure or invalid JSON response occurs

Record actual call fields:
- actual transcript text
- browser locale and ASR locale
- recognized phrase around APR / fee / pembiayaan
- TTS behavior for the refusal answer
- errors, audio clipping, or decode issues
- observations on whether the refusal is clear and understandable

## Q3 evidence matrix and required recording count

The repo supports Filipino, Tagalog, Taglish, and Indonesian language detection and locale selection via browser locale mapping. The actual ASR/TTS capability is browser- and device-dependent, and the code intentionally does not claim native accent fidelity or vendor-backed speech quality beyond the browser’s available voice set.

### Minimum examples per market

#### Philippines / Filipino / Tagalog / Taglish
- "Kamusta, ano ang loan para sa negosyo?"
- "Magandang araw, kailangan ko ng business loan para sa negosyo."
- "Pwede po ba akong magtanong tungkol sa preliminary qualification?"
- "Magandang araw, I need a business loan for my negosyo."
- "Hi, I want to know the product and the approval process."

#### Indonesia / Bahasa Indonesia
- "Halo, apakah pinjaman usaha ini untuk modal kerja?"
- "Saya mau tahu cicilan dan tenor untuk pembiayaan."
- "Apakah saya perlu membayar DP atau ada biaya lain?"
- "Halo, berapa APR dan fee untuk pembiayaan ini?"
- "Saya ingin follow-up untuk pinjaman saya dan butuh bantuan manusia."

### Required recorded calls per market

- Philippines market: at least 2 real browser recordings capturing different prompts and a language selection change or fallback scenario.
- Indonesia market: at least 2 real browser recordings covering formal Indonesian and colloquial/mixed-language usage.

For each real call, save:
- timestamped audio recording
- transcript text file
- browser name and version
- OS and selected locale
- recognized text and assistant response
- outcome status and any ASR/TTS issues
- note whether the voice engine used a browser-default fallback

Important: if a browser cannot produce a local Tagalog or Indonesian voice, record the failure honestly and keep the result as a partial or failed validation. Do not claim accent support or native TTS quality without evidence.

## 4) Recording procedure for genuine browser demo calls

Use this procedure only for actual local browser testing. Do not fabricate any call results.

1. Start the existing app from the repo as you normally would for local testing:
   - backend service via Docker Compose or the local backend setup
   - Streamlit frontend at http://localhost:8501
2. Open the browser UI, choose the relevant language in the voice selector, and confirm the browser supports microphone access.
3. Use a quiet room and speak one scripted utterance at a time. Keep each call short and focused. If ASR is poor, use the text box as a fallback while still recording the observed microphone behavior.
4. Save artifacts locally using a timestamped naming scheme such as:
   - `data/recordings/YYYY-MM-DD/q1_a_voice_<timestamp>.webm` or `.m4a`
   - `data/recordings/YYYY-MM-DD/q1_a_transcript_<timestamp>.txt`
   - `data/recordings/YYYY-MM-DD/q1_a_notes_<timestamp>.md`
5. In the notes file, record the fields below for each call:
   - scenario ID
   - exact user utterance as spoken
   - selected language / locale
   - ASR recognized text
   - assistant response as heard
   - TTS playback success or failure
   - browser errors
   - backend errors or network issues
   - observation notes
6. Store only local files. Do not add secrets, access tokens, or private call data. Do not commit or push audio or transcripts that include personal information.

## 5) Real-call recording checklist

Required for every real browser demo call:
- [ ] audio file saved locally
- [ ] transcript file saved locally
- [ ] selected browser locale recorded
- [ ] ASR recognized text recorded
- [ ] TTS playback result recorded
- [ ] errors and observations recorded
- [ ] no fake outcomes claimed in notes or docs

## 6) Recommended local evidence folder

Create a local folder for evidence only when testing, for example:
- `data/recordings/`
- `data/test_notes/`

Do not add audio files or secrets to the repo as part of this task. This document intentionally describes the procedure without adding any actual recording artifacts.

## 7) Practical assessment note

This repository’s actual current behavior is limited to a demo-safe, synthetic KB and an orchestration flow for product questions, qualifications, objections, escalation, and localized greetings. The call-testing pack above is therefore designed to validate user interactions and browser behavior without claiming a real production telephony stack, ASR engine, or live call completion.
