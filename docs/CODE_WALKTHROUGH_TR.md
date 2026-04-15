# uniAI RBAC + RAG + MCP Projesi Kod Anlatım Rehberi

Bu doküman, projeyi baştan sona insanlara anlatırken kullanabileceğin detaylı teknik konuşma akışıdır. Amaç slayt tasarımı yapmak değil; kod üzerinden sistemin nasıl çalıştığını, hangi dosyanın ne işe yaradığını ve canlı demoda hangi sırayla ilerlenmesi gerektiğini netleştirmektir.

## 1. Kısa Açılış: Bu Proje Ne Yapıyor?

Projeyi şu cümleyle açabilirsin:

> Bu proje, üniversite öğrenci bilgi sistemi için rol bazlı veri erişimi olan, Türkçe destekli bir RAG asistanıdır. Kullanıcı soru sorar, sistem kullanıcının tokenına göre yetkisini belirler, soruyu RAG / MCP / Hybrid olarak route eder, gerekli doküman veya veritabanı bilgisini toplar ve LLM’e kontrollü bir context vererek cevap üretir.

Ana fikir:

- Kullanıcı doğal dille soru sorar.
- Sistem token üzerinden kullanıcıyı tanır.
- Soru üç rotadan birine gider:
  - `RAG`: Doküman / yönerge / politika bilgisi gerekir.
  - `MCP`: Veritabanı / öğrenci kaydı / listeleme / sayma gerekir.
  - `HYBRID`: Hem doküman hem veritabanı gerekir.
- RAG tarafında bilgi bankası dokümanlarından ilgili chunk bulunur.
- MCP/RBAC tarafında kullanıcı yetkisine göre kayıtlar filtrelenir.
- LLM yalnızca verilen context üzerinden cevap üretir.
- Cevapta kaynaklar `[1]`, `[2]` gibi numaralı atıflarla gösterilir.

Kısa örnek:

```text
Soru:
Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?

Beklenen rota:
HYBRID

RAG kısmı:
Ders bırakma yönergesine göre W notu ne zaman verilir?

MCP kısmı:
electronics bölümünde kaç öğrenci var?
```

## 2. Klasör Yapısı: Nerede Ne Var?

Kod anlatımına başlamadan önce repo yapısını göster:

```text
rbac-rag-mcp/
  src/
    config.py
    db/
    llm/
    mcp/
    models/
    rag/
    rbac/
    router/
    text/
    web/
  scripts/
  tests/
  deploy/
```

Dosya sorumlulukları:

| Klasör / Dosya | Görev |
|---|---|
| `src/config.py` | Ortam değişkenlerini ve uygulama ayarlarını okur. |
| `src/db/schema.sql` | PostgreSQL tablo şemasını kurar. |
| `src/db/seed.sql` | Roller, kullanıcılar, örnek öğrenci kayıtları ve bilgi bankası dokümanlarını ekler. |
| `src/db/manager.py` | Veritabanı işlemlerinin ana sınıfıdır. |
| `src/rbac/` | Authentication ve authorization mantığı. |
| `src/rag/` | Chunking, embedding, vector search, lexical fallback ve reranking. |
| `src/text/normalization.py` | Türkçe karakter, ek ve stopword normalizasyonu. |
| `src/router/classifier.py` | Sorunun RAG / MCP / HYBRID olup olmadığına karar verir. |
| `src/router/context_builder.py` | LLM’e verilecek system prompt ve user context’i oluşturur. |
| `src/llm/` | Claude, Ollama veya local model provider katmanı. |
| `src/mcp/server.py` | Tüm parçaları birleştiren ana orchestration katmanı. |
| `src/web/app.py` | FastAPI endpointleri ve basit web UI. |
| `tests/` | Unit testler ve integration testler. |
| `deploy/docker-compose.yml` | Postgres, ingest ve web servislerini Docker ile çalıştırır. |

## 3. En İyi Anlatım Stratejisi

Bu projeyi anlatırken kod dosyalarını tek tek rastgele gezmek yerine akışı kullanıcı isteğinden başlat:

1. Kullanıcı web UI’da soru sorar.
2. FastAPI `/api/ask` endpointi isteği alır.
3. `MCPServer.ask_question()` çağrılır.
4. Token authenticate edilir.
5. Router soru tipini belirler.
6. Gerekirse RAG çalışır.
7. Gerekirse RBAC filtreli DB sorgusu çalışır.
8. ContextBuilder LLM promptunu kurar.
9. LLM cevap üretir.
10. API cevabı route, kaynaklar, citationlar ve DB sonucu ile döner.
11. Web UI cevabı ve kaynak kartlarını gösterir.

Bu akışı bir cümleyle özetle:

> Projenin merkezi `MCPServer.ask_question()` fonksiyonudur; bütün sistem bu fonksiyonun etrafında okunabilir.

## 4. Config Katmanı

Başlangıç dosyası:

```text
src/config.py
```

Bu dosya `.env` veya environment variable üzerinden ayarları okur.

Önemli ayarlar:

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD

USE_CLAUDE_API
CLAUDE_MODEL
LOCAL_MODEL_NAME
OLLAMA_HOST
LLM_MAX_TOKENS

EMBEDDING_MODEL
CHUNK_SIZE
CHUNK_OVERLAP
RAG_TOP_K
SIMILARITY_THRESHOLD

MCP_HOST
MCP_PORT
```

Anlatırken vurgula:

- Sistem davranışı büyük ölçüde environment ayarlarıyla değişebilir.
- `EMBEDDING_MODEL` Türkçe RAG kalitesini etkiler.
- `RAG_TOP_K` kaç kaynak getirileceğini belirler.
- `SIMILARITY_THRESHOLD` fallback routing davranışını etkiler.
- `USE_CLAUDE_API=false` ise local provider veya Ollama kullanılabilir.

Örnek konuşma:

> Config katmanı uygulamanın kontrol paneli gibi çalışıyor. Veritabanı, LLM provider, embedding modeli ve RAG parametreleri burada belirleniyor. Böylece kodu değiştirmeden sistemi farklı deployment ortamlarına taşıyabiliyoruz.

## 5. Veritabanı Katmanı

Ana dosyalar:

```text
src/db/schema.sql
src/db/seed.sql
src/db/manager.py
```

### 5.1 Schema

`schema.sql` veritabanı tablolarını kurar.

Temel tablo grupları:

- Kullanıcı / rol / permission tabloları:
  - `users`
  - `roles`
  - `role_permissions`
- RAG tabloları:
  - `kb_documents`
  - `kb_chunks`
- İş verisi tabloları:
  - `orders`
  - `refunds`
  - `ogrenci_bilgi_sistemi`

RAG için önemli detay:

```sql
embedding VECTOR(384)
```

Bu alan pgvector ile benzerlik araması yapabilmek için kullanılır.

### 5.2 Seed Data

`seed.sql` örnek verileri yükler.

Önemli seed içerikleri:

- Roller:
  - `admin`
  - `manager`
  - `viewer`
- Tokenlar:
  - `admin_token`
  - `manager_token`
  - `viewer_token`
- Bilgi bankası dokümanları:
  - `Ders Kayıt Yönergesi`
  - `Notlandırma Sistemi ve Akademik Durum`
  - `Mezuniyet Gereksinimleri`
  - `Mali Yardım ve Burslar`
  - `Öğrenci Davranış Kuralları`
  - `Yurt ve Konaklama Hizmetleri`
  - `Ders Bırakma ve Eğitime Ara Verme`
  - `Sınav Politikaları ve Final Sınavları`
- Öğrenci kayıtları:
  - `Mert Yilmaz`
  - `Selin Acar`
  - `Ahmet Kaya`
  - `Ece Demir`
  - `Burak Can`
  - `Deniz Karaca`

### 5.3 DatabaseManager

Ana dosya:

```text
src/db/manager.py
```

Önemli fonksiyonlar:

| Fonksiyon | Görev |
|---|---|
| `setup()` | `schema.sql` ve `seed.sql` çalıştırır. |
| `get_user_by_token()` | Token ile kullanıcıyı ve permissionlarını bulur. |
| `query_records()` | RBAC filtreli tablo sorgusu yapar. |
| `_build_filters()` | Role göre SQL `WHERE` filtresi üretir. |
| `get_all_documents()` | RAG ingest için tüm dokümanları getirir. |
| `store_chunk()` | Chunk embeddingini `kb_chunks` tablosuna yazar. |
| `search_similar_chunks()` | pgvector ile similarity search yapar. |
| `get_searchable_chunks()` | Lexical reranking için tüm erişilebilir chunkları getirir. |
| `create_document()` | Yeni kullanıcı dokümanı oluşturur. |
| `delete_document()` | Kullanıcının kendi dokümanını siler. |

Özellikle `_build_filters()` fonksiyonunu anlat:

```text
admin   → filtre yok
manager → department / bolum filtresi
viewer  → assigned_to / processed_by / advisor_id filtresi
```

Öğrenci tablosu için:

```text
admin   → SELECT * FROM ogrenci_bilgi_sistemi
manager → WHERE bolum = user.department
viewer  → WHERE advisor_id = user.id
```

Bu önemli cümleyi kullan:

> RBAC güvenliği LLM’e bırakılmıyor; SQL sorgusu seviyesinde uygulanıyor.

## 6. RBAC Katmanı

Ana dosyalar:

```text
src/rbac/auth.py
src/rbac/engine.py
src/models/user.py
src/models/enums.py
```

### 6.1 Authentication

`Authenticator` tokenı alır ve `DatabaseManager.get_user_by_token()` ile kullanıcıyı bulur.

Örnek:

```text
viewer_token → Charlie Kim
manager_token → Bob Martinez
admin_token → Alice Chen
```

### 6.2 Authorization

`RBACEngine` kullanıcının ilgili tabloya erişim izni olup olmadığını kontrol eder.

Role göre erişim:

| Rol | Scope | Açıklama |
|---|---|---|
| `admin` | `all` | Tüm kayıtları görür. |
| `manager` | `department` | Kendi departmanını görür. |
| `viewer` | `own` | Sadece kendisine ait kayıtları görür. |

Örnek:

```text
Soru:
Electronics bölümündeki öğrencileri göster

admin_token:
Tüm electronics öğrencilerini görür.

manager_token:
Bob Martinez electronics manager olduğu için electronics öğrencilerini görür.

viewer_token:
Charlie Kim sadece advisor_id = 3 olan kayıtları görür.
```

Sunumda bunu canlı göstermek güçlü olur.

## 7. RAG Pipeline

Ana dosyalar:

```text
src/rag/chunker.py
src/rag/vector_store.py
src/rag/pipeline.py
```

### 7.1 Chunking

Dosya:

```text
src/rag/chunker.py
```

`TextChunker`, dokümanı parçalara böler.

Önemli ayarlar:

- `chunk_size`
- `chunk_overlap`
- separators:
  - paragraf
  - satır
  - cümle
  - boşluk

Anlat:

> RAG sistemlerinde uzun doküman doğrudan embed edilmez. Önce chunklara bölünür, sonra her chunk ayrı embedding olarak saklanır.

### 7.2 Embedding

Dosya:

```text
src/rag/vector_store.py
```

`VectorStore` embedding üretir.

Önemli nokta:

- Hem doküman hem query için `augment_for_embedding()` kullanılır.
- Bu fonksiyon Türkçe metnin normalize edilmiş varyantını da ekler.

Örnek:

```text
Öğrenci danışmanı

Eklenen normalize varyant:
ogrenci danismani
```

Bu sayede:

- `öğrenci`
- `ogrenci`
- `ÖĞRENCİ`

gibi yazım farkları retrieval kalitesini daha az bozar.

### 7.3 Retrieval

Dosya:

```text
src/rag/pipeline.py
```

`RAGPipeline.search()` şu işleri yapar:

1. Query embedding üretir.
2. pgvector ile benzer chunk adaylarını getirir.
3. Lexical search ile Türkçe token eşleşmelerini hesaplar.
4. Vector score ve lexical score’u birleştirir.
5. Başlık, token ve n-gram eşleşmesine göre rerank yapar.
6. En iyi `top_k` sonucu döndürür.

Önemli iyileştirme:

```text
Ders bırakma yönergesine göre W notu ne zaman verilir?
```

Bu soru eskiden yanlışlıkla `Ders Kayıt Yönergesi` gibi daha genel dokümana kayabiliyordu. Reranking sonrası daha spesifik kaynak öne çıkar:

```text
Ders Bırakma ve Eğitime Ara Verme
```

## 8. Türkçe Normalizasyon

Ana dosya:

```text
src/text/normalization.py
```

Bu dosya Türkçe RAG kalitesini artırmak için kritik.

Yaptığı işler:

- Türkçe karakter katlama:

```text
ö → o
ğ → g
ş → s
ç → c
ü → u
ı → i
```

- Büyük/küçük harf normalizasyonu.
- Stopword temizliği.
- Yaygın Türkçe ek indirgeme.
- Query ve document tokenlarını karşılaştırılabilir hale getirme.

Örnek:

```text
yönergesine → yonerge
bölümünde → bolum
öğrencileri → ogrenc
```

Burada vurgula:

> Türkçe RAG için sadece multilingual embedding yeterli olmadı. Ek olarak Türkçe normalization ve reranking gerekli oldu.

## 9. Query Router

Ana dosya:

```text
src/router/classifier.py
```

Bu katman kullanıcının sorusunun hangi akışa gideceğine karar verir.

Route türleri:

```text
RAG
MCP
HYBRID
```

### 9.1 RAG Soruları

Örnek:

```text
Yurt başvuruları ne zaman açılır?
```

Bu soru doküman bilgisi istediği için RAG’e gider.

### 9.2 MCP Soruları

Örnek:

```text
Electronics bölümündeki öğrencileri göster
```

Bu soru veritabanı kaydı istediği için MCP’ye gider.

### 9.3 Hybrid Sorular

Örnek:

```text
Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?
```

Bu soru iki parça içerir:

- Belge sorusu:

```text
Ders bırakma yönergesine göre W notu ne zaman verilir?
```

- DB sorusu:

```text
electronics bölümünde kaç öğrenci var?
```

`_extract_rag_query()` burada devreye girer. Hybrid soruda RAG için gereksiz DB kısmını ayırır.

Anlatım cümlesi:

> Router sadece route seçmiyor, hybrid sorularda RAG tarafına gönderilecek alt sorguyu da temizliyor.

## 10. ContextBuilder ve Prompt Tasarımı

Ana dosya:

```text
src/router/context_builder.py
```

Bu sınıf LLM’e gidecek promptu hazırlar.

İki ana fonksiyon:

```text
build_system_prompt()
build_user_message()
```

### 10.1 System Prompt

System prompt şunları içerir:

- Asistan rolü.
- Kullanıcının adı, rolü, departmanı.
- Cevap dili.
- Sadece verilen context’e göre cevap verme kuralı.
- Kaynak gösterme kuralı.

Önemli kural:

```text
When you use knowledge-base content, cite it with numbered references in square brackets.
```

### 10.2 User Message

User message içinde:

- Kullanıcı sorusu.
- RAG kaynakları.
- DB sonucu.
- RBAC filtresi.
- Kayıt sayısı.
- Records listesi.

RAG kaynakları şu formatta verilir:

```text
[1] Ders Kayıt Yönergesi (similarity: 0.99)
...

[2] Ders Bırakma ve Eğitime Ara Verme (similarity: 0.67)
...
```

Böylece LLM cevapta `[1]`, `[2]` diye atıf verebilir.

## 11. LLM Provider Katmanı

Ana dosyalar:

```text
src/llm/base.py
src/llm/factory.py
src/llm/ollama_provider.py
src/llm/claude_provider.py
src/llm/local_provider.py
```

### 11.1 Base Interface

`LLMProvider` ortak interface sağlar:

```text
generate(system_prompt, user_message, max_tokens)
```

Bu sayede sistem modelden bağımsız kalır.

### 11.2 Factory

`LLMProviderFactory` config’e göre provider seçer:

- Claude API
- Ollama
- Local Transformers

Anlat:

> Model değişse bile RAG, RBAC ve Router katmanları değişmez. Sadece provider değişir.

### 11.3 Ollama Provider

Ollama local LLM için kullanılır.

Önemli ayarlar:

- `model`
- `messages`
- `num_predict`
- `temperature`

## 12. MCPServer: Sistemin Kalbi

Ana dosya:

```text
src/mcp/server.py
```

Bu dosyayı anlatımın merkezine koy.

En önemli fonksiyon:

```text
ask_question()
```

Akış:

1. Token authenticate edilir.
2. Router soru için karar verir.
3. Route RAG veya HYBRID ise RAG search yapılır.
4. Route MCP veya HYBRID ise RBAC query yapılır.
5. ContextBuilder prompt oluşturur.
6. LLM cevap üretir.
7. Cevaptaki kaynak başlıkları `[1]`, `[2]` formatına normalize edilir.
8. `AssistantResponse` oluşturulur.
9. Response JSON olarak döner.

Pseudocode:

```python
user = authenticate(token)
decision = router.route(question)

if decision.route in (RAG, HYBRID):
    rag_results = rag.search(...)

if decision.route in (MCP, HYBRID):
    db_result = rbac.query(...)

system_prompt = ctx.build_system_prompt(user, question)
user_message = ctx.build_user_message(...)

answer = llm.generate(system_prompt, user_message)
answer = normalize_rag_citations(answer, rag_results)

return response_to_dict(...)
```

Bu dosyada ayrıca API response serialization yapılır.

Response içinde:

```json
{
  "answer": "... [1]",
  "route": "rag",
  "user": "Alice Chen",
  "role": "admin",
  "rag_sources": ["Ders Kayıt Yönergesi"],
  "rag_citations": [
    {
      "index": 1,
      "title": "Ders Kayıt Yönergesi",
      "similarity": 0.99,
      "snippet": "..."
    }
  ]
}
```

## 13. IEEE Benzeri Atıf Sistemi

Atıf sistemi şu şekilde çalışır:

### 13.1 Prompt Tarafı

ContextBuilder RAG kaynaklarını numaralı verir:

```text
[1] Ders Kayıt Yönergesi
[2] Ders Bırakma ve Eğitime Ara Verme
```

LLM’den cevapta bu numaraları kullanması istenir.

### 13.2 Server Tarafı

`MCPServer._normalize_rag_citations()` LLM bazen başlıkla atıf verirse onu numaraya çevirir.

Örnek:

```text
[Ders Kayıt Yönergesi] → [1]
```

### 13.3 API Tarafı

`rag_citations` alanı döner:

```json
[
  {
    "index": 1,
    "title": "Ders Kayıt Yönergesi",
    "similarity": 0.99,
    "snippet": "Onur öğrencileri ve son sınıf öğrencileri için erken kayıt imkanı bulunmaktadır..."
  }
]
```

### 13.4 UI Tarafı

Web UI:

- Cevap içindeki `[1]` değerini linke çevirir.
- Link tıklanınca `#citation-1` id’li kaynak kartına scroll yapar.
- Kart highlight olur.

Bu özellik demo sırasında çok iyi görünür:

1. RAG sorusu sor.
2. Cevaptaki `[1]` linkine tıkla.
3. Altta kaynak kartının açıldığını göster.
4. Snippet üzerinden cevabın nereden geldiğini doğrula.

## 14. Web UI

Ana dosya:

```text
src/web/app.py
```

FastAPI endpointleri:

| Endpoint | Görev |
|---|---|
| `/` | HTML UI döner. |
| `/api/health` | Sağlık kontrolü. |
| `/api/ask` | Soru-cevap endpointi. |
| `/api/upload` | Dosya upload + ingest. |
| `/api/ingest` | Text body üzerinden doküman ekleme. |
| `/api/documents` | Kullanıcının dokümanlarını listeleme. |
| `/api/documents/{doc_id}` | Kullanıcının dokümanını silme. |

UI bileşenleri:

- Token input.
- Soru textarea.
- Örnek soru butonları.
- Doküman yükleme paneli.
- Sonuç paneli.
- Route badge.
- Metadata chipleri.
- Kaynak kartları.
- Ham JSON çıktısı.

Önemli JavaScript fonksiyonları:

| Fonksiyon | Görev |
|---|---|
| `renderResult()` | API response’u UI’a basar. |
| `renderAnswer()` | Cevap içindeki `[1]` atıflarını tıklanabilir yapar. |
| `renderSources()` | `rag_citations` listesinden kaynak kartları üretir. |
| `renderMeta()` | Kullanıcı, rol, tablo ve kayıt sayısı gibi bilgileri gösterir. |
| `renderError()` | Hata mesajlarını gösterir. |

## 15. Testler

Klasör:

```text
tests/
```

Önemli test dosyaları:

| Test | Görev |
|---|---|
| `test_router.py` | RAG / MCP / HYBRID routing kararlarını test eder. |
| `test_rag.py` | Chunking ve reranking davranışını test eder. |
| `test_text_normalization.py` | Türkçe normalization davranışını test eder. |
| `test_server.py` | Response serialization ve citation output test eder. |
| `test_rbac.py` | RBAC permission davranışlarını test eder. |
| `test_auth.py` | Authentication davranışını test eder. |
| `test_integration.py` | Gerçek DB isteyen integration testler. |

Komut:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest
```

Beklenen örnek sonuç:

```text
32 passed, 16 skipped
```

Integration testlerin skip olması normaldir; DB environment gerektirir.

## 16. Canlı Demo Akışı

Demo için en iyi sıralama:

### Demo 1: Sadece RAG

Token:

```text
admin_token
```

Soru:

```text
Ders kayıt yönergesine göre erken kayıt kimler için var?
```

Beklenen:

- Route: `rag`
- Cevapta `[1]`
- Kaynak: `Ders Kayıt Yönergesi`
- Snippet içinde erken kayıt cümlesi.

### Demo 2: Sadece MCP

Token:

```text
manager_token
```

Soru:

```text
Electronics bölümündeki öğrencileri göster
```

Beklenen:

- Route: `mcp`
- User: `Bob Martinez`
- Role: `manager`
- Filter: `bolum = 'electronics'`
- Count: `3`

### Demo 3: RBAC Karşılaştırması

Aynı soru:

```text
Electronics bölümündeki öğrencileri göster
```

Üç tokenla sor:

| Token | Beklenen |
|---|---|
| `admin_token` | Tüm electronics öğrencileri. |
| `manager_token` | Electronics manager olduğu için electronics öğrencileri. |
| `viewer_token` | Sadece advisor_id kendi user id’si olan kayıtlar. |

Bu demo RBAC mantığını en iyi gösterir.

### Demo 4: Hybrid

Soru:

```text
Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?
```

Beklenen:

- Route: `hybrid`
- RAG kaynağı: `Ders Bırakma ve Eğitime Ara Verme`
- DB sonucu: electronics öğrenci sayısı `3`
- Cevap: `3-10. hafta arası, dekan onayı ile W notu`
- Cevapta `[1]`
- Altta kaynak kartı.

### Demo 5: Doküman Upload

Yeni bir `.txt` dokümanı yükle.

Örnek içerik:

```text
Öğrenci kulüp başvuruları her dönem ilk üç hafta içinde Öğrenci İşleri üzerinden yapılır.
```

Sonra sor:

```text
Öğrenci kulüp başvuruları ne zaman yapılır?
```

Beklenen:

- Yeni doküman RAG kaynağı olarak döner.
- Citation kartı yeni dokümanı gösterir.

## 17. Sunumda Özellikle Vurgulanacak Teknik Kararlar

### 17.1 RBAC LLM’e Bırakılmadı

Yanlış yaklaşım:

```text
LLM’e "bu kullanıcı viewer, ona göre cevap ver" demek.
```

Doğru yaklaşım:

```text
SQL sorgusunu role göre filtrelemek.
```

Bu projede doğru yaklaşım kullanılıyor.

### 17.2 Türkçe RAG İçin Ek Normalizasyon Gerekli

Sadece embedding kullanmak yetmedi.

Eklenenler:

- Türkçe karakter normalizasyonu.
- Ek indirgeme.
- Stopword temizliği.
- Lexical fallback.
- Başlık/n-gram reranking.

### 17.3 Hybrid Sorular Parçalanmalı

Şu soru tek embedding query olarak giderse RAG kalitesi düşebilir:

```text
Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?
```

Bu yüzden router RAG kısmını ayırır:

```text
Ders bırakma yönergesine göre W notu ne zaman verilir
```

### 17.4 Citation Şeffaflık Sağlar

LLM cevabının doğruluğu tek başına yeterli değildir.

Kullanıcı şunu görmelidir:

- Bilgi hangi dokümandan geldi?
- Dokümanın hangi parçası kullanıldı?
- Similarity skoru ne?

Bu yüzden `rag_citations` eklendi.

## 18. Sık Gelebilecek Sorulara Hazır Cevaplar

### Soru: Neden MCP dediniz?

Cevap:

> Bu projede MCPServer, RAG, RBAC, DB sorgusu ve LLM provider parçalarını tek bir servis arayüzü altında orkestre eden katman olarak kullanılıyor. Yani dışarıdan doğal dil sorusu geliyor, içeride gerekli tool benzeri işlemler çağrılıyor ve cevap birleştiriliyor.

### Soru: RAG neden gerekli?

Cevap:

> Yönetmelik, yönerge ve politika gibi değişebilen metinleri modelin hafızasına gömmek yerine veritabanındaki bilgi bankasından çekiyoruz. Böylece kaynak güncellenirse sistem güncel bilgiyle cevap verir.

### Soru: RBAC neden gerekli?

Cevap:

> Öğrenci kayıtları hassas veri. Her kullanıcı tüm kayıtları görememeli. Admin tümünü, manager kendi bölümünü, viewer yalnız kendi kayıtlarını görmeli.

### Soru: LLM yanlış cevap verirse?

Cevap:

> Bu yüzden cevaba kaynak atıfı ve snippet ekledik. Ayrıca RBAC filtresi ve DB sonucu deterministik olarak backend tarafından üretiliyor. LLM sadece verilen context içinden cevap vermeye zorlanıyor.

### Soru: Türkçe neden özel ele alındı?

Cevap:

> Türkçe eklemeli bir dil olduğu için aynı kavram birçok farklı yüzey formuyla gelebiliyor. Örneğin `yönergesine`, `yönerge`, `yonerge` gibi. Normalization bu farkları azaltıyor.

### Soru: Neden Docker build yavaş?

Cevap:

> `sentence-transformers` ve `torch` bağımlılıkları büyük. Varsayılan torch kurulumu CUDA paketlerini de çekebiliyor. Production için CPU-only torch veya dependency pinning ile image küçültülebilir.

## 19. Anlatım İçin Önerilen Zaman Planı

30 dakikalık anlatım:

| Süre | Bölüm |
|---|---|
| 0-3 dk | Problem ve genel mimari |
| 3-7 dk | DB schema, seed, RBAC |
| 7-13 dk | RAG pipeline ve Türkçe normalization |
| 13-17 dk | Router ve hybrid soru mantığı |
| 17-22 dk | MCPServer `ask_question()` akışı |
| 22-25 dk | Atıf sistemi ve UI |
| 25-30 dk | Canlı demo ve testler |

45 dakikalık anlatım:

| Süre | Bölüm |
|---|---|
| 0-5 dk | Problem ve sistem hedefi |
| 5-10 dk | Klasör yapısı ve config |
| 10-17 dk | DB + RBAC |
| 17-25 dk | RAG + Türkçe retrieval |
| 25-31 dk | Router + ContextBuilder |
| 31-36 dk | MCPServer orchestration |
| 36-40 dk | UI + citation sistemi |
| 40-45 dk | Demo + soru-cevap |

## 20. En İyi Kod Okuma Sırası

Kod üstünden anlatırken şu sırayı takip et:

1. `src/web/app.py`
   - Kullanıcı isteği nereden geliyor?
2. `src/mcp/server.py`
   - Ana orchestration nasıl çalışıyor?
3. `src/router/classifier.py`
   - Soru nasıl route ediliyor?
4. `src/rbac/engine.py`
   - Yetki nasıl uygulanıyor?
5. `src/db/manager.py`
   - SQL filtreleri ve vector search nasıl çalışıyor?
6. `src/rag/pipeline.py`
   - RAG search nasıl yapılıyor?
7. `src/text/normalization.py`
   - Türkçe iyileştirme nasıl çalışıyor?
8. `src/router/context_builder.py`
   - LLM context’i nasıl kuruluyor?
9. `src/llm/ollama_provider.py`
   - Model çağrısı nasıl yapılıyor?
10. `tests/`
   - Bunların doğruluğu nasıl test ediliyor?

## 21. Kapanış Cümlesi

Sunumu şu cümleyle kapatabilirsin:

> Bu projede LLM tek başına karar veren bir yapı değil; RBAC, RAG, query routing, kaynak atıfı ve deterministic DB filtreleriyle kontrol edilen bir sistemin cevap üretim katmanıdır. Asıl değer, modelin etrafındaki güvenilir orchestration mimarisidir.


## 22. Fonksiyon Fonksiyon Detaylı Kod Rehberi

Bu bölüm, kodu ekranda açıp insanlara anlatırken kullanman için hazırlanmıştır. Burada amaç sadece “bu dosya ne yapıyor” demek değil; her önemli class ve fonksiyonun sistemdeki rolünü, girdisini, çıktısını ve anlatırken vurgulanacak noktayı açıklamaktır.

Sunumda bu bölümü doğrudan şu mantıkla kullanabilirsin:

1. Dosyayı aç.
2. Önce dosyanın sistemdeki yerini söyle.
3. Sonra class/fonksiyonları sırayla anlat.
4. Her fonksiyon için “girdi → işlem → çıktı” şeklinde konuş.
5. En sonda o modülün tüm akıştaki yerini özetle.

---

## 22.1 `src/config.py` — Uygulama Ayarları

Bu dosya uygulamanın environment/configuration katmanıdır. Kodun farklı ortamlarda çalışmasını sağlar: local development, Docker, farklı LLM provider, farklı database host gibi.

### `_env(key: str, default: str | None = None) -> str`

**Ne yapar?**

- Environment variable okur.
- Eğer değer yoksa default değeri döndürür.
- Eğer default da yoksa hata fırlatır.

**Girdi:**

- `key`: okunacak environment değişkeni adı.
- `default`: yoksa kullanılacak değer.

**Çıktı:**

- String config değeri.

**Neden önemli?**

- Uygulamanın `.env` dosyasından veya Docker environment ayarlarından bağımsız çalışmasını sağlar.
- Zorunlu config eksikse erken hata üretir.

**Anlatırken söyle:**

> Bu küçük helper, config okumayı standartlaştırıyor. Her yerde `os.environ.get` yazmak yerine tek yerden yönetiyoruz.

### `_env_int(key: str, default: int = 0) -> int`

**Ne yapar?**

- Environment variable okur.
- String değeri integer’a çevirir.

**Örnek kullanılan ayarlar:**

- `DB_PORT`
- `LLM_MAX_TOKENS`
- `CHUNK_SIZE`
- `CHUNK_OVERLAP`
- `RAG_TOP_K`
- `MCP_PORT`

**Neden önemli?**

- `.env` değerleri string gelir. Uygulamada bazı değerler sayı olarak kullanılmalıdır.

### `_env_float(key: str, default: float = 0.0) -> float`

**Ne yapar?**

- Float türündeki config değerlerini okur.

**Örnek:**

- `SIMILARITY_THRESHOLD`

**Anlatırken söyle:**

> RAG fallback kararlarında similarity threshold numeric olarak kullanıldığı için string kalmaması gerekiyor.

### `_env_bool(key: str, default: bool = False) -> bool`

**Ne yapar?**

- Boolean config değerlerini okur.
- `true`, `1`, `yes` değerlerini `True` kabul eder.

**Örnek:**

- `USE_CLAUDE_API`

**Neden önemli?**

- LLM provider seçimi bu değerle değişir.

### `AppConfig`

**Ne yapar?**

- Uygulamanın bütün ayarlarını immutable dataclass olarak tutar.

**Ana gruplar:**

- Database config
- LLM config
- RAG config
- MCP server config

**Önemli alanlar:**

```text
embedding_model
chunk_size
chunk_overlap
rag_top_k
similarity_threshold
use_claude_api
local_model_name
ollama_host
```

**Neden önemli?**

- Sistemin davranışını tek objede toplar.
- `build_server()` gibi factory fonksiyonlarına tek parametreyle tüm config verilebilir.

### `AppConfig.from_env() -> AppConfig`

**Ne yapar?**

- Environment variable değerlerini okuyup `AppConfig` instance’ı üretir.

**Akış:**

1. DB ayarlarını okur.
2. LLM ayarlarını okur.
3. RAG ayarlarını okur.
4. MCP server ayarlarını okur.
5. `AppConfig` döndürür.

**Anlatırken söyle:**

> Uygulama başlarken tüm ayarlar burada normalize edilip tek bir config objesine çevriliyor. Böylece geri kalan kod environment detaylarını bilmek zorunda kalmıyor.

---

## 22.2 `src/models/enums.py` — Sabit Kavramlar

Bu dosya sistemdeki sınırlı değer kümelerini tanımlar. Enum kullanmak magic string kullanımını azaltır.

### `Role(Enum)`

**Değerler:**

```text
ADMIN
MANAGER
VIEWER
```

**Ne temsil eder?**

- Kullanıcının sistemdeki rolünü temsil eder.

**Nerede kullanılır?**

- `User.role`
- RBAC kararları
- Prompt içinde kullanıcı rolünü belirtme

### `RouteType(Enum)`

**Değerler:**

```text
RAG
MCP
HYBRID
```

**Ne temsil eder?**

- Kullanıcı sorusunun hangi execution path’e gideceğini gösterir.

**Örnek:**

```text
Yurt başvuruları ne zaman açılır? → RAG
Electronics bölümündeki öğrencileri göster → MCP
Ders bırakma yönergesi ... ve kaç öğrenci var? → HYBRID
```

### `AccessScope(Enum)`

**Değerler:**

```text
ALL
DEPARTMENT
OWN
```

**Ne temsil eder?**

- Bir kullanıcının tablo verisini hangi kapsamda görebileceğini belirtir.

**RBAC karşılığı:**

| Scope | Anlam |
|---|---|
| `ALL` | Tüm kayıtlar |
| `DEPARTMENT` | Kendi departmanındaki kayıtlar |
| `OWN` | Kendi kayıtları |

---

## 22.3 `src/models/user.py` — User ve Permission Modeli

Bu dosya kullanıcı ve permission objelerini tanımlar.

### `Permission`

**Alanlar:**

```text
resource
action
scope
```

**Ne temsil eder?**

- Bir role ait tekil izin kaydını temsil eder.

**Örnek:**

```text
resource = ogrenci_bilgi_sistemi
action = read
scope = department
```

Bu şu anlama gelir:

> Kullanıcı öğrenci bilgi sistemi tablosunu okuyabilir ama sadece departman scope’unda.

### `User`

**Alanlar:**

```text
id
name
email
role
department
permissions
```

**Ne temsil eder?**

- Authenticated kullanıcıyı temsil eder.
- Kullanıcının rolünü ve permissionlarını taşır.

### `User.has_permission(resource: str, action: str = "read") -> AccessScope | None`

**Ne yapar?**

- Kullanıcının belirli resource/action için izni var mı diye bakar.
- Varsa scope döndürür.
- Yoksa `None` döndürür.

**Girdi:**

```text
resource = "ogrenci_bilgi_sistemi"
action = "read"
```

**Çıktı:**

```text
AccessScope.ALL
AccessScope.DEPARTMENT
AccessScope.OWN
None
```

**Neden önemli?**

- RBAC kararının ilk adımıdır.
- `DatabaseManager.query_records()` bu scope’a göre SQL filtresi kurar.

**Anlatırken söyle:**

> Bu fonksiyon “kullanıcı bu tabloyu hangi kapsamda okuyabilir?” sorusunun cevabını verir.

### `User.is_admin`

**Ne yapar?**

- Kullanıcının admin olup olmadığını boolean olarak döndürür.

**Neden var?**

- Kod içinde admin özel durumları gerekirse okunabilirlik sağlar.

---

## 22.4 `src/models/results.py` — Servisler Arası Veri Taşıma Objeleri

Bu dosya farklı katmanlar arasında taşınan response objelerini tanımlar.

### `SearchResult`

**Alanlar:**

```text
chunk_id
text
document_title
similarity
```

**Ne temsil eder?**

- RAG aramasından dönen tek chunk sonucudur.

**Örnek:**

```text
chunk_id = 12
document_title = Ders Kayıt Yönergesi
similarity = 0.99
text = ilgili chunk metni
```

**Nerede kullanılır?**

- `RAGPipeline.search()` sonucu
- `ContextBuilder.build_user_message()` içinde LLM context’i
- `MCPServer._response_to_dict()` içinde `rag_citations`

### `QueryResult`

**Alanlar:**

```text
records
count
total_amount
access_scope
filter_description
table_name
```

**Ne temsil eder?**

- RBAC filtreli DB sorgusunun sonucudur.

**Örnek:**

```text
table_name = ogrenci_bilgi_sistemi
filter_description = bolum = 'electronics'
count = 3
records = tuple of rows
```

**Neden önemli?**

- DB sonucu sadece raw records değildir; hangi RBAC filtresi uygulandığı da taşınır.

### `RoutingDecision`

**Alanlar:**

```text
route
rag_query
db_table
confidence
```

**Ne temsil eder?**

- Router’ın verdiği kararı temsil eder.

**Örnek HYBRID karar:**

```text
route = HYBRID
rag_query = Ders bırakma yönergesine göre W notu ne zaman verilir
db_table = ogrenci_bilgi_sistemi
confidence = 0.9
```

### `AssistantResponse`

**Alanlar:**

```text
answer
route
user
rag_sources
rag_results
db_result
```

**Ne temsil eder?**

- Son kullanıcıya dönecek asistan cevabının backend içindeki typed halidir.

**Neden `rag_results` eklendi?**

- `rag_sources` sadece başlıkları tutar.
- `rag_results` snippet ve similarity gibi citation detaylarını üretmek için gerekir.

---

## 22.5 `src/models/exceptions.py` — Domain Hataları

Bu dosya custom exception sınıflarını tanımlar.

### `RBACError`

**Ne yapar?**

- Projeye özgü hataların base class’ıdır.

### `AuthenticationError`

**Ne zaman kullanılır?**

- Token geçersizse.
- Kullanıcı bulunamazsa.

**Web karşılığı:**

- FastAPI tarafında `401 Unauthorized` olarak döner.

### `PermissionDeniedError`

**Ne zaman kullanılır?**

- Kullanıcı bir tabloyu okumaya yetkili değilse.
- Kullanıcının silmek istediği doküman kendisine ait değilse.

**Web karşılığı:**

- FastAPI tarafında `403 Forbidden` olarak döner.

### `RoutingError`

**Ne için var?**

- Routing katmanında ileride özel hata durumları için kullanılabilir.

---

## 22.6 `src/db/manager.py` — DatabaseManager Detayları

Bu dosya backend’in veritabanı gateway’idir. SQL yazan ve DB ile konuşan ana katman burasıdır.

### `DatabaseManager.__init__(config: AppConfig)`

**Ne yapar?**

- PostgreSQL bağlantısını açar.
- `psycopg2.connect()` kullanır.
- `autocommit = True` yapar.

**Girdi:**

- `AppConfig`

**Neden önemli?**

- Tüm DB fonksiyonları aynı connection üzerinden çalışır.

### `setup() -> None`

**Ne yapar?**

- `schema.sql` dosyasını çalıştırır.
- `seed.sql` dosyasını çalıştırır.
- DB’yi ilk kullanılabilir hale getirir.

**Anlatırken söyle:**

> Local development veya test ortamında DB’yi sıfırdan kurmak için kullanılır.

### `get_user_by_token(token: str) -> User`

**Ne yapar?**

1. `users` tablosundan token ile kullanıcıyı bulur.
2. `roles` tablosuyla join yaparak role bilgisini alır.
3. `role_permissions` tablosundan permissionları alır.
4. Bunları `User` dataclass objesine çevirir.

**Başarısız durumda:**

- Token bulunamazsa `AuthenticationError` fırlatır.

**Neden önemli?**

- Authentication akışının temelidir.
- RBAC sistemi burada dönen `User.permissions` üstüne kurulur.

### `query_records(user: User, table: str) -> QueryResult`

**Ne yapar?**

- Belirli tabloyu kullanıcının yetkisine göre sorgular.

**Adımlar:**

1. Tablo allowed mı kontrol eder.
2. Kullanıcının permission scope’unu bulur.
3. `_build_filters()` ile SQL `WHERE` clause üretir.
4. Sorguyu çalıştırır.
5. Kayıtları tuple/dict formatında döndürür.
6. Amount alanı varsa toplam hesaplar.
7. `QueryResult` döndürür.

**Örnek:**

```text
manager_token + ogrenci_bilgi_sistemi
→ WHERE bolum = 'electronics'
```

**Anlatırken söyle:**

> LLM’e tüm veriyi verip “sen filtrele” demiyoruz. Veri daha LLM’e gitmeden RBAC filtreli geliyor.

### `_build_filters(user: User, table: str, scope: AccessScope)`

**Ne yapar?**

- Scope’a göre SQL filtre üretir.

**Scope bazlı davranış:**

```text
ALL        → "", []
DEPARTMENT → WHERE department/bolum = user.department
OWN        → WHERE assigned_to/processed_by/advisor_id = user.id
```

**Tabloya göre kolon eşlemesi:**

| Table | Department filter | Own filter |
|---|---|---|
| `orders` | `department` | `assigned_to` |
| `refunds` | `department` | `processed_by` |
| `ogrenci_bilgi_sistemi` | `bolum` | `advisor_id` |

**Neden kritik?**

- RBAC güvenliği bu fonksiyonla SQL seviyesinde uygulanır.

### `get_all_documents() -> list[dict]`

**Ne yapar?**

- `kb_documents` tablosundaki tüm dokümanları getirir.

**Nerede kullanılır?**

- `RAGPipeline.ingest()` içinde.

### `store_chunk(doc_id: int, text: str, index: int, embedding: list[float]) -> None`

**Ne yapar?**

- Bir doküman chunk’ını ve embedding vektörünü `kb_chunks` tablosuna yazar.

**Neden embedding stringe çevriliyor?**

- pgvector insert için vektör `[...]` formatında string olarak SQL’e veriliyor.

### `create_document(title, content, category, user_id) -> int`

**Ne yapar?**

- Kullanıcının yüklediği yeni dokümanı `kb_documents` tablosuna ekler.
- Yeni `document_id` döndürür.

**Nerede kullanılır?**

- Web UI doküman upload.
- `/api/ingest` endpointi.
- `MCPServer.ingest_document()`.

### `search_similar_chunks(query_embedding, top_k, user_id) -> list[dict]`

**Ne yapar?**

- pgvector cosine distance ile en benzer chunkları getirir.

**SQL mantığı:**

```sql
1 - (c.embedding <=> query_vector) AS similarity
ORDER BY c.embedding <=> query_vector
LIMIT top_k
```

**User filter:**

- `user_id` verilirse sadece:
  - global dokümanlar (`user_id IS NULL`)
  - kullanıcının kendi dokümanları
  görünür.

**Neden önemli?**

- RAG retrieval’ın vector search kısmıdır.

### `get_searchable_chunks(user_id) -> list[dict]`

**Ne yapar?**

- Lexical fallback ve reranking için erişilebilir chunkları getirir.

**Neden vector search yetmedi?**

- Türkçe ekler ve yazım farkları yüzünden bazı doğru dokümanlar vector sıralamada geriye düşebilir.
- Lexical reranking bu sorunu azaltır.

### `reset_kb_chunks() -> None`

**Ne yapar?**

- `kb_chunks` tablosunu temizler.

**Nerede kullanılır?**

- Re-ingest sırasında eski embeddingleri silmek için.

### `get_user_documents(user_id) -> list[dict]`

**Ne yapar?**

- Belirli kullanıcının yüklediği dokümanları listeler.

### `delete_document(doc_id, user_id) -> bool`

**Ne yapar?**

- Dokümanı yalnızca sahibi silebilir.
- Silindiyse `True`, bulunamadıysa veya kullanıcıya ait değilse `False` döner.

### `close() -> None`

**Ne yapar?**

- DB connection açıksa kapatır.

---

## 22.7 `src/rbac/auth.py` — Authenticator

### `Authenticator.__init__(db: DatabaseManager)`

**Ne yapar?**

- DB manager dependency’sini saklar.

### `authenticate(token: str) -> User`

**Ne yapar?**

- Tokenı DB’ye sorar.
- Kullanıcıyı döndürür.

**Asıl işi kim yapıyor?**

- `DatabaseManager.get_user_by_token()`.

**Neden ayrı class var?**

- Authentication sorumluluğunu RBAC engine ve DB manager’dan ayırır.

---

## 22.8 `src/rbac/engine.py` — RBACEngine

### `RBACEngine.__init__(db, authenticator)`

**Ne yapar?**

- DB ve Authenticator dependency’lerini saklar.

### `authenticate(token: str) -> User`

**Ne yapar?**

- Authenticator’a delegate eder.

**Neden var?**

- Dış katmanların tek RBAC facade üzerinden çalışmasını sağlar.

### `query(user: User, table: str) -> QueryResult`

**Ne yapar?**

- Kullanıcının role/permission bilgisiyle tablo sorgusu yapar.
- İşin detayını `DatabaseManager.query_records()` yapar.

**Anlatırken söyle:**

> RBACEngine policy kararını temsil eder, SQL detaylarını DB manager’a bırakır.

### `get_permissions_summary(user: User) -> dict`

**Ne yapar?**

- Kullanıcının rol, departman ve permission listesini okunabilir dict olarak döndürür.

**Nerede kullanılır?**

- `list_permissions` tool/endpoint için.

---

## 22.9 `src/text/normalization.py` — Türkçe Metin Normalizasyonu

Bu dosya Türkçe RAG kalitesinin en kritik destek katmanıdır.

### `normalize_for_matching(text: str) -> str`

**Ne yapar?**

- Türkçe karakterleri ASCII eşdeğerine çevirir.
- Casefold yapar.
- Unicode combining mark temizler.
- Fazla whitespace temizler.

**Örnek:**

```text
Öğrenci İşleri ve Sınıf
→ ogrenci isleri ve sinif
```

**Nerede kullanılır?**

- QueryRouter keyword matching.
- RAG lexical search.
- Citation başlık normalize etme.

### `tokenize_for_matching(text: str) -> tuple[str, ...]`

**Ne yapar?**

1. Metni normalize eder.
2. Tokenlara böler.
3. Türkçe ekleri indirger.
4. Stopwordleri çıkarır.

**Örnek:**

```text
yönergesine bölümünde öğrencileri
→ yonerge, bolum, ogrenc
```

**Neden önemli?**

- Türkçe eklemeli olduğu için aynı kelime çok farklı yüzey formlarında gelebilir.

### `augment_for_embedding(text: str) -> str`

**Ne yapar?**

- Orijinal metne normalize edilmiş varyantı ekler.

**Örnek:**

```text
Öğrenci danışmanı

ogrenci danismani
```

**Neden önemli?**

- Embedding modelinin Türkçe/ASCII varyasyonlarını daha iyi yakalamasına yardım eder.

### `looks_turkish(text: str) -> bool`

**Ne yapar?**

- Metnin Türkçe olup olmadığını sezgisel olarak belirler.

**Kontroller:**

- Türkçe karakter var mı?
- Türkçe domain tokenları var mı?
- Tokenlar Türkçe hint listesiyle örtüşüyor mu?

**Nerede kullanılır?**

- ContextBuilder içinde cevap dilini Türkçe seçmek için.

### `_reduce_token(token: str) -> str`

**Ne yapar?**

- Token üstündeki yaygın Türkçe ekleri tekrar tekrar temizler.

**Örnek:**

```text
yönergesine → yonerge
```

### `_strip_one_suffix(token: str) -> str`

**Ne yapar?**

- Tek bir suffix temizleme adımı uygular.
- `_reduce_token()` bunu döngüyle tekrarlar.

---

## 22.10 `src/rag/chunker.py` — TextChunker

### `TextChunker.__init__(chunk_size=200, overlap=50)`

**Ne yapar?**

- LangChain `RecursiveCharacterTextSplitter` kurar.
- Chunk boyutu ve overlap ayarlarını alır.

**Parametreler:**

- `chunk_size`: her chunk yaklaşık kaç kelime olsun.
- `overlap`: ardışık chunklar arasında kaç kelime ortak kalsın.

**Neden overlap var?**

- Cümle veya anlam bölünürse bir sonraki chunkta bağlam kaybolmasın diye.

### `chunk(document_id: int, title: str, text: str) -> list[Document]`

**Ne yapar?**

1. Ham metni LangChain `Document` objesine çevirir.
2. Metadata olarak `document_id` ve `title` ekler.
3. Splitter ile parçalar.
4. Her chunk’a `chunk_index` metadata ekler.
5. Chunk listesi döndürür.

**Çıktı örneği:**

```text
Document(
  page_content="...",
  metadata={
    "document_id": 7,
    "title": "Ders Bırakma ve Eğitime Ara Verme",
    "chunk_index": 0
  }
)
```

---

## 22.11 `src/rag/vector_store.py` — VectorStore

### `VectorStore.__init__(model_name)`

**Ne yapar?**

- HuggingFace embedding modelini yükler.

**Örnek model:**

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

**Neden multilingual model?**

- Türkçe doküman ve Türkçe query için İngilizce odaklı embedding modelinden daha uygundur.

### `encode_document(text: str) -> list[float]`

**Ne yapar?**

- Doküman chunk metnini embedding vektörüne çevirir.
- Önce `augment_for_embedding()` uygular.

**Nerede kullanılır?**

- `RAGPipeline.ingest()`
- `RAGPipeline.ingest_document()`

### `encode_query(text: str) -> list[float]`

**Ne yapar?**

- Kullanıcı sorgusunu embedding vektörüne çevirir.
- Query için de normalize edilmiş varyant kullanır.

**Nerede kullanılır?**

- `RAGPipeline.search()`.

---

## 22.12 `src/rag/pipeline.py` — RAGPipeline Detayları

Bu dosya RAG sisteminin ana motorudur.

### `RAGPipeline.__init__(db, vector_store, chunker, top_k=3)`

**Ne yapar?**

- DB manager, vector store, chunker ve top_k ayarını saklar.

### `ingest(reset: bool = True) -> int`

**Ne yapar?**

1. Eğer `reset=True` ise eski chunkları siler.
2. `kb_documents` tablosundan tüm dokümanları getirir.
3. Her dokümanı chunklara böler.
4. Her chunk için embedding üretir.
5. Chunk + embedding veritabanına yazılır.
6. Toplam chunk sayısını döndürür.

**Ne zaman çalışır?**

- Docker `ingest` servisi çalıştığında.
- Manuel `python scripts/ingest.py` çalıştırıldığında.

### `search(query: str, top_k=None, user_id=None) -> list[SearchResult]`

**Ne yapar?**

- RAG araması yapar.

**Detaylı akış:**

1. `limit = top_k or self._top_k`
2. Query embedding üretir.
3. Vector DB’den candidate listesi getirir.
4. Vector sonuçlarını `SearchResult` objelerine çevirir.
5. Lexical search çalıştırır.
6. Vector + lexical sonuçları merge/rerank eder.
7. En iyi sonuçları döndürür.

**Neden candidate_limit daha yüksek?**

- Sadece `top_k=3` kadar aday getirirsek doğru doküman geride kalabilir.
- Daha geniş aday havuzu reranking için daha iyi sonuç verir.

### `_retrieve_documents(query_embedding, top_k, user_id) -> list[Document]`

**Ne yapar?**

- DB’den vector similarity ile raw chunk sonuçlarını alır.
- Bunları LangChain `Document` objesine çevirir.

**Neden ayrı fonksiyon?**

- DB sorgusu ile RAG result dönüşümü ayrılır.

### `_lexical_search(query, top_k, user_id) -> list[SearchResult]`

**Ne yapar?**

- Query ve chunkları token bazlı karşılaştırır.
- Türkçe normalize edilmiş tokenlar kullanır.
- Başlık eşleşmesine yüksek ağırlık verir.
- Bigram/trigram örtüşmesi hesaplar.
- Lexical similarity skoru üretir.

**Neden önemli?**

- Türkçe ekler ve domain terimleri vector similarity’de bazen yeterince iyi ayrışmayabilir.
- Örneğin `Ders bırakma yönergesi` sorgusunda doğru başlığın öne çıkmasını sağlar.

### `_merge_results(query, vector_results, lexical_results, top_k) -> list[SearchResult]`

**Ne yapar?**

- Vector ve lexical sonuçları chunk id’ye göre birleştirir.
- Her result için combined score üretir.
- Başlık bigramı ve title overlap gibi tie-breakerlar kullanır.
- En iyi `top_k` sonucu döndürür.

**Anlatırken söyle:**

> Bu fonksiyon vector search ile lexical search’ü uzlaştırıyor. RAG kalitesini artıran kritik adımlardan biri bu.

### `_ngram_overlap(query_tokens, haystack_tokens, size) -> float`

**Ne yapar?**

- Query tokenları ile doküman tokenları arasında bigram/trigram örtüşmesi hesaplar.

**Örnek:**

```text
query: ders bırakma yonerge
başlık: ders bırakma eğitime ara verme
```

Burada `ders bırakma` bigramı eşleşir.

### `ingest_document(title, content, category, user_id) -> dict`

**Ne yapar?**

1. Yeni dokümanı `kb_documents` tablosuna ekler.
2. Dokümanı chunklara böler.
3. Chunk embeddingleri üretir.
4. Chunkları DB’ye yazar.
5. `document_id` ve chunk sayısını döndürür.

**Nerede kullanılır?**

- Web UI doküman yükleme.
- `/api/upload`
- `/api/ingest`

---

## 22.13 `src/router/classifier.py` — QueryRouter Detayları

Bu dosya doğal dil sorusunu execution route’a çevirir.

### `QueryRouter.__init__(rag, threshold=0.3)`

**Ne yapar?**

- RAG pipeline dependency’sini saklar.
- Similarity threshold saklar.
- Keyword listelerini normalize eder.

**Neden keywordler normalize ediliyor?**

- Türkçe karakter veya casing farklarından etkilenmemek için.

### `_score(query: str, keywords: list[str]) -> int`

**Ne yapar?**

- Query içinde kaç keyword geçtiğini sayar.

**Örnek:**

```text
query = "Öğrenci not ortalamasını göster"
keywords = ["ogrenci", "not ortalamasi", "goster"]
score = 3
```

### `_detect_table(query: str) -> str`

**Ne yapar?**

- Query’ye göre hangi DB tablosunun sorgulanacağını belirler.

**Örnekler:**

```text
refund / iade → refunds
ogrenci / gpa / danisman / sinif → ogrenci_bilgi_sistemi
order / siparis → orders
```

**Default:**

```text
orders
```

### `_extract_rag_query(query: str) -> str`

**Ne yapar?**

- Hybrid sorularda RAG için gerekli alt sorguyu ayırır.

**Örnek:**

```text
Orijinal:
Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?

RAG query:
Ders bırakma yönergesine göre W notu ne zaman verilir
```

**Neden önemli?**

- DB kısmı RAG search’e giderse doğru doküman sıralaması bozulabilir.

### `route(query: str) -> RoutingDecision`

**Ne yapar?**

- Soru için route kararını verir.

**Karar mantığı:**

1. RAG keyword score hesapla.
2. MCP keyword score hesapla.
3. MCP action score hesapla.
4. RAG + MCP action varsa HYBRID.
5. Sadece MCP ise MCP.
6. Sadece RAG ise RAG.
7. Belirsizse RAG similarity fallback dene.
8. Yine belirsizse güvenli default olarak RAG döndür.

**Neden default RAG?**

- Belirsiz soruda DB’ye yanlış tablo sorgusu atmaktansa doküman aramasına düşmek daha güvenli.

---

## 22.14 `src/router/context_builder.py` — ContextBuilder Detayları

### `build_system_prompt(user, question=None) -> str`

**Ne yapar?**

- LLM’e verilecek sistem talimatını üretir.

**İçerik:**

- Asistan rolü.
- Sadece context’e göre cevap verme talimatı.
- Kullanıcı adı, rolü, departmanı.
- Cevap dili.
- Türkçe terimleri koruma talimatı.
- Numaralı kaynak atıfı talimatı.
- Uydurma bilgi üretmeme talimatı.

**Neden önemli?**

- Modelin davranış sınırlarını belirler.

### `build_user_message(question, rag_results, db_result, user) -> str`

**Ne yapar?**

- LLM’e verilecek user message/context metnini kurar.

**RAG varsa:**

```text
[1] Ders Kayıt Yönergesi (similarity: 0.99)
chunk metni...
```

**DB varsa:**

```text
Table: ogrenci_bilgi_sistemi
Filter applied: bolum = 'electronics'
Record count: 3
Records:
  - {...}
```

**Neden önemli?**

- LLM’in görebileceği tek bilgi buradaki context’tir.
- RBAC filtreli DB sonucu burada modele verilir.

### `_build_db_summary(db_result: QueryResult) -> list[str]`

**Ne yapar?**

- Bazı DB sonuçları için deterministic özet üretir.
- Şu an özellikle `ogrenci_bilgi_sistemi` için sınıf bazında en yüksek GPA bilgisini hesaplar.

**Neden var?**

- LLM’in hesaplama hatası yapmasını azaltmak için.

---

## 22.15 `src/llm/base.py` — LLM Interface

### `LLMProvider.generate(system_prompt, user_message, max_tokens) -> str`

**Ne yapar?**

- Tüm LLM providerlar için ortak generate kontratıdır.

**Neden abstract?**

- Claude, Ollama veya local model aynı interface ile kullanılabilir.

### `LLMProvider.get_model_name() -> str`

**Ne yapar?**

- Kullanılan model adını döndürür.

---

## 22.16 `src/llm/factory.py` — Provider Seçimi

### `LLMProviderFactory.create(config) -> LLMProvider`

**Ne yapar?**

- Config’e göre hangi LLM provider’ın kullanılacağını seçer.

**Karar mantığı:**

```text
USE_CLAUDE_API=true → ClaudeProvider
LOCAL_MODEL_NAME içinde ':' varsa → OllamaProvider
aksi halde → LocalProvider
```

**Neden önemli?**

- Model provider değiştirmek sistemin geri kalanını etkilemez.

---

## 22.17 `src/llm/ollama_provider.py` — OllamaProvider

### `OllamaProvider.__init__(config)`

**Ne yapar?**

- Ollama model adını ve base URL’i config’ten alır.

### `generate(system_prompt, user_message, max_tokens) -> str`

**Ne yapar?**

1. Model lokal Ollama’da var mı kontrol eder.
2. `/api/chat` endpointine request atar.
3. System ve user mesajlarını gönderir.
4. JSON response içinden model cevabını alır.
5. String olarak döndürür.

**Önemli seçenekler:**

```text
num_predict = max_tokens
temperature = 0.1
```

**Neden düşük temperature?**

- Daha stabil, daha az dağınık cevap almak için.

### `get_model_name() -> str`

**Ne yapar?**

- Ollama model adını döndürür.

### `_model_exists() -> bool`

**Ne yapar?**

- Ollama `/api/tags` endpointinden lokal model listesini alır.
- Kullanılacak model listede var mı kontrol eder.

**Neden önemli?**

- Model pull edilmemişse daha anlaşılır hata vermek için.

---

## 22.18 `src/llm/claude_provider.py` — ClaudeProvider

### `ClaudeProvider.__init__(config)`

**Ne yapar?**

- Claude model adını config’ten alır.
- Anthropic client oluşturur.

### `generate(system_prompt, user_message, max_tokens) -> str`

**Ne yapar?**

- Anthropic Messages API’ye istek atar.
- System prompt ve user message gönderir.
- İlk content text’ini döndürür.

### `get_model_name() -> str`

**Ne yapar?**

- Claude model adını döndürür.

---

## 22.19 `src/llm/local_provider.py` — LocalProvider

### `LocalProvider.__init__(config)`

**Ne yapar?**

- Transformers tokenizer ve model yükler.
- Local HuggingFace instruct model çalıştırmak için kullanılır.

### `generate(system_prompt, user_message, max_tokens) -> str`

**Ne yapar?**

1. System ve user mesajlarını chat template’e koyar.
2. Tokenize eder.
3. Model generate çalıştırır.
4. Sadece yeni üretilen tokenları decode eder.
5. Cevabı string döndürür.

**Neden prompt_length kullanılıyor?**

- Model output’u prompt + yeni tokenlardan oluşur.
- Sadece cevabı almak için prompt kısmı kesilir.

### `get_model_name() -> str`

**Ne yapar?**

- Local model adını döndürür.

---

## 22.20 `src/mcp/server.py` — MCPServer Fonksiyonları

Bu dosya projenin merkezi. Kod anlatımında en çok zaman ayrılacak dosya budur.

### `MCPServer.__init__(...)`

**Ne yapar?**

- RBAC, RAG, Router, LLM provider, ContextBuilder ve max token ayarını saklar.

**Dependency injection mantığı:**

- Sınıf kendi içinde DB veya model oluşturmaz.
- Dışarıdan verilen bileşenleri kullanır.

### `search_knowledge(query, top_k=3) -> dict`

**Ne yapar?**

- Auth gerektirmeyen açık RAG araması yapar.
- `RAGPipeline.search()` çağırır.
- Chunk id, text, title ve similarity döndürür.

**Nerede kullanılır?**

- MCP tool olarak bilgi bankasında arama yapmak için.

### `query_records(token, table) -> dict`

**Ne yapar?**

1. Token authenticate eder.
2. RBAC query çalıştırır.
3. QueryResult’ı dict’e çevirir.

**Neden önemli?**

- Direkt DB sorgusu ama RBAC filtreli.

### `ask_question(token, question) -> dict`

**Ne yapar?**

Bu sistemin ana fonksiyonudur.

Adımlar:

1. `self._rbac.authenticate(token)` ile kullanıcıyı bulur.
2. `self._router.route(question)` ile route kararı alır.
3. Route RAG/HYBRID ise RAG araması yapar.
4. Route MCP/HYBRID ise RBAC filtreli DB sorgusu yapar.
5. System prompt oluşturur.
6. User message/context oluşturur.
7. LLM generate çağırır.
8. Cevaptaki kaynakları numaralı citation formatına normalize eder.
9. `AssistantResponse` oluşturur.
10. `_response_to_dict()` ile JSON payload üretir.

**Bu fonksiyonu anlatırken şu şemayı çiz:**

```text
token + question
    ↓
authenticate
    ↓
route query
    ↓
RAG search?      RBAC query?
    ↓                 ↓
rag_results       db_result
    ↓                 ↓
ContextBuilder
    ↓
LLM generate
    ↓
normalize citations
    ↓
JSON response
```

### `list_permissions(token) -> dict`

**Ne yapar?**

- Kullanıcının permission özetini döndürür.

### `ingest_all_documents(reset=True) -> dict`

**Ne yapar?**

- Tüm bilgi bankası dokümanlarını yeniden chunk + embedding yapar.

### `ingest_document(token, title, content, category) -> dict`

**Ne yapar?**

- Kullanıcıyı authenticate eder.
- Yeni dokümanı RAG indeksine ekler.

### `list_user_documents(token) -> dict`

**Ne yapar?**

- Kullanıcının yüklediği dokümanları listeler.

### `delete_user_document(token, doc_id) -> dict`

**Ne yapar?**

- Kullanıcının kendi dokümanını siler.
- Başkasının dokümanını silmeye çalışırsa permission hatası verir.

### `_query_result_to_dict(result) -> dict`

**Ne yapar?**

- `QueryResult` dataclass objesini API JSON formatına çevirir.

**Çıktıda ne var?**

```text
table
filter
access_scope
count
records
total_amount, varsa
```

### `_response_to_dict(resp) -> dict`

**Ne yapar?**

- `AssistantResponse` objesini API JSON payload’a çevirir.

**Önemli ek alanlar:**

```text
rag_sources
rag_citations
db_result
```

### `_build_snippet(text, max_len=220) -> str`

**Ne yapar?**

- RAG chunk metnini kısa snippet’e çevirir.
- Fazla whitespace temizler.
- Uzunsa `…` ile keser.

**Neden önemli?**

- UI’da kaynak kartında tüm dokümanı göstermek yerine kısa kanıt parçası gösterilir.

### `_normalize_rag_citations(answer, rag_results) -> str`

**Ne yapar?**

- LLM cevapta `[Ders Kayıt Yönergesi]` gibi başlıkla atıf verirse bunu `[1]` formatına çevirir.
- Zaten `[1]` verdiyse dokunmaz.

**Neden önemli?**

- LLM her zaman tam istediğimiz formatı takip etmeyebilir.
- Backend bunu standardize eder.

### `build_server(config=None) -> MCPServer`

**Ne yapar?**

- Tüm dependency graph’ı kurar.

Oluşturduğu bileşenler:

```text
DatabaseManager
LLMProvider
VectorStore
TextChunker
RAGPipeline
Authenticator
RBACEngine
QueryRouter
ContextBuilder
MCPServer
```

**Anlatırken söyle:**

> Uygulama wiring burada yapılıyor. Burası dependency assembly noktası.

### `create_app(config=None) -> FastMCP`

**Ne yapar?**

- FastMCP app oluşturur.
- MCP tool fonksiyonlarını register eder.

Registered tools:

```text
search_knowledge
query_records
ask_question
list_permissions
```

### `get_mcp_app() -> FastMCP`

**Ne yapar?**

- Lazy singleton app döndürür.

**Neden lazy?**

- Import sırasında embedding model yüklenmesin diye.
- Testlerde CUDA/OOM gibi sorunları engeller.

---

## 22.21 `src/web/app.py` — FastAPI ve UI Fonksiyonları

### `AskRequest`

**Ne yapar?**

- `/api/ask` request body modelidir.

Alanlar:

```text
token
question
```

### `IngestRequest`

**Ne yapar?**

- `/api/ingest` endpointi için request body modelidir.

Alanlar:

```text
token
title
content
category
```

### `_build_html() -> str`

**Ne yapar?**

- Tek sayfalık HTML/CSS/JS UI üretir.

UI içinde:

- Token input.
- Soru textarea.
- Örnek soru butonları.
- Doküman upload formu.
- Sonuç paneli.
- Route badge.
- Metadata chipleri.
- Kaynak kartları.
- Ham JSON çıktısı.

Önemli JS fonksiyonları:

| JS Fonksiyonu | Görev |
|---|---|
| `setBusy()` | Status text değiştirir. |
| `setRoute()` | Route badge rengini ve metnini ayarlar. |
| `renderMeta()` | User, role, table, count bilgilerini gösterir. |
| `renderSources()` | `rag_citations` listesinden kaynak kartları üretir. |
| `escapeHtml()` | XSS riskine karşı text escape eder. |
| `renderAnswer()` | Cevaptaki `[1]` değerlerini tıklanabilir link yapar. |
| `renderResult()` | API cevabını UI’a basar. |
| `renderError()` | Hata mesajını gösterir. |

### `create_fastapi_app() -> FastAPI`

**Ne yapar?**

- AppConfig okur.
- `build_server(config)` ile MCPServer kurar.
- FastAPI app oluşturur.
- CORS middleware ekler.
- Endpointleri tanımlar.

### `index() -> HTMLResponse`

**Endpoint:**

```text
GET /
```

**Ne yapar?**

- `_build_html()` çıktısını döndürür.

### `health() -> dict`

**Endpoint:**

```text
GET /api/health
```

**Ne yapar?**

- Basit health response döndürür.

```json
{"status": "ok"}
```

### `ask(body: AskRequest) -> dict`

**Endpoint:**

```text
POST /api/ask
```

**Ne yapar?**

- Request body’den token ve question alır.
- `server.ask_question()` çağırır.
- Authentication hatasını `401` döndürür.
- Permission hatasını `403` döndürür.
- Diğer hataları `500` döndürür.

### `upload_document(...) -> dict`

**Endpoint:**

```text
POST /api/upload
```

**Ne yapar?**

1. Token, title, file ve category alır.
2. Dosya adını sanitize eder.
3. Uzantı kontrolü yapar.
4. Dosya boyutu kontrolü yapar.
5. PDF ise text extract eder.
6. TXT/MD ise UTF-8 decode eder.
7. `server.ingest_document()` çağırır.
8. Dokümanı RAG indeksine ekler.

**Desteklenen dosyalar:**

```text
.txt
.md
.pdf
```

### `ingest_text(body: IngestRequest) -> dict`

**Endpoint:**

```text
POST /api/ingest
```

**Ne yapar?**

- JSON body ile gelen doküman içeriğini ingest eder.

### `list_documents(token: str) -> dict`

**Endpoint:**

```text
GET /api/documents
```

**Ne yapar?**

- Authenticated kullanıcının yüklediği dokümanları listeler.

### `delete_document(doc_id: int, token: str) -> dict`

**Endpoint:**

```text
DELETE /api/documents/{doc_id}
```

**Ne yapar?**

- Kullanıcının kendi dokümanını siler.

---

## 22.22 `scripts/` Klasörü

### `scripts/setup_db.py::main()`

**Ne yapar?**

- Config okur.
- DatabaseManager oluşturur.
- `setup()` çağırarak schema + seed çalıştırır.
- DB connection kapatır.

### `scripts/ingest.py::main()`

**Ne yapar?**

- Config okur.
- DB manager, vector store, chunker ve RAG pipeline kurar.
- `rag.ingest(reset=True)` çağırır.
- Tüm dokümanları yeniden indexler.

### `scripts/demo.py::main()`

**Ne yapar?**

- Interactive CLI demo başlatır.
- Kullanıcıdan token ve soru alır.
- `MCPServer.ask_question()` benzeri akışla cevap döndürür.

### `scripts/migrate_add_user_id.py::main()`

**Ne yapar?**

- Var olan DB’ye doküman sahipliği için `user_id` migration uygular.

---

## 22.23 Test Dosyaları Fonksiyonel Bakış

### `tests/test_auth.py`

**Ne test eder?**

- Geçerli token authenticate oluyor mu?
- Geçersiz token hata veriyor mu?

### `tests/test_rbac.py`

**Ne test eder?**

- Admin tüm kayıtları görebiliyor mu?
- Manager department scope ile filtreleniyor mu?
- Viewer own scope ile filtreleniyor mu?
- Yetkisiz tablo hatası doğru mu?

### `tests/test_router.py`

**Ne test eder?**

- RAG keywordleri doğru route ediyor mu?
- MCP keywordleri doğru route ediyor mu?
- Hybrid sorgular doğru route ediliyor mu?
- Türkçe sorgular doğru sınıflanıyor mu?
- Hybrid sorgudan RAG alt sorgusu doğru çıkarılıyor mu?

### `tests/test_rag.py`

**Ne test eder?**

- Chunker temel parçalama davranışı.
- Overlap davranışı.
- Empty text davranışı.
- Reranking doğru dokümanı öne alıyor mu?

### `tests/test_text_normalization.py`

**Ne test eder?**

- Türkçe harf normalization.
- Suffix indirgeme.
- Embedding augment.
- Türkçe query detection.
- ContextBuilder Türkçe cevap talimatı.

### `tests/test_server.py`

**Ne test eder?**

- `rag_citations` API payload’a ekleniyor mu?
- Citation index doğru mu?
- Başlık atıfı `[1]` formatına normalize ediliyor mu?

### `tests/test_integration.py`

**Ne test eder?**

- Gerçek PostgreSQL bağlantısı varsa uçtan uca authentication, RBAC, RAG ve router davranışı.

**Neden skip olabilir?**

- Integration testler `RUN_INTEGRATION_TESTS=1` gerektirir.

---

## 23. Kod Üzerinden Canlı Anlatım İçin Hazır Senaryo

Bu bölümü Claude’a verirsen PPT akışına da dönüştürebilir. Kod açarak anlatırken şu sırayı takip et.

### 23.1 İlk Açılacak Dosya: `src/mcp/server.py`

Gösterilecek fonksiyon:

```text
ask_question()
```

Konuşma:

> Bu fonksiyon sistemin ana akışı. Kullanıcıdan token ve soru geliyor. Önce kullanıcı authenticate ediliyor, sonra soru route ediliyor, sonra route’a göre RAG veya DB çalışıyor, sonra context LLM’e veriliyor ve cevap dönüyor.

### 23.2 Sonra Router’a Git: `src/router/classifier.py`

Gösterilecek fonksiyonlar:

```text
route()
_detect_table()
_extract_rag_query()
```

Konuşma:

> Burada doğal dil sorusunun hangi execution path’e gideceği seçiliyor. Hybrid sorularda RAG kısmını ayırmak retrieval kalitesi için kritik.

### 23.3 RBAC’a Git: `src/db/manager.py` ve `src/rbac/engine.py`

Gösterilecek fonksiyonlar:

```text
query_records()
_build_filters()
RBACEngine.query()
```

Konuşma:

> Yetki kontrolü model promptuna bırakılmıyor. SQL sorgusu role göre filtreleniyor.

### 23.4 RAG’a Git: `src/rag/pipeline.py`

Gösterilecek fonksiyonlar:

```text
search()
_lexical_search()
_merge_results()
_ngram_overlap()
```

Konuşma:

> RAG sadece vector search değil. Türkçe için lexical fallback ve reranking ekledik. Bu, doğru dokümanı öne almak için gerekli oldu.

### 23.5 Türkçe Normalization’a Git: `src/text/normalization.py`

Gösterilecek fonksiyonlar:

```text
normalize_for_matching()
tokenize_for_matching()
augment_for_embedding()
```

Konuşma:

> Türkçe karakter ve ekler retrieval kalitesini bozabiliyor. Bu yüzden sorgu ve doküman metinlerini karşılaştırılabilir forma indiriyoruz.

### 23.6 Prompt’a Git: `src/router/context_builder.py`

Gösterilecek fonksiyonlar:

```text
build_system_prompt()
build_user_message()
```

Konuşma:

> LLM’e verilen bilgi burada sınırlandırılıyor. Model DB’ye kendisi gitmiyor, sadece bizim verdiğimiz context’i görüyor.

### 23.7 UI’a Git: `src/web/app.py`

Gösterilecek noktalar:

```text
/api/ask endpointi
renderAnswer()
renderSources()
```

Konuşma:

> UI sadece cevabı göstermiyor; route bilgisini, RBAC metadata’sını, raw JSON’u ve kaynak kartlarını da gösteriyor. `[1]` tıklanınca ilgili kaynak kartına gidiyor.

### 23.8 Testlere Git

Gösterilecek dosyalar:

```text
tests/test_router.py
tests/test_rag.py
tests/test_server.py
```

Konuşma:

> Kritik davranışları testledik: routing, Türkçe normalization, RAG reranking ve citation serialization.

---

## 24. PPT’ye Dönüştürmek İçin Bölüm Başlıkları

Bu Markdown’dan PPT çıkarırken şu başlıkları kullanabilirsin:

1. Projenin Amacı
2. Sistem Mimarisi
3. Kullanıcı İsteği Akışı
4. Config ve Environment
5. Database Schema ve Seed Verisi
6. RBAC: Role, Permission, Scope
7. RAG Pipeline
8. Türkçe Normalization
9. Query Routing
10. Hybrid Soru Ayrıştırma
11. ContextBuilder ve Prompt Tasarımı
12. LLM Provider Katmanı
13. MCPServer: Ana Orchestration
14. IEEE Benzeri Atıf Sistemi
15. Web UI ve Kullanıcı Deneyimi
16. Test Stratejisi
17. Canlı Demo
18. Teknik Kararlar
19. Sınırlamalar ve İyileştirme Fırsatları
20. Sonuç

Her slaytta maksimum 3-5 madde kullan. Kod anlatımı sırasında ayrıntıyı sözlü ver; slaytlar sadece iskelet olsun.


## 25. MCPServer ve LLM İlişkisi: Kim Kimi Çağırıyor?

Bu bölüm özellikle önemli; çünkü “MCP server var mı?”, “LLM bunu mu çağırıyor?”, “tool calling var mı?” gibi sorular gelebilir.

Kısa cevap:

> Bu projede MCPServer var, fakat mevcut web UI akışında LLM MCP server’ı doğrudan çağırmıyor. MCPServer backend orchestration katmanı olarak çalışıyor; önce RAG ve RBAC context’i topluyor, sonra LLM’i çağırıyor.

### 25.1 MCP Server Var mı?

Evet, var.

Ana dosya:

```text
src/mcp/server.py
```

Bu dosyada iki şey var:

1. `MCPServer` class’ı
2. `FastMCP` app/tool tanımı

Önemli class:

```python
class MCPServer:
    ...
```

Önemli factory:

```python
def create_app(config: AppConfig | None = None) -> FastMCP:
    ...
```

Burada FastMCP tool’ları tanımlanıyor:

```python
@mcp.tool()
def search_knowledge(query: str, top_k: int = 3) -> dict:
    ...

@mcp.tool()
def query_records(token: str, table: str) -> dict:
    ...

@mcp.tool()
def ask_question(token: str, question: str) -> dict:
    ...

@mcp.tool()
def list_permissions(token: str) -> dict:
    ...
```

Yani proje içinde MCP tool server olarak expose edilebilecek bir katman var.

### 25.2 Web UI MCP Protokolünü mü Kullanıyor?

Hayır.

Web UI tarafı şu dosyada:

```text
src/web/app.py
```

FastAPI uygulaması `build_server(config)` çağırarak aynı `MCPServer` class’ını Python objesi olarak kullanıyor.

Yani browser’dan gelen istek şu şekilde ilerliyor:

```text
Browser UI
  ↓ HTTP
FastAPI /api/ask
  ↓ Python method call
MCPServer.ask_question()
```

Bu akışta browser bir MCP client değildir.

Web UI, MCP tool protokolüyle konuşmaz. HTTP endpoint üzerinden backend’e gelir.

### 25.3 LLM MCP Server’ı Çağırıyor mu?

Mevcut projede hayır.

Bu projede LLM’in rolü şudur:

```text
Hazırlanmış context'i alır → doğal dil cevabı üretir
```

LLM’in yapmadığı şeyler:

- MCP tool çağırmaz.
- DB sorgusu atmaz.
- RAG search başlatmaz.
- RBAC kararı vermez.
- Kullanıcının hangi kayıtları görebileceğine karar vermez.

Bunların hepsini backend yapar.

Doğru çağrı yönü:

```text
User
  ↓
FastAPI / MCPServer
  ↓
Authentication
  ↓
QueryRouter
  ↓
RAG search + RBAC DB query
  ↓
ContextBuilder
  ↓
LLM
  ↓
Final answer
```

Yani LLM en sonda çağrılır.

### 25.4 Mevcut Projede Asıl Orchestration Kimde?

Asıl orchestration `MCPServer.ask_question()` fonksiyonundadır.

Bu fonksiyon:

1. Kullanıcıyı authenticate eder.
2. Soruyu route eder.
3. Gerekirse RAG search yapar.
4. Gerekirse RBAC filtreli DB query yapar.
5. Prompt/context hazırlar.
6. LLM’i çağırır.
7. Cevap + citation + DB result payload’unu döndürür.

Basitleştirilmiş akış:

```python
user = self._rbac.authenticate(token)
decision = self._router.route(question)

if decision.route in (RouteType.RAG, RouteType.HYBRID):
    rag_results = self._rag.search(...)

if decision.route in (RouteType.MCP, RouteType.HYBRID):
    db_result = self._rbac.query(...)

system_prompt = self._ctx.build_system_prompt(user, question)
user_message = self._ctx.build_user_message(...)

answer = self._llm.generate(system_prompt, user_message)
```

Burada LLM sadece son adımdadır.

### 25.5 “LLM MCP Tool Çağırsaydı” Akış Nasıl Olurdu?

Eğer sistem agentic tool-calling mimarisinde olsaydı akış şöyle olurdu:

```text
User
  ↓
LLM Agent
  ↓ tool call
MCP Server tool
  ↓ tool result
LLM Agent
  ↓
Final answer
```

Bu mimaride LLM şuna karar verirdi:

- Hangi tool çağrılacak?
- Tool parametreleri ne olacak?
- Tool sonucu nasıl yorumlanacak?

Ancak mevcut projede böyle değil.

Mevcut projede akış şu:

```text
User
  ↓
Backend Orchestrator
  ↓
RAG / RBAC / DB işlemleri
  ↓
LLM'e hazırlanmış context
  ↓
Final answer
```

### 25.6 Bu Mimari Neden Daha Kontrollü?

Bu yaklaşımın avantajları:

- RBAC kararları LLM’e bırakılmaz.
- DB sorguları backend tarafından deterministic yapılır.
- RAG retrieval backend tarafından kontrol edilir.
- LLM sadece izin verilen context’i görür.
- Güvenlik sınırları daha nettir.
- Debug etmek daha kolaydır.

Özellikle RBAC için bu çok önemlidir.

Yanlış yaklaşım:

```text
LLM'e tüm kayıtları verip “viewer sadece kendi kaydını görsün” demek.
```

Doğru yaklaşım:

```text
Viewer için SQL seviyesinde advisor_id = user.id filtresi uygulamak.
```

Bu projede doğru yaklaşım kullanılıyor.

### 25.7 Sunumda Nasıl Söylenmeli?

Sunumda şu cümleyi kullanabilirsin:

> Bu projede MCPServer iki rol taşıyor: Birincisi FastMCP tool server olarak dışarıya tool expose edebiliyor. İkincisi, web uygulamasında core backend orchestration class’ı olarak kullanılıyor. Ancak mevcut web akışında LLM MCP tool çağırmıyor; backend gerekli RAG ve RBAC verisini topladıktan sonra LLM’i sadece cevap üretmesi için çağırıyor.

Daha kısa versiyon:

> LLM tool çağıran taraf değil; LLM cevap üreten son katman. Tool/data orchestration backend tarafında.

### 25.8 Kod Üzerinde Nereler Gösterilmeli?

Bu ayrımı anlatırken şu dosyaları aç:

1. `src/mcp/server.py`
   - `MCPServer.ask_question()`
   - `create_app()`
   - `@mcp.tool()` tanımları

2. `src/web/app.py`
   - `create_fastapi_app()`
   - `/api/ask` endpointi
   - `server.ask_question(...)` çağrısı

3. `src/llm/ollama_provider.py`
   - `generate(...)`
   - LLM’in sadece prompt aldıktan sonra cevap ürettiğini göster

### 25.9 Şematik Özet

Mevcut proje:

```text
Browser
  ↓ HTTP
FastAPI
  ↓
MCPServer.ask_question()
  ↓
RAG + RBAC + DB
  ↓
ContextBuilder
  ↓
LLM.generate()
  ↓
Answer + citations
```

Agentic MCP tool-calling olsaydı:

```text
Browser / User
  ↓
LLM Agent
  ↓ MCP tool call
MCP Server
  ↓ tool result
LLM Agent
  ↓
Final answer
```

Bu proje birinci akışı kullanıyor.

### 25.10 Soru Gelirse Hazır Cevap

Soru:

```text
Bu projede MCP var ama LLM mi çağırıyor?
```

Cevap:

```text
Hayır, mevcut web akışında LLM MCP tool çağırmıyor. MCPServer backend orchestration katmanı olarak çalışıyor. Önce token doğrulama, routing, RAG retrieval ve RBAC filtreli DB sorgusu backend tarafında yapılıyor. Sonra bu bilgiler ContextBuilder ile prompt haline getiriliyor ve LLM yalnızca cevap üretmek için çağrılıyor.
```


## 26. Production Seviyesi Router Güncellemesi: Keyword Router’dan Structured LLM Router’a

Bu bölüm, router eleştirisini ve yapılan mimari iyileştirmeyi anlatmak için eklendi. Sunumda bunu özellikle vurgulamak iyi olur; çünkü “kelime bazlı router production için yeterli mi?” sorusu teknik olarak çok yerinde bir sorudur.

### 26.1 Eski Router’ın Problemi

İlk router kural tabanlıydı:

```text
keyword varsa → RAG
keyword varsa → MCP
ikisi de varsa → HYBRID
```

Bu yaklaşım demo için anlaşılırdır ama production için zayıftır.

Problemler:

- Kelime eşleşmesine fazla bağımlıdır.
- Bağlamı anlamaz.
- Türkçedeki ekler ve eş anlamlılar route hatası yaratabilir.
- `öğrenci` kelimesi hem DB tablosu hem doküman başlığı içinde geçebilir.
- Yeni domain geldikçe keyword listesi büyür ve bakımı zorlaşır.
- Hybrid sorularda belge kısmı ve DB kısmını doğru ayırmak zorlaşır.

Örnek problemli soru:

```text
Öğrenci davranış kuralları nedir?
```

Bu soru RAG sorusudur. Ancak sadece `öğrenci` kelimesine bakmak DB/MCP yönüne yanlış sinyal verebilir.

### 26.2 Yeni Yaklaşım

Yeni yaklaşım iki katmanlıdır:

```text
User question
  ↓
Deterministic fallback router
  ↓
Structured LLM router
  ↓
Pydantic/schema validation
  ↓
RBAC-safe backend execution
```

Burada LLM SQL yazmaz. LLM sadece structured intent üretir.

### 26.3 Structured LLM Router Ne Üretiyor?

Yeni router dosyası:

```text
src/router/llm_router.py
```

LLM’den istenen çıktı şu şekildedir:

```json
{
  "route": "hybrid",
  "rag_query": "Fazla yük almak için şartlar nelerdir?",
  "db_intent": {
    "table": "ogrenci_bilgi_sistemi",
    "operation": "count",
    "filters": {
      "bolum": "electronics",
      "gpa_gt": 3.5
    }
  },
  "confidence": 0.94
}
```

Bu output doğal dil cevabı değildir. Bu sadece route ve intent planıdır.

### 26.4 Neden SQL Yazdırmıyoruz?

LLM’e SQL yazdırmak risklidir:

- SQL injection riski doğabilir.
- RBAC filtreleri bypass edilebilir.
- Tablo/kolon hallucination olabilir.
- Production güvenliği zayıflar.

Bu projede doğru yaklaşım kullanılır:

```text
LLM intent çıkarır
Backend validate eder
Backend RBAC filtresi ekler
Backend güvenli sorgu/filtre uygular
```

### 26.5 Schema Validation

`src/router/llm_router.py` içinde Pydantic modelleri kullanılır:

```text
StructuredRoute
StructuredDBIntent
```

Allowed değerler:

```text
route: rag, mcp, hybrid
operation: list, count, sum, average, max, min
table: orders, refunds, ogrenci_bilgi_sistemi
```

Allowed filterlar tabloya göre sınırlıdır:

```text
ogrenci_bilgi_sistemi:
  bolum, sinif, advisor_id, gpa_gt, gpa_gte, gpa_lt, gpa_lte

orders:
  department, status, assigned_to, amount_gt, amount_gte, amount_lt, amount_lte

refunds:
  department, processed_by, amount_gt, amount_gte, amount_lt, amount_lte
```

Eğer LLM geçersiz filter üretirse karar reddedilir ve deterministic fallback router’a dönülür.

### 26.6 Deterministic Fallback Neden Hâlâ Var?

LLM router production seviyesine daha yakın olsa da fallback gerekir.

Fallback şu durumlarda kullanılır:

- LLM timeout olur.
- LLM JSON yerine açıklama döndürür.
- JSON parse edilemez.
- Pydantic validation fail olur.
- Confidence düşük döner.
- Geçersiz tablo/filter/operation üretir.

Bu sayede sistem tamamen LLM router’a bağımlı kalmaz.

### 26.7 Backend Intent Filtering

Yeni intent filtreleri backend tarafında güvenli şekilde uygulanır.

Dosya:

```text
src/mcp/server.py
```

İlgili fonksiyon:

```text
_apply_db_intent(result, intent)
```

Bu fonksiyon:

1. RBAC filtreli DB sonucunu alır.
2. LLM router’dan gelen intent filterlarını kontrol eder.
3. Sadece allowlist içindeki filterları uygular.
4. Kayıtları daraltır.
5. `QueryResult.count` değerini günceller.
6. `filter_description` alanına intent filter açıklaması ekler.

Örnek:

```text
Soru:
Ders kayıt yönergesine göre fazla yük şartları nelerdir ve electronics bölümünde GPA'si 3.5 üstü kaç öğrenci var?
```

LLM router intent:

```json
{
  "table": "ogrenci_bilgi_sistemi",
  "operation": "count",
  "filters": {
    "bolum": "electronics",
    "gpa_gt": 3.5
  }
}
```

Backend önce RBAC uygular, sonra intent filter uygular.

Admin için:

```text
base records: tüm öğrenciler
intent filters: bolum = electronics, gpa > 3.5
sonuç: Selin Acar
```

Viewer için:

```text
base records: advisor_id = viewer.id
intent filters: bolum = electronics, gpa > 3.5
sonuç: sadece viewer'ın yetkili olduğu kayıtlar içinde filtrelenmiş sonuç
```

Yani LLM router RBAC’i override edemez.

### 26.8 MCP Tool Güncellemesi

MCP tool olarak routing kararını dışarı açmak için yeni tool eklendi:

```text
route_question(token, question)
```

Dosya:

```text
src/mcp/server.py
```

Bu tool ne yapar?

- Kullanıcıyı authenticate eder.
- Sadece routing decision döndürür.
- RAG/DB/LLM final answer üretmez.

Örnek output:

```json
{
  "route": "hybrid",
  "rag_query": "Fazla yük almak için şartlar nelerdir?",
  "db_table": "ogrenci_bilgi_sistemi",
  "confidence": 0.94,
  "source": "llm",
  "db_intent": {
    "table": "ogrenci_bilgi_sistemi",
    "operation": "count",
    "filters": {
      "bolum": "electronics",
      "gpa_gt": 3.5
    }
  }
}
```

Web debug için ayrıca endpoint eklendi:

```text
POST /api/route
```

Bu endpoint route kararını görmeyi kolaylaştırır.

### 26.9 Yeni Akış

Güncel production’a daha yakın akış:

```text
User question
  ↓
FastAPI / MCPServer
  ↓
Auth
  ↓
LLMQueryRouter
  ↓
Structured JSON route intent
  ↓
Pydantic validation
  ↓
RAG search and/or RBAC DB query
  ↓
Safe intent filters
  ↓
ContextBuilder
  ↓
LLM final answer
```

Buradaki kritik ayrım:

```text
Router LLM intent çıkarır.
Answer LLM cevap üretir.
DB SQL backend tarafından kontrol edilir.
RBAC backend tarafından uygulanır.
```

### 26.10 Sunumda Nasıl Söylenmeli?

Şu cümleyi kullan:

> İlk router keyword-based olduğu için prototip seviyesindeydi. Production’a yaklaşmak için bunu structured LLM router ile değiştirdik. LLM artık SQL yazmıyor; sadece route, operation, table ve filter intent’i JSON olarak çıkarıyor. Bu JSON Pydantic ile validate ediliyor, allowlist dışı tablo veya filter reddediliyor. RBAC ise hâlâ backend tarafında SQL/veri katmanında uygulanıyor.

Daha kısa versiyon:

> Keyword router yerine schema-validated structured intent router kullandık. LLM karar öneriyor, backend güvenli şekilde uygulatıyor.

