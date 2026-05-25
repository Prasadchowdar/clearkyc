-- Runs once on first DB boot (docker-entrypoint-initdb.d).
-- Enable pgvector now so Phase 2 RAG (rule embeddings) needs no migration.
CREATE EXTENSION IF NOT EXISTS vector;
