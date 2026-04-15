# RBAC RAG MCP

Containerised MCP gateway exposing RAG + RBAC microservice behaviour with LangChain-powered retrieval and PostgreSQL/pgvector storage.

## Quick Start

1. Copy the sample environment file and adjust secrets if needed:

   ```bash
   cp .env.example .env
   ```

2. Build and start the stack (Postgres + ingestion job + MCP server + web UI):

   ```bash
   docker compose up --build
   ```

   The `ingest` one-shot service seeds embeddings after the SQL seed runs. The `mcp` service exposes port `8000`, while the bundled chatbot UI lives at `http://localhost:3000` (served by the `web` service).

   If you want to use a local LLM via Ollama in Docker, the compose file includes an `ollama` service on port `11434`. The `mcp` service points to it via `OLLAMA_HOST=http://ollama:11434`. You may need to pull your chosen model first (from your host or by shelling into the container) e.g. `docker exec -it rbac-rag-ollama ollama pull deepseek-r1:14b`.

3. Re-run ingestion manually after updating documents:

   ```bash
   docker compose run --rm ingest
   ```

4. Open the playground UI at `http://localhost:3000`, paste one of the seeded tokens (e.g., `admin_token`, `manager_token`), and try uploading a new document via the "Upload Knowledge Document" pane to verify ingestion.

5. Stop everything and remove volumes when you need a clean slate:

   ```bash
   docker compose down -v
   ```

## Local Development

- Install dependencies with `pip install -e .[dev]`.
- Export a local `.env` (see `.env.example`).
- Run the MCP server directly: `python -m src.mcp.server`.
- Populate embeddings locally with `python scripts/ingest.py` (requires a running PostgreSQL matching `.env`).
- For Turkish or mixed-language documents, use the default multilingual embedding model in `.env` and re-run ingestion after changing the model so existing vectors are rebuilt.
- Launch the FastAPI playground: `uvicorn src.web.app:app --reload`.

### Using a local Ollama model

- To run with an Ollama model (e.g. `deepseek-r1:14b`), install and start Ollama locally and pull the model:

  ```bash
  ollama pull deepseek-r1:14b
  ```

- Set `USE_CLAUDE_API=false` and `LOCAL_MODEL_NAME=deepseek-r1:14b` in `.env`. Optionally set `OLLAMA_HOST` if not on the default `http://localhost:11434`.

- If `LOCAL_MODEL_NAME` contains a colon (`:`), the app will route generation requests to Ollama. Otherwise it loads a Hugging Face model via `transformers`.

## Testing

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest
```

Integration tests require `RUN_INTEGRATION_TESTS=1` and a reachable PostgreSQL/pgvector instance populated via `scripts/setup_db.py`.

## Claude / MCP Client Integration

This project can run as a FastMCP server for Claude Desktop or any MCP-compatible client.

Recommended local stdio server:

```bash
cd /home/ege/Desktop/uniAI/rbac-rag-mcp
MCP_TRANSPORT=stdio python -m src.mcp.server
```

Available MCP tools:

- `route_question` — return structured route intent without executing the final answer flow.
- `search_knowledge` — search RAG knowledge chunks.
- `fetch_source` — fetch a cited source chunk by `chunk_id` with visibility checks.
- `query_records` — query a protected table with RBAC filtering.
- `query_records_intent` — run a structured, RBAC-safe DB intent without accepting SQL.
- `ask_question` — run the backend-orchestrated full answer flow.
- `list_permissions` — show authenticated user's permissions.

Claude Desktop setup details are documented in `docs/CLAUDE_MCP_SETUP_TR.md`.
# uniAI
