CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content text NOT NULL,
  kind text DEFAULT 'raw',
  metadata jsonb DEFAULT '{}',
  -- vector size is determined by the embedding model architecture
  embedding vector(1024) NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memories_embedding_hnsw
ON memories USING hnsw (embedding vector_cosine_ops);
