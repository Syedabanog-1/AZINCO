-- AZINCO Step 0.2 — runs once, as the bootstrap superuser, on an empty data volume.
-- Extensions are created by the superuser; application roles cannot create extensions.

CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector: RAG embeddings (BS §7.6)
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), digest() for hash chains (BS §8.2)
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive e-mail addresses
