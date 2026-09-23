
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agents.loan_graph import QualificationRequest, run_qualification_workflow
from .audio.insights import AudioStreamRequest, process_live_audio_stream
from .db.db import init_db
from .kb.kb import answer_question, ingest_document_file, ingest_json, retrieve
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

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8501,http://127.0.0.1:8501",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
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


@app.post("/kb/ingest/file")
async def ingest_uploaded_document(
    file: UploadFile = File(...),
    title: str = Form("Uploaded document"),
    category: str = Form("general"),
    source: str = Form("uploaded://document"),
):
    try:
        suffix = Path(file.filename or "uploaded.txt").suffix.lower()
        if suffix not in {".txt", ".md", ".csv", ".json", ".pdf"}:
            raise ValueError("Unsupported file type. Use .txt, .md, .csv, .json, or .pdf.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        try:
            return ingest_document_file(temp_path, title=title, category=category, source=source or f"uploaded://{file.filename}")
        finally:
            os.unlink(temp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/kb/ingest/document")
async def ingest_document_alias(
    file: UploadFile = File(...),
    title: str = Form("Uploaded document"),
    category: str = Form("general"),
    source: str = Form("uploaded://document"),
):
    return await ingest_uploaded_document(file=file, title=title, category=category, source=source)


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