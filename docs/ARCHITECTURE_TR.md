# rbac-rag-mcp — Mimarisi ve Detaylı Çalışma Rehberi

Bu doküman, projedeki her bileşenin nasıl çalıştığını, birbirleriyle nasıl etkileşime girdiğini ve verinin nasıl aktığını açıklar.

---

## İçindekiler

1. [Proje Genel Bakış](#1-proje-genel-bakış)
2. [Mimari Diyagram](#2-mimari-diyagram)
3. [Veritabanı Katmanı (Database Layer)](#3-veritabanı-katmanı)
4. [RBAC — Rol Bazlı Erişim Kontrolü](#4-rbac--rol-bazlı-erişim-kontrolü)
5. [RAG — Erişim Artırılmış Üretim (Retrieval-Augmented Generation)](#5-rag--erişim-artırılmış-üretim)
6. [LLM — Büyük Dil Modeli (Large Language Model)](#6-llm--büyük-dil-modeli)
7. [Router — Soru Yönlendirme Sistemi](#7-router--soru-yönlendirme-sistemi)
8. [MCP — Model Context Protocol Sunucusu](#8-mcp--model-context-protocol-sunucusu)
9. [Web API — FastAPI HTTP Arayüzü](#9-web-api--fastapi-http-arayüzü)
10. [Oturum Yönetimi (Session Management)](#10-oturum-yönetimi)
11. [Metin İşleme ve Normalizasyon](#11-metin-i̇şleme-ve-normalizasyon)
12. [Veri Akışı — Uçtan Uca Senaryolar](#12-veri-akışı--uçtan-uca-senaryolar)
13. [Yapılandırma (Configuration)](#13-yapılandırma)
14. [Docker Dağıtımı](#14-docker-dağıtımı)

---

## 1. Proje Genel Bakış

**rbac-rag-mcp**, bir üniversite öğrenci bilgi asistanıdır. Kullanıcılar Türkçe veya İngilizce doğal dil soruları sorar ve sistem şu üç yoldan biriyle yanıt verir:

| Rota | Açıklama | Veri Kaynağı |
|------|----------|-------------|
| **RAG** | Bilgi tabanında belge arama | `kb_documents` + `kb_chunks` (pgvector) |
| **MCP** | Rol bazlı veritabanı sorgulama | `orders`, `refunds`, `ogrenci_bilgi_sistemi` |
| **HYBRID** | Her ikisini birden | RAG + MCP sonuçlarını birleştirir |

Sistem, soruyu analiz edip otomatik olarak doğru rotaya yönlendirir. Ardından LLM (Büyük Dil Modeli) ile insani bir yanıt üretir.

**Temel Özellikler:**
- RBAC ile korumalı veritabanı erişimi (admin/manager/viewer)
- Vektör benzerlik + sözlüksel arama hibrit RAG
- MCP protokolü ile dış araç entegrasyonu
- Ollama veya Claude API ile LLM yanıtlama
- FastAPI web arayüzü ve REST API
- Oturum bazlı token yönetimi

---

## 2. Mimari Diyagram

```
Kullanıcı (Tarayıcı / MCP Client)
    |
    v
+-------------------+     +-------------------+
|   Web UI (HTML)   |     |   MCP Client      |
|   :8080           |     |   :8000           |
+--------+----------+     +--------+----------+
         |                         |
         v                         v
+-------------------+     +-------------------+
|  FastAPI (app.py) |     |  FastMCP          |
|  REST API         |     |  MCP Server       |
+--------+----------+     +--------+----------+
         |                         |
         +------------+------------+
                      |
                      v
              +-------+-------+
              |  MCPServer     |  (Orkestrasyon katmanı)
              |  (server.py)   |
              +-------+--------+
                      |
       +--------------+--------------+--------------+
       |              |              |              |
       v              v              v              v
+------+-----+ +-----+------+ +----+-------+ +---+--------+
| RBACEngine | | RAGPipeline | | LLMProvider| | Router     |
| (auth +    | | (vector +   | | (Ollama /  | | (classify  |
|  query)    | |  lexical)   | |  Claude)   | |  + route)  |
+------+-----+ +-----+------+ +----+-------+ +---+--------+
       |              |                         |
       v              v                         v
+------+-----+ +-----+------+          +-------+--------+
| Database   | | VectorStore|          | ContextBuilder |
| Manager    | | + Chunker  |          | (prompt build) |
+------+-----+ +------------+          +----------------+
       |
       v
+------+------------+
|  PostgreSQL       |
|  + pgvector       |
|  :5432            |
+-------------------+
```

---

## 3. Veritabanı Katmanı

### 3.1 Şema Yapısı

Veritabanı iki kategoriye ayrılır:

#### Korumalı Tablolar (RBAC — rol bazlı erişim)

```sql
roles              -- 3 rol: admin(level 3), manager(level 2), viewer(level 1)
users              -- 5 kullanıcı, token ile kimlik doğrulama
role_permissions   -- her rolün hangi tabloya hangi kapsamda erişeceği
orders             -- 10 sipariş kaydı (department bazlı)
refunds            -- 6 iade kaydı (department bazlı)
ogrenci_bilgi_sistemi  -- 6 öğrenci kaydı (bolum/advisor_id bazlı)
```

#### Açık Tablolar (RAG — erişim kontrolü yok)

```sql
kb_documents       -- 8 üniversite yönetmelik belgesi + kullanıcı yüklemeleri
kb_chunks          -- belgelerin parçalanmış hali + 384-boyutlu vektör embedding'ler
```

### 3.2 Roller ve Erişim Kapsamları

| Rol | Açıklama | Erişim Kapsamı | Filtre Mantığı |
|-----|----------|---------------|----------------|
| **admin** (level 3) | Tam yetkili | `ALL` | Filtre yok — tüm kayıtları görür |
| **manager** (level 2) | Bölüm yetkilisi | `DEPARTMENT` | `WHERE department = kullanıcı.bolum` |
| **viewer** (level 1) | Danışman/öğrenci | `OWN` | `WHERE assigned_to/advisor_id = kullanıcı.id` |

**Örnek:**
- Alice Chen (admin) → `SELECT * FROM ogrenci_bilgi_sistemi` → 6 kayıt
- Bob Martinez (manager, electronics) → `WHERE bolum = 'electronics'` → 3 kayıt
- Charlie Kim (viewer, advisor_id=3) → `WHERE advisor_id = 3` → 1 kayıt

### 3.3 DatabaseManager (`src/db/manager.py`)

Tüm PostgreSQL işlemlerini tek sınıfta toplar. `psycopg2` ile bağlanır, `RealDictCursor` kullanır.

**Temel Metotlar:**

| Metot | İşlev |
|-------|-------|
| `get_user_by_token(token)` | Token ile kullanıcıyı bulur, rol ve yetkilerini yükler |
| `query_records(user, table)` | RBAC filtresi uygulayıp `QueryResult` döndürür |
| `search_similar_chunks(embedding, top_k)` | pgvector ile kosinüs benzerlik araması |
| `store_chunk(doc_id, text, index, embedding)` | Parça ve vektörü kaydeder |
| `create_document(title, content, category, user_id)` | Yeni belge oluşturur |
| `get_user_documents(user_id)` | Kullanıcının yüklediği belgeleri listeler |
| `delete_document(doc_id, user_id)` | Kullanıcının kendi belgesini siler |

**RBAC Filtreleme Mantığı** (`_build_filters` metodu):

```python
# scope == ALL     → WHERE yok
# scope == DEPARTMENT → WHERE department = 'electronics'
# scope == OWN     → WHERE assigned_to = 3

# ogrenci_bilgi_sistemi tablosu için:
# DEPARTMENT → WHERE bolum = 'electronics'
# OWN       → WHERE advisor_id = 3
```

---

## 4. RBAC — Rol Bazlı Erişim Kontrolü

RBAC sistemi üç bileşenden oluşur:

### 4.1 Authenticator (`src/rbac/auth.py`)

```python
class Authenticator:
    def authenticate(self, token: str) -> User:
        return self._db.get_user_by_token(token)
```

Token'ı alır, veritabanında arar. Bulamazsa `AuthenticationError` fırlatır. Bulursa `User` nesnesi döndürür.

### 4.2 RBACEngine (`src/rbac/engine.py`)

```python
class RBACEngine:
    def authenticate(self, token) -> User       # Authenticator'a delege eder
    def query(self, user, table) -> QueryResult  # RBAC filtreli sorgu
    def get_permissions_summary(self, user)      # Yetki özeti
```

Kimlik doğrulama + yetkilendirme + sorgulama işlemlerini birleştiren üst düzey arayüz.

### 4.3 User ve Permission Modelleri (`src/models/`)

```python
@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str
    role: Role                    # admin / manager / viewer
    department: str               # all / electronics / clothing / books
    permissions: tuple[Permission]

    def has_permission(self, resource, action) -> AccessScope | None:
        # Kullanıcının belirli bir kaynağa erişim kapsamını döndürür
        # Erişim yoksa None döner
```

```python
class Role(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"

class AccessScope(Enum):
    ALL = "all"            # Tüm kayıtlar
    DEPARTMENT = "department"  # Sadece kendi bölümü
    OWN = "own"            # Sadece kendi kayıtları
```

### 4.4 Yetki Kontrol Akışı

```
1. Kullanıcı token gönderir
2. Authenticator → DatabaseManager.get_user_by_token(token)
3. User nesnesi oluşturulur (id, name, role, department, permissions)
4. User.has_permission("ogrenci_bilgi_sistemi", "read") → AccessScope döner
5. DatabaseManager._build_filters(user, table, scope) → SQL WHERE oluşturulur
6. Sorgu çalıştırılır, filtrelenmiş kayıtlar döner
```

---

## 5. RAG — Erişim Artırılmış Üretim

RAG sistemi, kullanıcının sorusuna bilgi tabanından (kb_documents) ilgili parçalar bulur.

### 5.1 Bileşenler

#### VectorStore (`src/rag/vector_store.py`)

HuggingFace `sentence-transformers` modelini kullanarak metni 384-boyutlu vektörlere dönüştürür.

```python
class VectorStore:
    # Model: paraphrase-multilingual-MiniLM-L12-v2
    # 384 boyut, çok dilli (Türkçe dahil)

    def encode_document(text) -> list[float]  # Belge parçasını vektöre çevirir
    def encode_query(text) -> list[float]     # Sorguyu vektöre çevirir
```

Her iki metot da `augment_for_embedding()` fonksiyonunu kullanır — orijinal metne ASCII-folded versiyonunu ekler, böylece Türkçe karakter sorunu azalır.

#### TextChunker (`src/rag/chunker.py`)

LangChain `RecursiveCharacterTextSplitter` kullanarak belgeleri parçalar.

```python
class TextChunker:
    # chunk_size = 200 kelime
    # chunk_overlap = 50 kelime
    # separators: ["\n\n", "\n", ". ", " "] — paragraf, satır, cümle, kelime

    def chunk(document_id, title, text) -> list[Document]:
        # Her parçaya metadata ekler: document_id, title, chunk_index
```

**Parçalama stratejisi:** Önce `\n\n` (paragraf) ile böler. Paragraf büyükse `\n` (satır) ile, sonra `. ` (cümle) ile, en son boşlukla böler.

#### RAGPipeline (`src/rag/pipeline.py`)

Arama motoru — iki farklı algoritmayı birleştirir:

##### A. Vektör Araması (Semantic Search)

```
Sorgu metni → encode_query() → 384-boyutlu vektör
    → pgvector: cosine similarity (1 - (embedding <=> query_vector))
    → En yakın top_k*4 aday
```

PostgreSQL'deki `<=>` operatörü kosinüs mesafesini hesaplar. `1 - mesafe = benzerlik skoru`.

##### B. Sözlüksel Arama (Lexical Search)

```
Sorgu metni → tokenize_for_matching() → token'lara ayrılır
    → Her kb_chunks kaydı ile karşılaştırılır
    → Bigram ve trigram örtüşmesi hesaplanır
    → Türkçe sonek çıkarma (50+ sonek)
    → Başlık ödüllendirme (title_boost)
    → Kelime öbeği eşleşme bonusu (phrase_bonus)
```

**Skorlama formülü:**
```
lexical_score = (title_coverage × 0.75)
              + (text_coverage × 0.45)
              + (title_bigram × 1.2)
              + (title_trigram × 1.35)
              + (bigram × 0.8)
              + (trigram × 0.9)
              + phrase_bonus + title_bonus
```

##### C. Sonuç Birleştirme (Merge)

Her iki aramadan gelen sonuçlar chunk_id üzerinden eşleştirilir:

```
combined_score = max(vector_score, lexical_score, vector×0.45 + lexical×0.85)
```

Ardından başlık bigram örtüşmesine göre sıralanıp ilk `top_k` sonuç seçilir.

### 5.2 Belge Yükleme (Ingestion)

```
1. Metin alınır (dosya yükleme veya API)
2. TextChunker ile parçalara ayrılır
3. Her parça VectorStore ile vektöre dönüştürülür
4. kb_chunks tablosuna embedding ile kaydedilir
```

Kullanıcı yüklemelerinde `user_id` kaydedilir — böylece sadece belgeyi yükleyen kullanıcı ve admin o belgeyi görebilir.

---

## 6. LLM — Büyük Dil Modeli

### 6.1 Soyut Arayüz

```python
class LLMProvider(ABC):
    def generate(system_prompt, user_message, max_tokens) -> str
    def get_model_name() -> str
```

### 6.2 Fabrika Deseni (Factory Pattern)

`LLMProviderFactory.create(config)` yönlendirmesi:

```
USE_CLAUDE_API=true  → ClaudeProvider     (Anthropic API)
model_name ":" içeriyor → OllamaProvider   (Yerel Ollama HTTP)
diğer              → LocalProvider      (HuggingFace transformers)
```

### 6.3 Sağlayıcılar

#### ClaudeProvider (`src/llm/claude_provider.py`)

Anthropic API SDK kullanır. `ANTHROPIC_API_KEY` çevresel değişkeni gereklidir.

```
system_prompt + user_message → Anthropic API → yanıt metni
```

#### OllamaProvider (`src/llm/ollama_provider.py`)

Yerel Ollama sunucusuyla HTTP üzerinden konuşur.

```
1. Model varlığını kontrol eder: GET /api/tags
2. Sohbet isteği gönderir: POST /api/chat
3. Yanıtı parse eder: response["message"]["content"]
```

- `temperature: 0.1` (düşük yaratıcılık, tutarlı yanıtlar)
- `stream: false` (tek seferde tam yanıt)

#### LocalProvider (`src/llm/local_provider.py`)

HuggingFace `transformers` kütüphanesi ile modeli doğrudan belleğe yükler.

```
1. AutoTokenizer + AutoModelForCausalLM ile model yüklenir
2. GPU varsa float16 + CUDA, yoksa CPU + float32
3. apply_chat_template() ile sohbet formatı oluşturulur
4. model.generate() ile yanıt üretilir
5. Sadece yeni token'lar decode edilir (prompt hariç)
```

- `repetition_penalty: 1.2` (tekrar döngüsünü önler)
- `temperature: 0.7` (hafif yaratıcılık)

---

## 7. Router — Soru Yönlendirme Sistemi

Router, kullanıcının sorusunun RAG, MCP veya HYBRID rotasına mı ait olduğunu belirler.

### 7.1 Deterministic Router (`src/router/classifier.py`)

Anahtar kelime bazlı yönlendirme:

**RAG Anahtar Kelimeleri:** yönerge, politika, kural, ne zaman, nasıl, nedir, kredi, not, ortalama, devamsızlık, mezuniyet, yurt, burs, sınav, mali...

**MCP Anahtar Kelimeleri:** sipariş, iade, öğrenci, bakiye, kayıt, müşteri, order, refund, student...

**MCP Eylem Kelimeleri:** kaç, liste, göster, say, toplam, ortalama, en yüksek, en düşük...

**Yönlendirme Mantığı:**

```
RAG kelime + MCP eylem kelime → HYBRID
Sadece MCP kelime/eylem       → MCP
Sadece RAG kelime              → RAG
Hiçbiri                       → RAG (fallback: vektör araması dener)
```

**Tablo ve İşlem Algılama:**
- Tablo: ogrenci_bilgi_sistemi, orders, refunds
- İşlem: count, sum, average, max, min, list
- Filtre: bolum, department, status gibi alanlar

### 7.2 LLM Router (`src/router/llm_router.py`)

LLM kullanarak yapısal JSON yönlendirme kararı üretir. Deterministic router'ı fallback olarak kullanır.

```
1. LLM'e sistem prompt'u + soru gönderilir
2. LLM yapısal JSON yanıt üretir:
   {
     "route": "hybrid",
     "rag_query": "W notu ne zaman verilir",
     "db_table": "ogrenci_bilgi_sistemi",
     "db_intent": {"table": "...", "operation": "count", "filters": {...}},
     "confidence": 0.9
   }
3. Pydantic ile doğrulanır (StructuredRoute, StructuredDBIntent)
4. Geçersiz ise deterministic router'a düşer
```

**Filtre Doğrulama:** Her tablo için izin verilen filtreler (`ALLOWED_FILTERS`) tanımlanır. İzin verilmeyen filtreler yok sayılır.

### 7.3 ContextBuilder (`src/router/context_builder.py`)

LLM'in yanıtlaması için sistem ve kullanıcı prompt'larını oluşturur.

**Sistem Promptu:**
- Kullanıcının rolü ve bölümü
- Dil talimatı (Türkçe algılama)
- Alıntı talimatı ([1], [2] gibi referanslar)

**Kullanıcı Mesajı:**
- Orijinal soru
- RAG sonuçları (numaralı kaynaklar)
- MCP sonuçları (tablo verisi)
- Otomatik "GPA özeti" (ogrenci_bilgi_sistemi için)

---

## 8. MCP — Model Context Protocol Sunucusu

### 8.1 MCP Nedir?

MCP (Model Context Protocol), LLM uygulamalarının dış araçlarla (tools) standart bir protokolle iletişim kurmasını sağlar. Claude Desktop, Cursor gibi istemciler MCP sunucularına bağlanıp araç çağırabilir.

### 8.2 MCPServer (`src/mcp/server.py`)

Tüm bileşenleri birleştiren ana orkestratör sınıf.

#### Kayıtlı MCP Araçları

| Araç | İşlev | Token Gerekli? |
|------|-------|----------------|
| `search_knowledge` | Bilgi tabanında arama | Hayır |
| `query_records` | RBAC filtreli tablo sorgusu | Evet |
| `query_records_intent` | Yapısal DB sorgusu | Evet (veya session) |
| `fetch_source` | Kaynak parça getirme | Evet |
| `ask_question` | Tam soru-yanıt pipeline'ı | Evet |
| `route_question` | Yönlendirme kararı önizleme | Evet (veya session) |
| `list_permissions` | Kullanıcı yetki özeti | Evet |
| `set_user_token` | Oturum token'ı ayarla | Evet (ayarlanan token) |
| `get_current_token` | Mevcut oturum bilgisi | Hayır |
| `clear_token` | Oturumu temizle | Hayır |

#### ask_question Akışı (Tam Pipeline)

```
1. authenticate(token) → User nesnesi
2. route(question) → RoutingDecision (RAG/MCP/HYBRID)
3. RAG gerekli ise:
   rag.search(query, user_id) → vektör + sözlüksel sonuçlar
4. MCP gerekli ise:
   rbac.query(user, table) → filtrelenmiş DB kayıtları
   _apply_db_intent(result, intent) → istem filtreleri uygulanır
5. context_builder.build_system_prompt(user, question)
   context_builder.build_user_message(question, rag_results, db_result)
6. llm.generate(system_prompt, user_message) → yanıt metni
7. _normalize_rag_citations(answer, rag_results) → [başlık] → [1] dönüşümü
8. AssistantResponse oluşturulur ve döndürülür
```

### 8.3 SessionManager

MCP sunucusu içinde bellek-tabanlı oturum deposu:

```python
class SessionManager:
    _sessions: dict[str, str] = {}  # session_id → token

    # Başlangıçta DEFAULT_USER_TOKEN çevresel değişkeninden "default" oturum açılır
```

**Kullanım amacı:** MCP client'ları her çağrıda token göndermek zorunda değil. Bir kez `set_user_token` ile ayarladıktan sonra tüm sonraki çağrılarda otomatik olarak kullanılır.

### 8.4 Uygulama Filtreleme (_apply_db_intent)

RBAC filtresinden geçen kayıtlara ek filtreler uygular:

```python
# "electronics" bölümündeki kayıtları filtrele
filters = {"bolum": "electronics"}

# "amount > 100" koşulu
filters = {"amount_gt": 100}

# Desteklenen operatörler: eq, gt, gte, lt, lte
```

---

## 9. Web API — FastAPI HTTP Arayüzü

### 9.1 Endpoint'ler

| Endpoint | Method | Auth | Açıklama |
|----------|--------|------|----------|
| `GET /` | GET | Yok | Web UI (HTML sayfası) |
| `GET /api/health` | GET | Yok | Sağlık kontrolü |
| `POST /api/session/token` | POST | Token | Oturum aç |
| `GET /api/session/token` | GET | Yok | Oturum durumu |
| `DELETE /api/session/token` | DELETE | Yok | Oturumu kapat |
| `POST /api/search-knowledge` | POST | Yok | Bilgi tabanında arama |
| `POST /api/ask` | POST | Token* | Soru sor |
| `POST /api/route` | POST | Token* | Yönlendirme önizleme |
| `POST /api/query-intent` | POST | Token* | Yapısal DB sorgusu |
| `GET /api/source/{chunk_id}` | GET | Token* | Kaynak parça getir |
| `POST /api/upload` | POST | Token* | Dosya yükle |
| `POST /api/ingest` | POST | Token* | Metin belgesi ekle |
| `GET /api/documents` | GET | Token* | Belgeleri listele |
| `DELETE /api/documents/{doc_id}` | DELETE | Token* | Belge sil |

**\* Token opsiyonel:** Session token ayarlandıysa explicit token gerekmez.

### 9.2 Token Çözümleme Mantığı

```python
def _resolve_token(explicit_token):
    final = explicit_token or session_manager.get_token()
    if not final:
        raise 401 "No token provided and no session token set"
    return final
```

Öncelik: Explicit token > Session token > Hata (401)

### 9.3 Web UI Özellikleri

- **Tab sistemi:** Soru Sor, Bilgi Arama, Oturum, Doküman Yükle
- **Hızlı token seçimi:** Üstteki token chip'lerine tıklayınca otomatik session açılır
- **Session bilgisi:** Açık oturumun kullanıcı adı, rolü, masked token'ı gösterilir
- **Bilgi arama:** Auth gerektirmez, doğrudan RAG araması yapar
- **Sonuç gösterimi:** Cevap, rota badge'i, meta bilgileri, kaynak kartları, ham JSON

---

## 10. Oturum Yönetimi

### 10.1 Sunucu Tarafı

```python
# Oturum aç
POST /api/session/token  {"token": "admin_token"}
→ {"status": "ok", "user": "Alice Chen", "role": "admin", "masked_token": "admin_to..."}

# Oturum durumu
GET /api/session/token
→ {"status": "ok", "user": "Alice Chen", "role": "admin", "masked_token": "admin_to..."}

# Oturumu kapat
DELETE /api/session/token
→ {"status": "ok", "message": "Token cleared for session 'default'"}
```

### 10.2 Varsayılan Oturum

Docker container'ları `DEFAULT_USER_TOKEN=admin_token` çevresel değişkeni ile başlar. Bu, sunucu başladığında otomatik olarak bir "default" oturum oluşturur.

### 10.3 Sınırlamalar

- **Bellek-içi:** Process yeniden başlatıldığında oturumlar kaybolur
- **Tek process:** Birden fazla container oturum paylaşmaz
- **Süre yok:** Token'lar son kullanma tarihi yoktur
- **Şifresiz:** Token'lar veritabanında düz metin olarak saklanır

---

## 11. Metin İşleme ve Normalizasyon

### 11.1 `src/text/normalization.py`

Türkçe metin işleme araçları:

#### normalize_for_matching(text)

Türkçe karakterleri ASCII'ye dönüştürür:
```
ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u
İ→I, Ç→C, Ğ→G, Ö→O, Ş→S, Ü→U
Küçük harf + birleştirme işaretleri temizlenir
```

#### tokenize_for_matching(text)

1. `normalize_for_matching()` uygulanır
2. Alfanumerik tokenlara ayrılır
3. **50+ Türkçe sonek çıkarılır:** -lar, -ler, -ın, -in, -un, -ün, -da, -de, -dan, -den, -e, -a, -i, -ı, -u, -ü, -nın, -nin, -nun, -nün, -ca, -ce, -cı, -ci, -cu, -cü, -lık, -lik, -luk, -lük, -siz, -sız, -suz, -süz, -mış, -miş, -muş, -müş, -dır, -dir, -dur, -dür, -tır, -tir, -tur, -tür, -arak, -erek, -ken, -sa, -se, -malı, -meli, -abil, -ebil...
4. Türkçe durak kelimeleri (ve, veya, ile, için, bu, şu, vb.) kaldırılır

#### augment_for_embedding(text)

Orijinal metne ASCII-folded versiyonunu ekler:
```
"Ders Bırakma" → "Ders Bırakma ders birakma"
```
Bu, çok dilli embedding modellerinde Türkçe karakter tutarsızlığını azaltır.

#### looks_turkish(text)

Türkçe karakter veya Türkçe anahtar kelimeler algılayarak dil tespiti yapar.

---

## 12. Veri Akışı — Uçtan Uca Senaryolar

### Senaryo 1: RAG Sorusu

```
Kullanıcı: "Yurt başvuruları ne zaman açılır?"

1. [Web UI] POST /api/ask {"question": "Yurt başvuruları ne zaman açılır?"}
2. [FastAPI] _resolve_token() → session token veya explicit token
3. [MCPServer] authenticate(token) → User (Alice Chen, admin)
4. [MCPServer] route("Yurt başvuruları ne zaman açılır?")
5. [Router] "yurt", "başvuru" RAG keyword'leri → ROTA: RAG
6. [MCPServer] rag.search("Yurt başvuruları ne zaman açılır?", user_id=1)
7. [RAGPipeline]
   a. encode_query() → 384-boyutlu vektör
   b. pgvector ile en yakın 12 aday (top_k*4)
   c. Sözlüksel arama: "yurt", "başvuru", "aç" token'ları
   d. Sonuçları birleştir → ilk 3 sonuç
8. [MCPServer] context_builder.build_system_prompt(user, question)
9. [MCPServer] context_builder.build_user_message(question, rag_results)
10. [MCPServer] llm.generate(system_prompt, user_message)
11. [Ollama] POST /api/chat → "Yurt başvuruları 1 Şubat'ta açılır [1]."
12. [MCPServer] _normalize_rag_citations() → [Yurt ve Konaklama] → [1]
13. [FastAPI] JSON yanıt döner
14. [Web UI] Cevap, kaynak kartları ve rota badge'i gösterilir
```

### Senaryo 2: MCP Sorusu

```
Kullanıcı: "Electronics bölümündeki öğrencilerin not ortalamalarını göster"

1. [MCPServer] authenticate(token) → User (Bob Martinez, manager, electronics)
2. [Router] "öğrenci", "not", "ortalama" → ROTA: MCP, tablo: ogrenci_bilgi_sistemi
3. [RBACEngine] query(user, "ogrenci_bilgi_sistemi")
4. [DatabaseManager] scope=DEPARTMENT → WHERE bolum = 'electronics'
5. SQL: SELECT * FROM ogrenci_bilgi_sistemi WHERE bolum = 'electronics'
6. Sonuç: 3 kayıt (Mert, Selin, Deniz)
7. [ContextBuilder] Tablo verisini kullanıcı mesajına ekler
8. [LLM] "Öğrenci not ortalamaları: Mert 3.42, Selin 3.78, Deniz 3.05"
```

### Senaryo 3: HYBRID Sorusu

```
Kullanıcı: "Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?"

1. [Router] "yönerge" (RAG) + "kaç öğrenci" (MCP eylem) → ROTA: HYBRID
2. RAG dalı:
   - search("W notu ne zaman verilir ders bırakma") → "Ders Bırakma ve Eğitime Ara Verme" belgesi
3. MCP dalı:
   - query(user, "ogrenci_bilgi_sistemi") → RBAC filtreli kayıtlar
   - _apply_db_intent(filters={"bolum": "electronics"}) → 3 kayıt
4. [ContextBuilder] Hem RAG sonuçları hem DB sonuçları prompt'a eklenir
5. [LLM] İki bilgiyi birleştirerek kapsamlı yanıt üretir:
   "W notu 3-10. hafta arasında dekan onayı ile verilir [1]. Electronics bölümünde 3 öğrenci bulunmaktadır."
```

### Senaryo 4: Session ile Token'sız İşlem

```
1. Kullanıcı "admin_token" chip'ine tıklar
2. [Web UI] POST /api/session/token {"token": "admin_token"}
3. [MCPServer] set_user_token() → Session'da saklanır
4. Kullanıcı soru sorar (token alanı boş)
5. [FastAPI] _resolve_token(null) → session_manager.get_token() → "admin_token"
6. Normal akış devam eder

Oturumu kapatmak:
7. [Web UI] DELETE /api/session/token
8. [MCPServer] clear_token() → Session temizlenir
9. Artık token'sız istekler 401 döner
```

---

## 13. Yapılandırma

Tüm ayarlar çevresel değişkenler üzerinden yapılır (`src/config.py`):

### Veritabanı

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `DB_HOST` | localhost | PostgreSQL sunucusu |
| `DB_PORT` | 5432 | Port |
| `DB_NAME` | rbac_rag_db | Veritabanı adı |
| `DB_USER` | postgres | Kullanıcı |
| `DB_PASSWORD` | (boş) | Şifre |

### LLM

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `USE_CLAUDE_API` | true | Claude API kullanılsın mı? |
| `CLAUDE_MODEL` | claude-sonnet-4-20250514 | Claude model adı |
| `LOCAL_MODEL_NAME` | Qwen/Qwen2.5-1.5B-Instruct | Yerel model adı (":" varsa Ollama) |
| `OLLAMA_HOST` | http://localhost:11434 | Ollama sunucusu |
| `LLM_MAX_TOKENS` | 512 | Maksimum yanıt token |
| `USE_LLM_ROUTER` | true | LLM router kullanılsın mı? |
| `LLM_ROUTER_MAX_TOKENS` | 700 | Router için maksimum token |

### RAG

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `EMBEDDING_MODEL` | paraphrase-multilingual-MiniLM-L12-v2 | Embedding modeli |
| `EMBEDDING_DIM` | 384 | Vektör boyutu |
| `CHUNK_SIZE` | 200 | Parça boyutu (kelime) |
| `CHUNK_OVERLAP` | 50 | Parça örtüşmesi |
| `RAG_TOP_K` | 3 | Döndürülecek sonuç sayısı |
| `SIMILARITY_THRESHOLD` | 0.3 | Minimum benzerlik eşiği |

### MCP

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `MCP_HOST` | localhost | MCP sunucu adresi |
| `MCP_PORT` | 8000 | MCP sunucu portu |
| `MCP_TRANSPORT` | stdio | Transport modu (stdio / streamable-http) |
| `DEFAULT_USER_TOKEN` | (boş) | Başlangıç oturum token'ı |

---

## 14. Docker Dağıtımı

### Servisler

```yaml
postgres:  # ankane/pgvector:v0.5.1 — PostgreSQL + pgvector eklentisi
ingest:    # Bir kez çalışır — belgeleri parçalayıp embedding'leri kaydeder
web:       # Uvicorn ile FastAPI — :8080
mcp:       # FastMCP sunucusu — :8000
```

### Başlatma Sırası

```
1. postgres başlar → healthcheck (pg_isready)
2. ingest çalışır → schema.sql + seed.sql + belge embedding'leri
3. web başlar → embedding modelini yükler → Uvicorn :8080
4. mcp başlar → FastMCP :8000
```

### Ağ Yapılandırması

- `network_mode: host` — web ve mcp container'ları host ağında çalışır
- Ollama'ya erişim: `localhost:11434` (host ağında)
- PostgreSQL: `5432` portu publish edilir

### Volume'lar

- `pg_data` — PostgreSQL veri kalıcılığı (container yeniden başlatılsa bile veri korunur)

---

## Dosya Yapısı Referansı

```
src/
├── config.py                    # Çevresel değişken yapılandırması
├── db/
│   ├── schema.sql               # Veritabanı şeması
│   ├── seed.sql                 # Başlangıç verileri
│   └── manager.py               # Tüm DB işlemleri
├── llm/
│   ├── base.py                  # Soyut LLM arayüzü
│   ├── factory.py               # Sağlayıcı fabrikası
│   ├── claude_provider.py       # Anthropic Claude API
│   ├── ollama_provider.py       # Ollama HTTP sağlayıcı
│   └── local_provider.py        # HuggingFace transformers
├── mcp/
│   └── server.py                # MCP sunucusu + SessionManager
├── models/
│   ├── enums.py                 # Role, RouteType, AccessScope
│   ├── exceptions.py            # RBACError hiyerarşisi
│   ├── results.py               # SearchResult, QueryResult, DBIntent...
│   └── user.py                  # User, Permission
├── rag/
│   ├── chunker.py               # LangChain TextSplitter
│   ├── pipeline.py              # Hibrit arama (vektör + sözlüksel)
│   └── vector_store.py          # Embedding üretici
├── rbac/
│   ├── auth.py                  # Token doğrulama
│   └── engine.py                # RBAC orkestrasyonu
├── router/
│   ├── classifier.py            # Deterministic keyword router
│   ├── context_builder.py       # LLM prompt oluşturucu
│   └── llm_router.py            # LLM bazlı yapısal router
├── text/
│   └── normalization.py         # Türkçe metin araçları
└── web/
    └── app.py                   # FastAPI + Web UI
```
