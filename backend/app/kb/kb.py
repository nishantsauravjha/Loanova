
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..db.db import get_connection


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://app:app_password@db:5432/assessment")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_embeddings() -> OpenAIEmbeddings:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set")
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


def get_chat_model() -> ChatOpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


def get_vector_store() -> PGVector:
    return PGVector(
        embeddings=get_embeddings(),
        connection=get_database_url(),
        collection_name="loan_knowledge_demo",
        create_extension=False,
    )


def chunk_text(text: str, size: int = 600, overlap: int = 120) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _redact_pii(value: str) -> tuple[str, bool]:
    cleaned = value or ""
    email_pattern = r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    phone_pattern = r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?){2,}\d{3,4}(?!\w)"
    id_pattern = r"\b(?:\d{3}-\d{2}-\d{4}|\d{9,}\b)"
    found_pii = bool(re.search(email_pattern, cleaned) or re.search(phone_pattern, cleaned) or re.search(id_pattern, cleaned))
    cleaned = re.sub(email_pattern, "[email redacted]", cleaned)
    cleaned = re.sub(phone_pattern, "[phone redacted]", cleaned)
    cleaned = re.sub(id_pattern, "[id redacted]", cleaned)
    return cleaned, found_pii


def prepare_records_for_ingestion(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    cleaned_records: list[dict[str, Any]] = []

    for raw_record in records or []:
        if not isinstance(raw_record, dict):
            continue
        record_id = str(raw_record.get("record_id") or "unknown_record").strip() or "unknown_record"
        title = _normalize_text(raw_record.get("title") or record_id)
        category = _normalize_text(raw_record.get("category") or "general")
        source = _normalize_text(raw_record.get("source") or "unknown")
        version = str(raw_record.get("version") or "1.0").strip() or "1.0"
        content = _normalize_text(raw_record.get("content") or "")
        content, pii_flag = _redact_pii(content)
        pii_flag = bool(raw_record.get("pii", False)) or pii_flag

        key = (
            record_id,
            title.lower(),
            category.lower(),
            source.lower(),
            content.lower(),
        )
        if key in seen:
            continue
        seen.add(key)

        cleaned_records.append(
            {
                "record_id": record_id,
                "title": title,
                "category": category,
                "source": source,
                "version": version,
                "content": content,
                "pii": pii_flag,
            }
        )

    return cleaned_records


def _read_document_text(path: str | Path) -> str:
    resolved_path = Path(path)
    suffix = resolved_path.suffix.lower()
    ocr_notice = " OCR is not supported for scanned PDFs in this repository."

    if suffix == ".json":
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return json.dumps(payload)
        if isinstance(payload, dict):
            if isinstance(payload.get("records"), list):
                return json.dumps(payload["records"])
            if payload.get("content"):
                return str(payload["content"])
        raise ValueError("Unsupported JSON document payload. Expected a list of records or a content field.")

    if suffix in {".txt", ".md", ".csv"}:
        content = resolved_path.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            raise ValueError("No readable text was extracted from the uploaded file.")
        return content

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError("PDF parsing requires pypdf, which is not available in the selected environment.") from None

        try:
            reader = PdfReader(str(resolved_path))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pragma: no cover - exercised through runtime PDF validation
            raise ValueError(f"Could not read the uploaded PDF: {exc}. OCR is not supported for scanned PDFs in this repository.") from exc

        text = "\n\n".join(page for page in pages if page.strip())
        if not text.strip():
            raise ValueError(
                "No readable text was extracted from the uploaded PDF. The file may be empty, scanned, or corrupt."
                + ocr_notice
            )
        return text

    raise ValueError(f"Unsupported document type: {suffix or 'unknown'}")


def _build_record_from_document(path: str | Path, title: str | None = None, category: str | None = None, source: str | None = None) -> dict[str, Any]:
    resolved_path = Path(path)
    stem = resolved_path.stem or "uploaded_document"
    record_id = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "uploaded_document"
    text = _read_document_text(resolved_path)
    return {
        "record_id": record_id,
        "title": title or stem.replace("_", " ").strip() or "Uploaded Document",
        "category": category or "general",
        "source": source or f"uploaded://{resolved_path.name}",
        "version": "1.0",
        "content": text,
        "pii": False,
    }


def ingest_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    cleaned_records = prepare_records_for_ingestion(records)
    vector_store = get_vector_store()
    total_chunks = 0

    for record in cleaned_records:
        metadata = {
            "record_id": record["record_id"],
            "title": record["title"],
            "category": record["category"],
            "source": record["source"],
            "version": record.get("version", "1.0"),
            "pii": bool(record.get("pii", False)),
        }
        chunks = [
            Document(
                page_content=chunk,
                metadata={**metadata, "chunk_index": idx},
            )
            for idx, chunk in enumerate(chunk_text(record["content"]))
        ]

        if chunks:
            ids = [f"{record['record_id']}_{idx}" for idx in range(len(chunks))]
            vector_store.add_documents(chunks, ids=ids)

        with get_connection() as conn:
            for idx, chunk in enumerate(chunk_text(record["content"])):
                vector = get_embeddings().embed_query(chunk)
                conn.execute(
                    """
                    INSERT INTO knowledge_chunks
                    (record_id, title, content, category, source, version, pii, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record["record_id"],
                        record["title"],
                        chunk,
                        record["category"],
                        record["source"],
                        record.get("version", "1.0"),
                        bool(record.get("pii", False)),
                        vector,
                    ),
                )
            conn.commit()
        total_chunks += len(chunks)

    return {"ingested_records": len(cleaned_records), "ingested_chunks": total_chunks}


def ingest_json(path: str | None = None) -> dict[str, Any]:
    resolved_path = Path(path or "/data/raw/loan_knowledge.json")
    records = json.loads(resolved_path.read_text(encoding="utf-8"))
    if isinstance(records, dict) and isinstance(records.get("records"), list):
        records = records["records"]
    return ingest_records(records)


def ingest_document_file(path: str | Path, title: str | None = None, category: str | None = None, source: str | None = None) -> dict[str, Any]:
    resolved_path = Path(path)
    if resolved_path.suffix.lower() == ".json":
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return ingest_records(payload)
        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            return ingest_records(payload["records"])

    record = _build_record_from_document(path, title=title, category=category, source=source)
    return ingest_records([record])


def retrieve(question: str, limit: int = 4) -> list[dict[str, Any]]:
    vector_store = get_vector_store()
    docs_with_scores = vector_store.similarity_search_with_score(question, k=limit)

    records: list[dict[str, Any]] = []
    for document, score in docs_with_scores:
        metadata = document.metadata or {}
        similarity = max(0.0, min(1.0, 1.0 - float(score)))
        records.append(
            {
                "record_id": metadata.get("record_id") or metadata.get("id", "unknown"),
                "title": metadata.get("title", "Untitled"),
                "content": document.page_content,
                "category": metadata.get("category", "general"),
                "source": metadata.get("source", "unknown"),
                "version": metadata.get("version", "1.0"),
                "pii": bool(metadata.get("pii", False)),
                "similarity": similarity,
            }
        )
    return records


def _serialize_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "record_id": chunk["record_id"],
            "title": chunk["title"],
            "source": chunk["source"],
            "similarity": chunk.get("similarity"),
            "category": chunk.get("category"),
        }
        for chunk in chunks
    ]


def _format_citation_text(chunks: list[dict[str, Any]]) -> str:
    return ", ".join(
        f"[{chunk['record_id']}] {chunk['title']} ({chunk['source']})"
        for chunk in chunks
    )


def answer_question(question: str):
    chunks = retrieve(question, limit=4)
    normalized_question = question.lower()

    unsupported_terms = [
        "apr",
        "annual percentage rate",
        "interest rate",
        "processing fee",
        "monthly payment",
        "approval",
        "approve",
        "approved",
        "eligibility",
        "eligible",
    ]
    has_relevant_chunks = bool(chunks) and chunks[0].get("similarity", 0) >= 0.25

    if any(term in normalized_question for term in unsupported_terms):
        if has_relevant_chunks:
            fallback = (
                "The requested loan rates, fees, eligibility, or approvals are unavailable in the demo knowledge base. "
                "This system supports synthetic, non-binding guidance only and can collect preliminary details or arrange a human follow-up."
            )
            return {
                "answer": f"{fallback}\n\nCitations: {_format_citation_text(chunks)}",
                "sources": _serialize_sources(chunks),
                "grounded": False,
            }
        return {
            "answer": (
                "The requested loan rates, fees, eligibility, or approvals are unavailable in the demo knowledge base. "
                "This system supports synthetic, non-binding guidance only and can collect preliminary details or arrange a human follow-up."
            ),
            "sources": [],
            "grounded": False,
        }

    if not chunks or chunks[0]["similarity"] < 0.25:
        return {
            "answer": (
                "I couldn’t find reliable support for that topic in the current knowledge base. "
                "I can collect preliminary qualification details or connect you with a human specialist."
            ),
            "sources": [],
            "grounded": False,
        }

    context = "\n\n".join(
        f"[{chunk['record_id']}] {chunk['title']} ({chunk['source']}): {chunk['content']}"
        for chunk in chunks
    )
    model = get_chat_model()
    response = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are a safe demo lending assistant. Answer using only the provided knowledge. "
                    "Never invent loan rates, fees, eligibility, approvals, or repayment terms. "
                    "If the knowledge does not support a claim, say the information is unavailable. "
                    "Present the answer in plain language and include citations using [record_id]."
                )
            ),
            HumanMessage(content=f"Question: {question}\n\nKnowledge:\n{context}"),
        ]
    )

    answer_text = (response.content or "").strip()
    final_answer = f"{answer_text}\n\nCitations: {_format_citation_text(chunks)}"

    return {
        "answer": final_answer,
        "sources": _serialize_sources(chunks),
        "grounded": True,
    }