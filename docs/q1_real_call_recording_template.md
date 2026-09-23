# Q1 Browser-Call Recording Template

This template is for real browser-based test calls only. It intentionally does not allow fabricated call results or false claims of telephony support. The available calling method in this repo is the browser voice UI at http://localhost:8501 using the browser’s Web Speech API. There is no public phone number or live IVR implementation in the project.

Use this template to record at least three real test calls, transcripts, and outcomes. Each call should be captured manually in a supported browser and saved locally with a timestamp.

## Required evidence for each call

- Date and time
- Browser name and version
- Operating system
- Selected language / voice locale
- Microphone permission status
- Recognized transcript or typed fallback text
- Assistant response as heard or displayed
- Outcome status: cooperative, objection, incomplete/conflicting, unsupported question, human escalation, or error
- Screenshots or saved audio if available
- Notes on ASR/TTS quality and any failures

## Call 1 — Cooperative product question

- Scenario: normal business-loan product question
- User prompt: "What is this business loan for?"
- Browser / voice setup:
  - Browser:
  - OS:
  - Language selected:
  - Microphone allowed: yes/no
- Recognized text:
  - 
- Assistant response:
  - 
- Outcome:
  - 
- Notes:
  - 

## Call 2 — Incomplete or conflicting qualification input

- Scenario: user provides partial or conflicting qualification details
- User prompt: "I need a business loan. I have been operating for 2 years, my revenue is 75k, and I need 50k for inventory."
- Browser / voice setup:
  - Browser:
  - OS:
  - Language selected:
  - Microphone allowed: yes/no
- Recognized text:
  - 
- Assistant response:
  - 
- Outcome:
  - 
- Notes:
  - 

## Call 3 — Unsupported financial question or human escalation

- Scenario: unsupported APR/fee/approval request or an escalation request
- User prompt: "What is the exact APR and fee for this loan?" or "I want a human callback right now."
- Browser / voice setup:
  - Browser:
  - OS:
  - Language selected:
  - Microphone allowed: yes/no
- Recognized text:
  - 
- Assistant response:
  - 
- Outcome:
  - 
- Notes:
  - 

## Recording checklist

- [ ] I confirmed the browser used a supported locale and voice.
- [ ] I captured the actual transcript or typed fallback.
- [ ] I recorded the assistant response as heard or displayed.
- [ ] I recorded the status outcome and any backend or browser errors.
- [ ] I did not fabricate transcript text, call timing, or success claims.
- [ ] I documented any limitation such as muted microphone, browser voice fallback, or unsupported locale.

## Final rule

No fabricated call evidence. If the browser does not support the scenario or the microphone fails, document the failure honestly and keep the result as a failed or partial test case.
