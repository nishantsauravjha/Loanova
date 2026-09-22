
import json
import os
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


def ingest_json(path: str | None = None) -> dict[str, Any]:
    resolved_path = Path(path or "/data/raw/loan_knowledge.json")
    records = json.loads(resolved_path.read_text())
    vector_store = get_vector_store()
    total_chunks = 0

    for record in records:
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

    return {"ingested_records": len(records), "ingested_chunks": total_chunks}


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