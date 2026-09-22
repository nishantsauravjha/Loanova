
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agents.loan_graph import QualificationRequest, run_qualification_workflow
from .audio.insights import AudioStreamRequest, process_live_audio_stream
from .db.db import init_db
from .kb.kb import answer_question, ingest_json, retrieve
from .voice.agent import VoiceTurnRequest, process_voice_turn


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Engineer Assessment API",
    version="0.1.0",
    lifespan=lifespan,
)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/kb/ingest")
def ingest():
    try:
        return ingest_json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/kb/search")
def search(payload: Question):
    try:
        return {"results": retrieve(payload.question)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/kb/answer")
def answer(payload: Question):
    try:
        return answer_question(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/agent/qualification")
def qualification(payload: QualificationRequest):
    try:
        return run_qualification_workflow(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/agent/loan-qualification")
def loan_qualification(payload: QualificationRequest):
    return qualification(payload)


@app.post("/voice/conversation")
def voice_conversation(payload: VoiceTurnRequest):
    try:
        return process_voice_turn(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/voice/agent")
def voice_agent(payload: VoiceTurnRequest):
    return voice_conversation(payload)


@app.post("/voice/live-insights")
def live_insights(payload: AudioStreamRequest):
    try:
        return process_live_audio_stream(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc