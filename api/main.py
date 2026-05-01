import json
import os
from typing import Any

import asyncpg
import httpx
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

DATABASE_URL = os.environ["DATABASE_URL"]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")


api = FastAPI(title="Semantic Memory API")
mcp = FastMCP("semantic-memory")

pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL)
    return pool


async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
        r.raise_for_status()
        return r.json()["embedding"]


def vector_literal(v: list[float]) -> str:
    return "[" + ",".join(str(x) for x in v) + "]"


class RememberRequest(BaseModel):
    content: str
    kind: str = "raw"
    metadata: dict[str, Any] = {}


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@api.get("/health")
async def health():
    return {"ok": True}


@api.post("/remember")
async def remember_http(req: RememberRequest):
    return await remember(req.content, req.kind, req.metadata)


@api.post("/search")
async def search_http(req: SearchRequest):
    return await search_memories(req.query, req.limit)


@mcp.tool()
async def remember(
    content: str,
    kind: str = "raw",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Store a memory, note, document chunk, or derived summary.
    """
    metadata = metadata or {}
    emb = await embed(content)

    db = await get_pool()
    row = await db.fetchrow(
        """
        INSERT INTO memories (content, kind, metadata, embedding)
        VALUES ($1, $2, $3::jsonb, $4::vector)
        RETURNING id, created_at
        """,
        content,
        kind,
        json.dumps(metadata),
        vector_literal(emb),
    )

    return {
        "id": str(row["id"]),
        "created_at": row["created_at"].isoformat(),
    }


@mcp.tool()
async def search_memories(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Search stored memories by semantic similarity.
    """
    emb = await embed(query)

    db = await get_pool()
    rows = await db.fetch(
        """
        SELECT
          id,
          content,
          kind,
          metadata,
          created_at,
          1 - (embedding <=> $1::vector) AS similarity
        FROM memories
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        vector_literal(emb),
        limit,
    )

    return [
        {
            "id": str(r["id"]),
            "content": r["content"],
            "kind": r["kind"],
            "metadata": json.loads(r["metadata"])
            if isinstance(r["metadata"], str)
            else r["metadata"],
            "created_at": r["created_at"].isoformat(),
            "similarity": float(r["similarity"]),
        }
        for r in rows
    ]


@mcp.tool()
async def get_memory(id: str) -> dict[str, Any] | None:
    """
    Fetch a memory by id.
    """
    db = await get_pool()
    row = await db.fetchrow(
        """
        SELECT id, content, kind, metadata, created_at
        FROM memories
        WHERE id = $1::uuid
        """,
        id,
    )

    if row is None:
        return None

    return {
        "id": str(row["id"]),
        "content": row["content"],
        "kind": row["kind"],
        "metadata": json.loads(row["metadata"])
        if isinstance(row["metadata"], str)
        else row["metadata"],
        "created_at": row["created_at"].isoformat(),
    }


@mcp.tool()
async def delete_memory(id: str) -> bool:
    """
    Delete a memory by id.
    """
    db = await get_pool()
    result = await db.execute(
        "DELETE FROM memories WHERE id = $1::uuid",
        id,
    )
    return result.endswith("1")


app = FastAPI(title="Semantic Memory MCP Server")
app.mount("/api", api)
app.mount("/mcp", mcp.streamable_http_app())
