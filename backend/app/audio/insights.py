from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field


DEFAULT_NUDGE_THRESHOLD = 0.55
DEFAULT_DUPLICATE_WINDOW_MS = 60_000
SIGNAL_PRIORITY = {
    "compliance_gap": 5,
    "missed_cross_sell": 4,
    "payment_difficulty": 4,
    "frustration": 3,
    "callback_need": 3,
}


class AudioStreamRequest(BaseModel):
    call_id: str | None = Field(default=None, max_length=200)
    audio_chunks: list[dict[str, Any]] | None = None
    transcript: str | None = Field(default=None, max_length=20000)
    conversation_state: dict[str, Any] | None = None
    mode: str = "replay"


class AudioSignal(BaseModel):
    category: str
    confidence: float
    message: str
    evidence: list[str] = Field(default_factory=list)
    timestamp_ms: int | None = None


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _compute_confidence(base: float, keyword_hits: int, strong_hits: int = 0) -> float:
    score = base + min(0.25, keyword_hits * 0.12) + min(0.2, strong_hits * 0.08)
    return max(0.0, min(0.98, score))


def _is_ambiguous_noise(normalized: str) -> bool:
    noise_markers = (
        "uh",
        "hmm",
        "not clear",
        "unclear",
        "not sure",
        "maybe maybe",
        "i do not know",
        "confusing",
    )
    if not normalized:
        return True
    return any(marker in normalized for marker in noise_markers) and not any(
        strong in normalized for strong in ("second vehicle", "call me back", "callback", "disclosure", "policy terms", "can't pay", "cannot pay")
    )


def extract_call_signals(transcript: str | None, conversation_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    normalized = _normalize_text(transcript)
    if not normalized:
        return []
    if _is_ambiguous_noise(normalized):
        return []

    signal_map = {
        "missed_cross_sell": {
            "keywords": [
                "second vehicle",
                "another vehicle",
                "additional vehicle",
                "multi vehicle",
                "two vehicles",
                "new vehicle",
                "car insurance",
            ],
            "message": "Missed cross-sell opportunity: the customer mentioned an additional asset or second vehicle.",
        },
        "compliance_gap": {
            "keywords": [
                "required disclosure",
                "disclosure",
                "policy terms",
                "before proceeding",
                "must disclose",
                "state the policy",
                "explain the terms",
            ],
            "message": "Compliance gap: the required disclosure or policy terms may be missing.",
        },
        "frustration": {
            "keywords": [
                "frustrated",
                "angry",
                "not happy",
                "unhappy",
                "very upset",
                "too long",
                "i am upset",
                "concerned",
            ],
            "message": "Rising frustration: the customer is showing signs of dissatisfaction or concern.",
        },
        "payment_difficulty": {
            "keywords": [
                "can't pay",
                "cannot pay",
                "struggling to pay",
                "payment issue",
                "payment support",
                "difficult to pay",
                "unable to pay",
                "late payment",
            ],
            "message": "Payment difficulty: the customer may need a payment-support pathway or callback.",
        },
        "callback_need": {
            "keywords": [
                "call me back",
                "callback",
                "need a callback",
                "follow up",
                "speak with a human",
                "human callback",
            ],
            "message": "Callback need: a live follow-up may be helpful.",
        },
    }

    signals: list[dict[str, Any]] = []
    for category, config in signal_map.items():
        matched = [keyword for keyword in config["keywords"] if keyword in normalized]
        if not matched:
            continue
        confidence = _compute_confidence(0.55, len(matched), 1 if category in {"compliance_gap", "callback_need"} else 0)
        if confidence < DEFAULT_NUDGE_THRESHOLD:
            continue
        signals.append(
            {
                "category": category,
                "confidence": round(confidence, 2),
                "message": config["message"],
                "evidence": matched,
                "timestamp_ms": int((conversation_state or {}).get("timestamp_ms", 0)),
            }
        )

    return sorted(signals, key=lambda item: (-item["confidence"], item["category"]))


def generate_nudges(signals: list[dict[str, Any]], history: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    prior_keys: set[str] = {item.get("dedupe_key", "") for item in (history or []) if item.get("dedupe_key")}

    for signal in signals or []:
        category = str(signal.get("category", "")).strip()
        confidence = float(signal.get("confidence", 0.0) or 0.0)
        if not category or confidence < DEFAULT_NUDGE_THRESHOLD:
            continue

        dedupe_key = f"{category}:{str(signal.get('message', '')).lower()}"
        if category in seen_categories or dedupe_key in prior_keys:
            continue

        template_map = {
            "missed_cross_sell": "Suggest the multi-vehicle or add-on offer while the customer is still interested.",
            "compliance_gap": "Remind the agent to confirm the disclosure or policy terms before proceeding.",
            "frustration": "Acknowledge the concern and slow the sales path before continuing.",
            "payment_difficulty": "Offer an approved payment-support or callback path for the customer.",
            "callback_need": "Offer a human callback or live follow-up while the intent is still active.",
        }

        message = template_map.get(category, "Address the customer need before the next step.")
        deduped.append(
            {
                "category": category,
                "message": message,
                "confidence": round(confidence, 2),
                "priority": SIGNAL_PRIORITY.get(category, 2),
                "dedupe_key": dedupe_key,
            }
        )
        seen_categories.add(category)

    deduped.sort(key=lambda item: (-item["priority"], -item["confidence"]))
    return deduped


def _compile_transcript(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return ""
    parts: list[str] = []
    for chunk in chunks:
        transcript = str(chunk.get("transcript") or chunk.get("text") or "").strip()
        if transcript:
            parts.append(transcript)
    return " ".join(parts).strip()


def _simulate_latency_values(chunks: list[dict[str, Any]], transcript: str, nudge_count: int) -> dict[str, float]:
    durations = [float(chunk.get("duration_ms") or 0.0) for chunk in chunks if chunk.get("duration_ms") is not None]
    if not durations:
        durations = [1000.0] * max(1, len(chunks))
    asr_ms = max(80.0, sum(durations) / max(1, len(durations)))
    signal_ms = max(90.0, len(transcript.split()) * 4.0)
    llm_ms = max(150.0, len(transcript.split()) * 6.0)
    delivery_ms = 50.0 + (nudge_count * 30.0)
    values = [asr_ms, signal_ms, llm_ms, delivery_ms]
    return {
        "asr_ms": round(asr_ms, 2),
        "signal_ms": round(signal_ms, 2),
        "llm_ms": round(llm_ms, 2),
        "delivery_ms": round(delivery_ms, 2),
        "p50_ms": round(_percentile(values, 0.50), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "total_ms": round(sum(values), 2),
    }


def process_live_audio_stream(payload: dict[str, Any] | AudioStreamRequest) -> dict[str, Any]:
    request = payload if isinstance(payload, AudioStreamRequest) else AudioStreamRequest(**payload)
    chunks = request.audio_chunks or []
    transcript = request.transcript or _compile_transcript(chunks)
    if not transcript:
        return {
            "call_id": request.call_id,
            "status": "idle",
            "mode": request.mode,
            "transcript": "",
            "signals": [],
            "nudges": [],
            "latency": {"asr_ms": 0.0, "signal_ms": 0.0, "llm_ms": 0.0, "delivery_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "total_ms": 0.0},
            "pipeline": "chunked_replay",
            "notes": "No audio transcript was provided; live insight processing is waiting for more chunks.",
        }

    signals = extract_call_signals(transcript, request.conversation_state or {})
    nudges = generate_nudges(signals)
    latency = _simulate_latency_values(chunks, transcript, len(nudges))
    return {
        "call_id": request.call_id,
        "status": "live_insights",
        "mode": request.mode,
        "transcript": transcript,
        "signals": signals,
        "nudges": nudges,
        "latency": latency,
        "pipeline": "chunked_replay",
        "notes": "This is a chunked replay / local pipeline simulation; real microphone capture would require an ASR provider and a streaming transport.",
        "confidence_threshold": DEFAULT_NUDGE_THRESHOLD,
    }
