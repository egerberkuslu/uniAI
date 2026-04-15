# Claude ile uniAI MCP Server Bağlama Rehberi

Bu proje FastMCP ile MCP server olarak çalışabilir. Claude Desktop veya MCP destekleyen başka bir client bu server'a bağlanıp tool çağırabilir.

## 1. Önemli Mimari Karar

Production için önerilen akış:

```text
Claude / LLM Agent
  ↓ MCP tool call
uniAI MCP Server
  ↓ backend validation
RBAC + RAG + DB
  ↓ tool result
Claude / LLM Agent
  ↓ final answer
```

Kritik güvenlik sınırları:

- Claude SQL yazmaz.
- Claude RBAC filtresi belirlemez.
- Claude sadece MCP tool parametresi verir.
- Backend token doğrular.
- Backend RBAC uygular.
- Backend table/filter allowlist kontrolü yapar.
- Backend result döndürür.

## 2. Mevcut MCP Tool Listesi

`src/mcp/server.py` içinde kayıtlı tool'lar:

| Tool | Amaç |
|---|---|
| `search_knowledge` | RAG bilgi bankasında arama yapar. |
| `fetch_source` | Belirli RAG chunk kaynağını getirir. |
| `query_records` | RBAC filtreli tabloyu döndürür. |
| `query_records_intent` | SQL kabul etmeden structured DB intent çalıştırır. |
| `route_question` | Soru için structured route kararını döndürür. |
| `ask_question` | Backend-orchestrated uçtan uca cevap üretir. |
| `list_permissions` | Kullanıcının izinlerini listeler. |

## 3. En Önemli Tool: `query_records_intent`

Bu tool production açısından önemlidir çünkü SQL almaz.

Örnek input:

```json
{
  "token": "manager_token",
  "table": "ogrenci_bilgi_sistemi",
  "operation": "count",
  "filters": {
    "bolum": "electronics",
    "gpa_gt": 3.5
  }
}
```

Backend şunları yapar:

1. Token authenticate eder.
2. Kullanıcının RBAC scope'unu uygular.
3. Filter allowlist kontrolü yapar.
4. Kayıtları güvenli şekilde filtreler.
5. Sonucu döndürür.

Claude burada SQL yazmaz.

## 4. Claude Desktop İçin Local MCP Config

Claude Desktop MCP config dosyasına şu yapı eklenebilir.

> Not: Dosya yolu işletim sistemine göre değişebilir. Claude Desktop MCP config genelde `claude_desktop_config.json` içindedir.

Örnek config:

```json
{
  "mcpServers": {
    "uniai-rbac-rag": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/home/ege/Desktop/uniAI/rbac-rag-mcp",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "rbac_rag_db",
        "DB_USER": "postgres",
        "DB_PASSWORD": "postgres",
        "USE_CLAUDE_API": "false",
        "LOCAL_MODEL_NAME": "deepseek-r1:14b",
        "OLLAMA_HOST": "http://localhost:11434",
        "USE_LLM_ROUTER": "true",
        "EMBEDDING_MODEL": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
      }
    }
  }
}
```

## 5. Çalıştırma Önkoşulları

Önce DB ve embeddings hazır olmalı:

```bash
cd /home/ege/Desktop/uniAI/rbac-rag-mcp/deploy
docker compose up -d postgres
```

Gerekirse ingest çalıştır:

```bash
cd /home/ege/Desktop/uniAI/rbac-rag-mcp
python scripts/ingest.py
```

Ollama kullanıyorsan model hazır olmalı:

```bash
ollama pull deepseek-r1:14b
```

## 6. Manuel MCP Server Çalıştırma

Claude olmadan stdio server başlatmak:

```bash
cd /home/ege/Desktop/uniAI/rbac-rag-mcp
MCP_TRANSPORT=stdio python -m src.mcp.server
```

HTTP/streamable transport ile çalıştırmak:

```bash
cd /home/ege/Desktop/uniAI/rbac-rag-mcp
MCP_TRANSPORT=streamable-http MCP_HOST=127.0.0.1 MCP_PORT=8000 python -m src.mcp.server
```

## 7. Claude'a Nasıl Prompt Verilmeli?

Claude'a şu sistem yaklaşımı söylenmeli:

```text
You have access to uniAI MCP tools. Use route_question first for complex questions. Use search_knowledge for policy/document questions. Use query_records_intent for RBAC-safe database questions. Never ask for or generate SQL. Use fetch_source when you need the full cited source. Use ask_question only when you want backend-orchestrated final answer directly.
```

## 8. Örnek Claude Tool Kullanım Akışı

Soru:

```text
Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?
```

Beklenen tool akışı:

1. `route_question`
2. `search_knowledge`
3. `query_records_intent`
4. Gerekirse `fetch_source`
5. Claude final answer üretir

## 9. Neden `ask_question` de Var?

`ask_question` tüm işi backend'e yaptıran kısa yoldur.

Avantaj:

- Tek tool call.
- Backend route/RAG/DB/LLM akışını kendi yürütür.

Dezavantaj:

- Claude tool trace içinde ara adımları daha az görür.

Agentic kullanım için önerilen yol:

```text
route_question + search_knowledge + query_records_intent + fetch_source
```

Hızlı kullanım için:

```text
ask_question
```

## 10. Güvenlik Notları

- Token MCP tool parametresi olarak gelir.
- RBAC backend tarafında zorunlu uygulanır.
- `query_records_intent` SQL kabul etmez.
- Filterlar allowlist ile sınırlıdır.
- Public olmayan user document chunkları `fetch_source` içinde token görünürlüğüne göre filtrelenir.

