# Semantic Memory

Minimal **semantic memory layer** for use with AI agent harnesses, using Docker + FastAPI + pgvector + Ollama.

---

## What this does

Stores and retrieves text based on **semantic meaning**.

```
Text → embedding → stored in Postgres
Query → embedding → nearest neighbors → returned
```

---

## Why this exists

I wanted a simple semantic layer for my agent harness and figured I'd share it. This repo shows the **minimal core abstraction**:

> store text → embed it → retrieve by meaning

---

## Architecture

```
[Your app / agent]
        ↓
   MCP / HTTP API
        ↓
   FastAPI server
        ↓
Postgres (pgvector)
        ↑
   Ollama embeddings
```

---

## Quick Start

### 1. Install [Ollama](https://ollama.com/) and pull an embedding model

```bash
ollama pull bge-m3
ollama serve
```

You can use any embedding model you choose, but you need to make sure that the vector size of the `embedding` field matches that of your model. See [Vector Size](#vector-size) 

---

### 2. Start the stack

```bash
docker compose up --build
```

---

### 3. Test it

Store a memory:

```bash
curl -X POST http://localhost:8000/api/remember \
  -H "Content-Type: application/json" \
  -d '{"content":"Postgres uses MVCC for concurrency control.","kind":"raw"}'
```

Search:

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"How do databases handle concurrent writes?","limit":5}'
```

You should retrieve the Postgres note.

---

## 🤖 MCP Endpoint

```
http://localhost:8000/mcp
```

Exposed tools:

- `remember`
- `search_memories`
- `get_memory`
- `delete_memory`

---

## Minimal MCP Configuration

```
{
  "mcpServers": {
    "semantic-memory": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

---

## Vector Size

The `embedding` column in Postgres must match the dimensionality of your embedding model.

Example:

#### `api/db.sql`
```sql
...
embedding vector(1024)
...
```

For this project:

- `bge-m3` → 1024 dimensions

If you switch embedding models, you **must update the schema** accordingly.

---

### Important

Vector size is not a runtime setting.

If you change it after data has been inserted:

- existing embeddings will be incompatible  
- queries will fail  

You will need to:

1. Drop the database (or table)  
2. Recreate it with the new vector size  
3. Re-embed all stored content  

---

## Ollama Networking

This project assumes Ollama is running outside the Docker environment. The API needs to reach Ollama, but you probably do **not** want Ollama exposed to the whole LAN.

### Option A: Bind to Docker bridge only

Bind Ollama to the Docker bridge IP:

```ini
OLLAMA_HOST=172.17.0.1:11434
```

Then set:

```env
OLLAMA_URL=http://172.17.0.1:11434
```

### Option B: Add a localhost proxy

Keep Ollama bound to the Docker bridge, then proxy localhost access:

```bash
socat TCP-LISTEN:11435,bind=127.0.0.1,fork TCP:172.17.0.1:11434
```

Then call:

```bash
curl http://127.0.0.1:11435/api/tags
```

### Option C: Bind to all interfaces

```ini
OLLAMA_HOST=0.0.0.0:11434
```

**Risk:** this can expose Ollama to your entire LAN, or worse if your machine/firewall is misconfigured.

Only use this with firewall rules:

```bash
sudo ufw deny 11434
sudo ufw allow in on docker0 to any port 11434
sudo ufw allow from 127.0.0.1 to any port 11434
```

---

## License

MIT