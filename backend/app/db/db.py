
import os

import psycopg
from pgvector.psycopg import register_vector


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://app:app_password@db:5432/assessment",
    )


def get_connection(register_vector_types: bool = True):
    conn = psycopg.connect(get_database_url())
    if register_vector_types:
        register_vector(conn)
    return conn


def init_db():
    with psycopg.connect(get_database_url()) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()

    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id BIGSERIAL PRIMARY KEY,
                record_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1.0',
                pii BOOLEAN NOT NULL DEFAULT FALSE,
                embedding VECTOR(1536) NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS knowledge_chunks_record_id_idx
            ON knowledge_chunks (record_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
            ON knowledge_chunks
            USING hnsw (embedding vector_cosine_ops)
            """
        )

        conn.commit()