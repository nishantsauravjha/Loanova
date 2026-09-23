# Q4 chunked-replay evaluation

This implementation is not a live audio telephony pipeline. It is a real-time-speed chunk replay / offline simulation that evaluates the live-insights pathway using transcript chunks and local latency estimates.

## Actual runtime mode

- Mode: chunked replay / local simulation
- Not live: no microphone capture, no real streaming ASR, no live call transport, and no real telephony backend
- What it does: replays ordered transcript chunks, extracts signal(s), generates nudges, reports latency summaries, and preserves the grounded Q1/Q2 behavior

## Goal

Verify that the backend can:
- ingest ordered transcript chunks,
- extract risk signals over time,
- generate nudges without duplicate spam,
- report per-chunk and cumulative latency metrics,
- preserve the core Q1/Q2 grounded knowledge behavior while live insights are present.

## Inputs

The synthetic replay fixture lives at [docs/q4_chunked_replay_fixture.json](q4_chunked_replay_fixture.json). It contains a short call transcript split into ordered chunks, each with a timestamp and duration.

## Reproducible demo command

From the project root:

```bash
PYTHONPATH=backend python - <<'PY'
import json
from app.audio.insights import process_live_audio_stream

with open('docs/q4_chunked_replay_fixture.json') as f:
    fixture = json.load(f)

result = process_live_audio_stream({
    'call_id': fixture['call_id'],
    'audio_chunks': fixture['chunks'],
    'conversation_state': {'last_status': 'ready'},
    'mode': 'replay',
})

print('mode=', result['mode'])
print('signals=', [s['category'] for s in result['signals']])
print('nudges=', [n['category'] for n in result['nudges']])
print('p50_ms=', result['latency']['p50_ms'])
print('p95_ms=', result['latency']['p95_ms'])
print('total_ms=', result['latency']['total_ms'])
PY
```

### Expected output guide

The current code emits a replay result such as:

```text
mode= replay
signals= ['compliance_gap', 'callback_need', 'frustration', 'missed_cross_sell']
nudges= ['compliance_gap', 'missed_cross_sell', 'callback_need', 'frustration']
p50_ms= 351.5
p95_ms= 387.6
total_ms= 1623.5
```

These values are measured replay-simulation estimates produced by the local chunk pipeline. They are not real ASR, microphone, or production call latency numbers.

## Measured replay-simulation results

The current fixture produces:

- mode: replay
- final signals: compliance_gap, callback_need, frustration, missed_cross_sell
- final nudges: compliance_gap, missed_cross_sell, callback_need, frustration
- latency estimates: p50_ms = 351.5, p95_ms = 387.6, total_ms = 1623.5

These numbers are generated from ordered transcript chunks and local processing assumptions in the replay code. They should be interpreted as local pipeline estimates only.

## Method

1. Replay the transcript chunks in chronological order.
2. At each chunk, compute the cumulative transcript and extract signal(s) from the partial transcript.
3. Generate active nudges for that partial state, while suppressing duplicates within the same call.
4. Summarize the final state with cumulative signals, final nudges, and latency metrics.
5. Keep the result honest: the code notes this is a replay / local pipeline simulation.

## Verified result

The current regression suite result is:

- 42 passed, 1 warning in 0.98s

The warning is a third-party Starlette/TestClient deprecation warning and does not indicate a failing test.

This covers:
- Q4 cooldown / duplicate suppression,
- missed cross-sell detection,
- compliance / disclosure detection,
- frustration detection,
- noisy / ambiguous input filtering,
- latency reporting,
- live-insights integration with the grounded Q1/Q2 voice flow.

## Current limitations

- No live microphone streaming is implemented in this repo.
- No real telephony backend, call transport layer, or production monitoring stack is present.
- No provider-backed real-time ASR or TTS is claimed unless the code explicitly implements it.
- The recorded metrics above are replay-simulation estimates from local transcript chunks, not measured production call telemetry.

## Production reality check

A real-time voice deployment would require a streaming audio source, an ASR provider or private speech service, transport and session management, and production observability. This repo does not implement those components, so the Q4 replay path remains a local evaluation pipeline rather than a production-grade live call monitor.
