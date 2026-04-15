"""FastAPI wrapper exposing HTTP endpoints + simple chat UI."""

from __future__ import annotations

import io
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

try:
    import pypdf
except ImportError:
    pypdf = None

from src.config import AppConfig
from src.mcp.server import MCPServer, build_server
from src.models.exceptions import AuthenticationError, PermissionDeniedError


class AskRequest(BaseModel):
    token: str | None = None
    question: str


class IngestRequest(BaseModel):
    token: str | None = None
    title: str
    content: str
    category: str | None = None


class QueryIntentRequest(BaseModel):
    token: str | None = None
    table: str
    operation: str = "list"
    filters: dict | None = None


class SetTokenRequest(BaseModel):
    token: str
    session_id: str = "default"


class SearchKnowledgeRequest(BaseModel):
    query: str
    top_k: int = 3


def _build_html() -> str:
    return (
        """
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Üniversite AI Asistanı</title>
            <style>
                :root {
                    color-scheme: light;
                    --bg: #0f172a;
                    --panel: rgba(255, 255, 255, 0.92);
                    --panel-soft: rgba(255, 255, 255, 0.72);
                    --text: #0f172a;
                    --muted: #475569;
                    --line: rgba(148, 163, 184, 0.35);
                    --primary: #2563eb;
                    --primary-dark: #1d4ed8;
                    --accent: #7c3aed;
                    --success: #059669;
                    --warning: #d97706;
                    --shadow: 0 18px 48px rgba(15, 23, 42, 0.16);
                }

                * { box-sizing: border-box; }
                body {
                    margin: 0;
                    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                    color: var(--text);
                    background:
                        radial-gradient(circle at top left, rgba(37, 99, 235, 0.25), transparent 28%),
                        radial-gradient(circle at top right, rgba(124, 58, 237, 0.22), transparent 24%),
                        linear-gradient(180deg, #eff6ff 0%, #eef2ff 45%, #f8fafc 100%);
                    min-height: 100vh;
                    scroll-behavior: smooth;
                }

                .shell {
                    max-width: 1320px;
                    margin: 0 auto;
                    padding: 32px 20px 48px;
                }

                .hero {
                    display: grid;
                    grid-template-columns: 1.3fr 0.8fr;
                    gap: 20px;
                    margin-bottom: 22px;
                }

                .hero-card,
                .stats-card,
                .panel,
                .result-card {
                    background: var(--panel);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.75);
                    border-radius: 24px;
                    box-shadow: var(--shadow);
                }

                .hero-card {
                    padding: 28px;
                }

                .eyebrow {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 12px;
                    border-radius: 999px;
                    background: rgba(37, 99, 235, 0.10);
                    color: var(--primary-dark);
                    font-weight: 700;
                    font-size: 13px;
                    margin-bottom: 14px;
                }

                h1 {
                    margin: 0 0 10px;
                    font-size: clamp(30px, 4vw, 44px);
                    line-height: 1.05;
                    letter-spacing: -0.03em;
                }

                .hero p,
                .muted {
                    color: var(--muted);
                    line-height: 1.65;
                    margin: 0;
                }

                .stats-card {
                    padding: 24px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    gap: 18px;
                }

                .token-list,
                .example-list,
                .meta-list,
                .source-list {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                }

                .token-chip,
                .example-chip,
                .meta-chip,
                .route-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    border-radius: 999px;
                    padding: 8px 12px;
                    font-size: 13px;
                    font-weight: 600;
                }

                .token-chip {
                    background: rgba(15, 23, 42, 0.06);
                    color: var(--text);
                }

                .meta-chip {
                    background: rgba(37, 99, 235, 0.10);
                    color: var(--primary-dark);
                }

                .example-chip {
                    border: 1px solid rgba(37, 99, 235, 0.18);
                    background: #fff;
                    color: var(--primary-dark);
                    cursor: pointer;
                    transition: 0.18s ease;
                }

                .example-chip:hover {
                    transform: translateY(-1px);
                    border-color: rgba(37, 99, 235, 0.35);
                    background: rgba(37, 99, 235, 0.06);
                }

                .route-badge.route-rag { background: rgba(37, 99, 235, 0.12); color: var(--primary-dark); }
                .route-badge.route-mcp { background: rgba(5, 150, 105, 0.12); color: var(--success); }
                .route-badge.route-hybrid { background: rgba(124, 58, 237, 0.12); color: var(--accent); }

                .layout {
                    display: grid;
                    grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
                    gap: 20px;
                    align-items: start;
                }

                .stack {
                    display: grid;
                    gap: 20px;
                }

                .panel {
                    padding: 22px;
                }

                .panel h2,
                .panel h3,
                .result-card h3,
                .stats-card h3 {
                    margin: 0 0 10px;
                    font-size: 18px;
                    letter-spacing: -0.02em;
                }

                .panel-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    gap: 16px;
                    margin-bottom: 18px;
                }

                label {
                    display: block;
                    margin: 14px 0 6px;
                    font-size: 14px;
                    font-weight: 700;
                }

                input,
                textarea {
                    width: 100%;
                    border: 1px solid var(--line);
                    border-radius: 16px;
                    background: rgba(255, 255, 255, 0.92);
                    padding: 13px 14px;
                    font: inherit;
                    color: var(--text);
                    transition: border-color 0.18s ease, box-shadow 0.18s ease;
                }

                textarea {
                    min-height: 132px;
                    resize: vertical;
                    line-height: 1.55;
                }

                input:focus,
                textarea:focus {
                    outline: none;
                    border-color: rgba(37, 99, 235, 0.45);
                    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
                }

                .button-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 12px;
                    margin-top: 16px;
                }

                button {
                    border: none;
                    border-radius: 14px;
                    padding: 12px 16px;
                    font: inherit;
                    font-weight: 700;
                    cursor: pointer;
                    transition: transform 0.16s ease, opacity 0.16s ease, background 0.16s ease;
                }

                button:disabled {
                    opacity: 0.6;
                    cursor: wait;
                    transform: none;
                }

                button:hover:not(:disabled) {
                    transform: translateY(-1px);
                }

                .primary-btn {
                    background: linear-gradient(135deg, var(--primary), var(--accent));
                    color: white;
                    box-shadow: 0 10px 24px rgba(37, 99, 235, 0.25);
                }

                .secondary-btn {
                    background: rgba(15, 23, 42, 0.06);
                    color: var(--text);
                }

                .result-card {
                    padding: 22px;
                    position: sticky;
                    top: 24px;
                }

                .result-answer {
                    min-height: 140px;
                    padding: 16px;
                    border-radius: 18px;
                    background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(248,250,252,0.95));
                    border: 1px solid rgba(148, 163, 184, 0.24);
                    white-space: pre-wrap;
                    line-height: 1.7;
                }

                .result-answer a {
                    color: var(--primary-dark);
                    font-weight: 800;
                    text-decoration: none;
                    border-bottom: 1px dashed rgba(37, 99, 235, 0.45);
                }

                .result-answer a:hover {
                    color: var(--accent);
                    border-bottom-color: rgba(124, 58, 237, 0.55);
                }

                .status {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    margin-top: 12px;
                    font-size: 13px;
                    color: var(--muted);
                }

                .status-dot {
                    width: 9px;
                    height: 9px;
                    border-radius: 999px;
                    background: var(--success);
                    box-shadow: 0 0 0 6px rgba(5, 150, 105, 0.10);
                }

                .result-section {
                    margin-top: 18px;
                    padding-top: 18px;
                    border-top: 1px solid rgba(148, 163, 184, 0.22);
                }

                .source-list {
                    gap: 10px;
                    flex-direction: column;
                }

                .source-item {
                    display: inline-flex;
                    padding: 8px 10px;
                    border-radius: 12px;
                    background: rgba(15, 23, 42, 0.05);
                    font-size: 13px;
                    color: var(--text);
                }

                .source-card {
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 16px;
                    background: rgba(15, 23, 42, 0.04);
                    border: 1px solid rgba(148, 163, 184, 0.18);
                    display: grid;
                    gap: 6px;
                    scroll-margin-top: 24px;
                    transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
                }

                .source-card:target {
                    border-color: rgba(37, 99, 235, 0.45);
                    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
                    background: rgba(37, 99, 235, 0.05);
                }

                .source-heading {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }

                .source-index {
                    width: 28px;
                    height: 28px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 999px;
                    background: rgba(37, 99, 235, 0.12);
                    color: var(--primary-dark);
                    font-size: 13px;
                    font-weight: 800;
                    flex: 0 0 auto;
                }

                .source-card strong {
                    font-size: 14px;
                }

                .source-meta {
                    font-size: 12px;
                    color: var(--primary-dark);
                    margin-bottom: 8px;
                }

                .source-snippet {
                    font-size: 13px;
                    line-height: 1.6;
                    color: var(--muted);
                }

                details {
                    margin-top: 16px;
                }

                summary {
                    cursor: pointer;
                    font-weight: 700;
                    color: var(--primary-dark);
                }

                pre {
                    margin: 12px 0 0;
                    white-space: pre-wrap;
                    word-break: break-word;
                    background: #0f172a;
                    color: #e2e8f0;
                    padding: 16px;
                    border-radius: 16px;
                    overflow: auto;
                    max-height: 320px;
                }

                .helper {
                    margin-top: 10px;
                    font-size: 13px;
                    color: var(--muted);
                }

                .session-info {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    padding: 10px 14px;
                    border-radius: 14px;
                    background: rgba(5, 150, 105, 0.08);
                    border: 1px solid rgba(5, 150, 105, 0.18);
                    margin-top: 10px;
                    font-size: 13px;
                    color: var(--success);
                }

                .session-info.inactive {
                    background: rgba(148, 163, 184, 0.08);
                    border-color: rgba(148, 163, 184, 0.18);
                    color: var(--muted);
                }

                .session-info strong {
                    margin-right: 4px;
                }

                .danger-btn {
                    background: rgba(239, 68, 68, 0.08);
                    color: #ef4444;
                    border: 1px solid rgba(239, 68, 68, 0.18);
                }

                .danger-btn:hover:not(:disabled) {
                    background: rgba(239, 68, 68, 0.14);
                }

                .search-results {
                    margin-top: 14px;
                    display: grid;
                    gap: 12px;
                }

                .search-card {
                    padding: 14px;
                    border-radius: 14px;
                    background: rgba(15, 23, 42, 0.03);
                    border: 1px solid rgba(148, 163, 184, 0.18);
                }

                .search-card-title {
                    font-weight: 700;
                    font-size: 14px;
                    margin-bottom: 4px;
                }

                .search-card-meta {
                    font-size: 12px;
                    color: var(--primary-dark);
                    margin-bottom: 8px;
                }

                .search-card-snippet {
                    font-size: 13px;
                    color: var(--muted);
                    line-height: 1.55;
                }

                .tab-bar {
                    display: flex;
                    gap: 0;
                    margin-bottom: 18px;
                    border-bottom: 2px solid rgba(148, 163, 184, 0.18);
                }

                .tab-btn {
                    padding: 10px 18px;
                    font-weight: 700;
                    font-size: 14px;
                    color: var(--muted);
                    background: none;
                    border: none;
                    border-bottom: 3px solid transparent;
                    margin-bottom: -2px;
                    cursor: pointer;
                    transition: 0.15s ease;
                }

                .tab-btn:hover { color: var(--primary-dark); }
                .tab-btn.active {
                    color: var(--primary-dark);
                    border-bottom-color: var(--primary);
                }

                .tab-content { display: none; }
                .tab-content.active { display: block; }

                @media (max-width: 1024px) {
                    .hero,
                    .layout {
                        grid-template-columns: 1fr;
                    }

                    .result-card {
                        position: static;
                    }
                }

                @media (max-width: 640px) {
                    .shell {
                        padding: 18px 14px 32px;
                    }

                    .hero-card,
                    .stats-card,
                    .panel,
                    .result-card {
                        border-radius: 20px;
                    }
                }
            </style>
        </head>
        <body>
            <div class="shell">
                <section class="hero">
                    <div class="hero-card hero">
                        <div class="eyebrow">🎓 Üniversite AI Asistanı</div>
                        <h1>RAG + RBAC destekli öğrenci bilgi asistanı</h1>
                        <p>Akademik yönergeler, idari belgeler ve yetkili veri sorgularını tek ekranda birleştirir. Türkçe sorular, belge arama ve rol bazlı veri erişimi için optimize edilmiştir.</p>
                    </div>
                    <div class="stats-card">
                        <div>
                            <h3>Hızlı Token Seç</h3>
                            <div class="token-list">
                                <button class="token-chip" data-token="admin_token" style="cursor:pointer"><strong>admin_token</strong> Yönetici</button>
                                <button class="token-chip" data-token="manager_token" style="cursor:pointer"><strong>manager_token</strong> Bölüm Başkanı</button>
                                <button class="token-chip" data-token="viewer_token" style="cursor:pointer"><strong>viewer_token</strong> Öğrenci / Danışman</button>
                            </div>
                        </div>
                        <div>
                            <h3>Örnek sorular</h3>
                            <div class="example-list">
                                <button class="example-chip" data-question="Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?">Hybrid sorgu</button>
                                <button class="example-chip" data-question="Yurt başvuruları ne zaman açılır?">RAG sorgu</button>
                                <button class="example-chip" data-question="Öğrenci not ortalaması ve danışman bilgilerini göster">MCP sorgu</button>
                            </div>
                        </div>
                    </div>
                </section>

                <section class="layout">
                    <div class="stack">
                        <div class="panel">
                            <div class="tab-bar">
                                <button class="tab-btn active" data-tab="tab-ask">Soru Sor</button>
                                <button class="tab-btn" data-tab="tab-search">Bilgi Arama</button>
                                <button class="tab-btn" data-tab="tab-session">Oturum</button>
                                <button class="tab-btn" data-tab="tab-upload">Doküman Yükle</button>
                            </div>

                            <div id="tab-ask" class="tab-content active">
                                <label for="token">Token (opsiyonel — oturum tokeni varsa boş bırakın)</label>
                                <input id="token" placeholder="admin_token" />
                                <label for="question">Soru</label>
                                <textarea id="question" placeholder="Örn: Ders kayıt yönergesine göre fazla yük almak için şartlar nelerdir ve electronics bölümünde GPA'si 3.5 üstü kaç öğrenci vardır?"></textarea>
                                <div class="button-row">
                                    <button id="send" class="primary-btn">Soruyu Çalıştır</button>
                                    <button id="clear" class="secondary-btn" type="button">Temizle</button>
                                </div>
                                <div class="helper">İpucu: "ve" ile birleşik sorular genelde hybrid rotaya gider. Token boşsa oturum tokeni kullanılır.</div>
                            </div>

                            <div id="tab-search" class="tab-content">
                                <label for="searchQuery">Arama Sorgusu</label>
                                <input id="searchQuery" placeholder="Örn: W notu ne zaman verilir" />
                                <label for="searchTopK">Sonuç Sayısı</label>
                                <input id="searchTopK" type="number" value="3" min="1" max="10" />
                                <div class="button-row">
                                    <button id="searchBtn" class="primary-btn">Bilgi Tabanında Ara</button>
                                </div>
                                <div class="helper">Kimlik doğrulaması gerekmez. Yalnızca bilgi tabanında arama yapar.</div>
                                <div id="searchResults" class="search-results"></div>
                            </div>

                            <div id="tab-session" class="tab-content">
                                <label for="sessionToken">Token ile Oturum Aç</label>
                                <input id="sessionToken" placeholder="admin_token, manager_token, viewer_token..." />
                                <div class="button-row">
                                    <button id="sessionSet" class="primary-btn">Oturum Aç</button>
                                    <button id="sessionClear" class="danger-btn" type="button">Oturumu Kapat</button>
                                </div>
                                <div id="sessionInfo" class="session-info inactive">
                                    Henüz oturum açılmadı
                                </div>
                                <div class="helper">Oturum açtıktan sonra soru sormanıza gerek kalmaz her istekte token girmezsiniz.</div>
                            </div>

                            <div id="tab-upload" class="tab-content">
                                <label for="docTitle">Doküman Başlığı</label>
                                <input id="docTitle" placeholder="Örn: Bilgisayar Mühendisliği Ders Kataloğu 2024" />
                                <label for="docFile">Doküman Dosyası</label>
                                <input type="file" id="docFile" accept=".txt,.md,.pdf" />
                                <label for="docCategory">Kategori</label>
                                <input id="docCategory" placeholder="Örn: akademik_politika, ders_bilgisi, yönetmelik" />
                                <div class="button-row">
                                    <button id="upload" class="primary-btn">Dokümanı Yükle</button>
                                </div>
                                <div class="helper">Desteklenen biçimler: .txt, .md, .pdf • Maksimum boyut: 10MB • Token gerekli (oturum tokeni de kabul edilir)</div>
                            </div>
                        </div>
                    </div>

                    <aside class="result-card">
                        <div class="panel-header">
                            <div>
                                <h3>Sonuç</h3>
                                <p class="muted">Cevap, rota ve kaynak bilgileri burada görünür.</p>
                            </div>
                            <span id="routeBadge" class="route-badge route-rag">Hazır</span>
                        </div>

                        <div id="answer" class="result-answer">Hazır. Bir soru sorabilir veya yeni bir doküman yükleyebilirsiniz.</div>

                        <div class="status">
                            <span class="status-dot"></span>
                            <span id="statusText">Sistem beklemede</span>
                        </div>

                        <div class="result-section">
                            <div class="meta-list" id="metaList"></div>
                        </div>

                        <div class="result-section">
                            <h3>Kaynaklar</h3>
                            <div class="source-list" id="sourceList">
                                <span class="source-item">Henüz kaynak yok</span>
                            </div>
                        </div>

                        <details>
                            <summary>Ham JSON çıktısı</summary>
                            <pre id="rawOutput">{
  "status": "ready"
}</pre>
                        </details>
                    </aside>
                </section>
            </div>
            <script>
                const byId = (id) => document.getElementById(id);
                const btn = byId('send');
                const clearBtn = byId('clear');
                const uploadBtn = byId('upload');
                const searchBtn = byId('searchBtn');
                const sessionSetBtn = byId('sessionSet');
                const sessionClearBtn = byId('sessionClear');
                const answerEl = byId('answer');
                const rawOutput = byId('rawOutput');
                const statusText = byId('statusText');
                const routeBadge = byId('routeBadge');
                const metaList = byId('metaList');
                const sourceList = byId('sourceList');
                const sessionInfo = byId('sessionInfo');
                const searchResults = byId('searchResults');

                // ---- Tab system ----
                document.querySelectorAll('.tab-btn').forEach((tab) => {
                    tab.addEventListener('click', () => {
                        document.querySelectorAll('.tab-btn').forEach((t) => t.classList.remove('active'));
                        document.querySelectorAll('.tab-content').forEach((c) => c.classList.remove('active'));
                        tab.classList.add('active');
                        byId(tab.dataset.tab).classList.add('active');
                    });
                });

                // ---- Quick token chips ----
                document.querySelectorAll('.token-chip[data-token]').forEach((chip) => {
                    chip.addEventListener('click', () => {
                        const token = chip.dataset.token;
                        byId('sessionToken').value = token;
                        byId('token').value = token;
                        // Auto-set session
                        setSession(token);
                    });
                });

                // ---- Helpers ----
                function setBusy(message) {
                    statusText.textContent = message;
                }

                function setRoute(route) {
                    const normalized = route || 'hazır';
                    routeBadge.textContent = normalized.toUpperCase();
                    routeBadge.className = 'route-badge';
                    if (normalized === 'rag') routeBadge.classList.add('route-rag');
                    else if (normalized === 'mcp') routeBadge.classList.add('route-mcp');
                    else if (normalized === 'hybrid') routeBadge.classList.add('route-hybrid');
                    else routeBadge.classList.add('route-rag');
                }

                function renderMeta(payload) {
                    const chips = [];
                    if (payload.user) chips.push(`Kullanıcı: ${payload.user}`);
                    if (payload.role) chips.push(`Rol: ${payload.role}`);
                    if (payload.db_result?.table) chips.push(`Tablo: ${payload.db_result.table}`);
                    if (payload.db_result?.count !== undefined) chips.push(`Kayıt: ${payload.db_result.count}`);

                    metaList.innerHTML = chips.length
                        ? chips.map((item) => `<span class="meta-chip">${item}</span>`).join('')
                        : '<span class="meta-chip">Meta bilgi yok</span>';
                }

                function renderSources(payload) {
                    const citations = payload.rag_citations || [];
                    if (citations.length) {
                        sourceList.innerHTML = citations.map((item) => `
                            <div class="source-card" id="citation-${item.index}">
                                <div class="source-heading">
                                    <span class="source-index">[${item.index}]</span>
                                    <strong>${escapeHtml(item.title)}</strong>
                                </div>
                                <div class="source-meta">Benzerlik: ${escapeHtml(item.similarity)}</div>
                                <div class="source-snippet">${escapeHtml(item.snippet)}</div>
                            </div>
                        `).join('');
                        return;
                    }

                    const sources = payload.rag_sources || [];
                    sourceList.innerHTML = sources.length
                        ? sources.map((item) => `<span class="source-item">${item}</span>`).join('')
                        : '<span class="source-item">Kaynak kullanılmadı</span>';
                }

                function escapeHtml(text) {
                    return String(text ?? '')
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#39;');
                }

                function renderAnswer(payload) {
                    const answer = escapeHtml(payload.answer || payload.message || 'Yanıt alınamadı.');
                    const linked = answer.replace(/\\[(\\d+)\\]/g, (match, index) => {
                        if ((payload.rag_citations || []).some((item) => String(item.index) === index)) {
                            return `<a href="#citation-${index}" class="citation-link">[${index}]</a>`;
                        }
                        return match;
                    });
                    return linked.replace(/\\\\n/g, '<br />');
                }

                function renderResult(payload) {
                    answerEl.innerHTML = renderAnswer(payload);
                    rawOutput.textContent = JSON.stringify(payload, null, 2);
                    setRoute(payload.route);
                    renderMeta(payload);
                    renderSources(payload);
                }

                function renderError(message, raw = null) {
                    answerEl.textContent = message;
                    rawOutput.textContent = raw ? JSON.stringify(raw, null, 2) : JSON.stringify({ error: message }, null, 2);
                    setRoute('error');
                    metaList.innerHTML = '<span class="meta-chip">Hata</span>';
                    sourceList.innerHTML = '<span class="source-item">Kaynak yok</span>';
                }

                // ---- Session management ----
                async function setSession(token) {
                    sessionSetBtn.disabled = true;
                    try {
                        const res = await fetch('/api/session/token', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ token }),
                        });
                        const payload = await res.json();
                        if (res.ok) {
                            sessionInfo.className = 'session-info';
                            sessionInfo.innerHTML = `<strong>Oturum açık:</strong> ${escapeHtml(payload.user)} (${escapeHtml(payload.role)}) — ${escapeHtml(payload.masked_token)}`;
                            setBusy(`Oturum açıldı: ${payload.user}`);
                        } else {
                            sessionInfo.className = 'session-info inactive';
                            sessionInfo.textContent = payload.detail || 'Oturum açılamadı';
                        }
                    } catch (err) {
                        sessionInfo.className = 'session-info inactive';
                        sessionInfo.textContent = 'Hata: ' + err;
                    } finally {
                        sessionSetBtn.disabled = false;
                    }
                }

                async function checkSession() {
                    try {
                        const res = await fetch('/api/session/token');
                        const payload = await res.json();
                        if (payload.status === 'ok') {
                            sessionInfo.className = 'session-info';
                            sessionInfo.innerHTML = `<strong>Oturum açık:</strong> ${escapeHtml(payload.user)} (${escapeHtml(payload.role)}) — ${escapeHtml(payload.masked_token)}`;
                        } else {
                            sessionInfo.className = 'session-info inactive';
                            sessionInfo.textContent = 'Henüz oturum açılmadı';
                        }
                    } catch {
                        sessionInfo.className = 'session-info inactive';
                        sessionInfo.textContent = 'Sunucuya ulaşılamıyor';
                    }
                }

                sessionSetBtn.addEventListener('click', () => {
                    const token = byId('sessionToken').value.trim();
                    if (!token) { sessionInfo.textContent = 'Token girin'; return; }
                    setSession(token);
                });

                sessionClearBtn.addEventListener('click', async () => {
                    try {
                        await fetch('/api/session/token', { method: 'DELETE' });
                        sessionInfo.className = 'session-info inactive';
                        sessionInfo.textContent = 'Oturum kapatıldı';
                        setBusy('Oturum kapatıldı');
                    } catch (err) {
                        sessionInfo.textContent = 'Hata: ' + err;
                    }
                });

                // Check session on load
                checkSession();

                // ---- Example questions ----
                document.querySelectorAll('.example-chip').forEach((chip) => {
                    chip.addEventListener('click', () => {
                        byId('question').value = chip.dataset.question || '';
                        // Switch to ask tab
                        document.querySelector('.tab-btn[data-tab="tab-ask"]').click();
                        byId('question').focus();
                    });
                });

                // ---- Ask question (token optional) ----
                btn.addEventListener('click', async () => {
                    const token = byId('token').value.trim() || null;
                    const question = byId('question').value.trim();
                    if (!question) {
                        renderError('Soru alanı zorunludur.');
                        return;
                    }
                    btn.disabled = true;
                    setBusy('Soru işleniyor...');
                    answerEl.textContent = 'Cevap hazırlanıyor...';
                    try {
                        const body = { question };
                        if (token) body.token = token;
                        const res = await fetch('/api/ask', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body),
                        });
                        const payload = await res.json();
                        if (!res.ok) {
                            renderError(payload.detail || 'Sorgu başarısız oldu.', payload);
                        } else {
                            renderResult(payload);
                            setBusy('Sorgu tamamlandı');
                        }
                    } catch (err) {
                        renderError('İstek sırasında hata oluştu: ' + err);
                    } finally {
                        btn.disabled = false;
                    }
                });

                clearBtn.addEventListener('click', () => {
                    byId('question').value = '';
                    answerEl.textContent = 'Hazır. Bir soru sorabilir veya yeni bir doküman yükleyebilirsiniz.';
                    rawOutput.textContent = JSON.stringify({ status: 'ready' }, null, 2);
                    metaList.innerHTML = '<span class="meta-chip">Temizlendi</span>';
                    sourceList.innerHTML = '<span class="source-item">Kaynak yok</span>';
                    setRoute('hazır');
                    setBusy('Sistem beklemede');
                });

                // ---- Knowledge search ----
                searchBtn.addEventListener('click', async () => {
                    const query = byId('searchQuery').value.trim();
                    const topK = parseInt(byId('searchTopK').value) || 3;
                    if (!query) {
                        searchResults.innerHTML = '<div class="search-card"><div class="search-card-snippet">Arama sorgusu girin.</div></div>';
                        return;
                    }
                    searchBtn.disabled = true;
                    searchResults.innerHTML = '<div class="search-card"><div class="search-card-snippet">Aranıyor...</div></div>';
                    try {
                        const res = await fetch('/api/search-knowledge', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ query, top_k: topK }),
                        });
                        const payload = await res.json();
                        if (!res.ok) {
                            searchResults.innerHTML = `<div class="search-card"><div class="search-card-snippet">Hata: ${escapeHtml(payload.detail)}</div></div>`;
                        } else {
                            const results = payload.results || [];
                            if (!results.length) {
                                searchResults.innerHTML = '<div class="search-card"><div class="search-card-snippet">Sonuç bulunamadı.</div></div>';
                            } else {
                                searchResults.innerHTML = results.map((item, i) => `
                                    <div class="search-card">
                                        <div class="search-card-title">${i + 1}. ${escapeHtml(item.document_title)}</div>
                                        <div class="search-card-meta">Benzerlik: ${escapeHtml(String(item.similarity))}</div>
                                        <div class="search-card-snippet">${escapeHtml(item.snippet)}</div>
                                    </div>
                                `).join('');
                            }
                            // Also show in raw output
                            rawOutput.textContent = JSON.stringify(payload, null, 2);
                            setBusy(`${payload.count} sonuç bulundu`);
                        }
                    } catch (err) {
                        searchResults.innerHTML = `<div class="search-card"><div class="search-card-snippet">Hata: ${err}</div></div>`;
                    } finally {
                        searchBtn.disabled = false;
                    }
                });

                // ---- Upload document (token optional) ----
                uploadBtn.addEventListener('click', async () => {
                    const title = byId('docTitle').value.trim();
                    const file = byId('docFile').files[0];
                    const category = byId('docCategory').value.trim() || null;

                    if (!title || !file) {
                        renderError('Doküman başlığı ve dosya alanı zorunludur.');
                        return;
                    }

                    uploadBtn.disabled = true;
                    setBusy('Doküman yükleniyor...');
                    answerEl.textContent = 'Doküman işleniyor...';

                    try {
                        const formData = new FormData();
                        formData.append('title', title);
                        formData.append('file', file);
                        if (category) formData.append('category', category);

                        const res = await fetch('/api/upload', {
                            method: 'POST',
                            body: formData,
                        });
                        const payload = await res.json();
                        if (!res.ok) {
                            renderError(payload.detail || 'Doküman yükleme başarısız oldu.', payload);
                        } else {
                            renderResult(payload);
                            setBusy('Doküman yüklendi ve indekslendi');
                        }
                    } catch (err) {
                        renderError('Yükleme sırasında hata oluştu: ' + err);
                    } finally {
                        uploadBtn.disabled = false;
                    }
                });
            </script>
        </body>
        </html>
        """
    )


def create_fastapi_app() -> FastAPI:
    config = AppConfig.from_env()
    server: MCPServer | None = None

    def get_server() -> MCPServer:
        nonlocal server
        if server is None:
            server = build_server(config)
        return server

    app = FastAPI(title="RBAC RAG Web")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(content=_build_html())

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    def _resolve_token(explicit_token: str | None) -> str:
        """Resolve token: explicit > session > error."""
        final = explicit_token or get_server()._session_manager.get_token()
        if not final:
            raise HTTPException(
                status_code=401,
                detail="No token provided and no session token set. Use POST /api/session/token first.",
            )
        return final

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    @app.post("/api/session/token")
    def set_session_token(body: SetTokenRequest) -> dict:
        """Set authentication token for the server-side session."""
        try:
            return get_server().set_user_token(body.token, body.session_id)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/session/token")
    def get_session_token(session_id: str = "default") -> dict:
        """Get the currently set session token (masked)."""
        try:
            return get_server().get_current_token(session_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/api/session/token")
    def clear_session_token(session_id: str = "default") -> dict:
        """Clear the session token."""
        try:
            return get_server().clear_token(session_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Knowledge base search (no auth required)
    # ------------------------------------------------------------------

    @app.post("/api/search-knowledge")
    def search_knowledge(body: SearchKnowledgeRequest) -> dict:
        """Search the open knowledge base. No authentication required."""
        try:
            return get_server().search_knowledge(body.query, body.top_k)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Core endpoints (token optional — session fallback)
    # ------------------------------------------------------------------

    @app.post("/api/ask")
    def ask(body: AskRequest) -> dict:
        try:
            token = _resolve_token(body.token)
            return get_server().ask_question(token, body.question)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - surfaced to caller
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/route")
    def route(body: AskRequest) -> dict:
        try:
            token = _resolve_token(body.token)
            return get_server().route_question(body.question, token)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - surfaced to caller
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/query-intent")
    def query_intent(body: QueryIntentRequest) -> dict:
        try:
            token = _resolve_token(body.token)
            return get_server().query_records_intent(
                body.table,
                operation=body.operation,
                filters=body.filters,
                token=token,
            )
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - surfaced to caller
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/source/{chunk_id}")
    def fetch_source(chunk_id: int, token: str | None = None) -> dict:
        try:
            final_token = _resolve_token(token)
            return get_server().fetch_source(final_token, chunk_id)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - surfaced to caller
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/upload")
    async def upload_document(
        title: str = Form(...),
        file: UploadFile = File(...),
        token: str = Form(None),
        category: str = Form(None),
    ) -> dict:
        # File size limit (10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        ALLOWED_EXTENSIONS = {'.txt', '.md', '.pdf'}

        try:
            # Validate filename
            if not file.filename:
                raise HTTPException(status_code=400, detail="No filename provided")

            # Sanitize filename and check extension
            filename = re.sub(r'[^\w\s\-\.]', '', file.filename)
            ext = Path(filename).suffix.lower()

            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
                )

            # Read file content
            content = await file.read()

            # Check file size
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024):.1f}MB"
                )

            # Check if file is empty
            if not content:
                raise HTTPException(status_code=400, detail="Empty file uploaded")

            # Extract text based on file type
            if ext == '.pdf':
                if pypdf is None:
                    raise HTTPException(
                        status_code=500,
                        detail="PDF support not available. Install pypdf package."
                    )
                try:
                    pdf_reader = pypdf.PdfReader(io.BytesIO(content))
                    content_str = "\n\n".join(
                        page.extract_text() for page in pdf_reader.pages if page.extract_text()
                    )
                    if not content_str.strip():
                        raise HTTPException(status_code=400, detail="PDF contains no extractable text")
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
            else:
                # Text files (.txt, .md)
                try:
                    content_str = content.decode("utf-8")
                except UnicodeDecodeError:
                    raise HTTPException(
                        status_code=400,
                        detail="File encoding error. Please ensure file is UTF-8 encoded."
                    )

            # Ingest document
            final_token = _resolve_token(token)
            result = get_server().ingest_document(final_token, title, content_str, category)
            return {
                "status": "success",
                "message": f"Document '{title}' uploaded and indexed",
                "filename": filename,
                **result,
            }
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/ingest")
    def ingest_text(body: IngestRequest) -> dict:
        try:
            token = _resolve_token(body.token)
            result = get_server().ingest_document(token, body.title, body.content, body.category)
            return {
                "status": "success",
                "message": f"Document '{body.title}' ingested",
                **result,
            }
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/documents")
    def list_documents(token: str | None = None) -> dict:
        """List all documents uploaded by the authenticated user."""
        try:
            final_token = _resolve_token(token)
            return get_server().list_user_documents(final_token)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/api/documents/{doc_id}")
    def delete_document(doc_id: int, token: str | None = None) -> dict:
        """Delete a document uploaded by the authenticated user."""
        try:
            final_token = _resolve_token(token)
            return get_server().delete_user_document(final_token, doc_id)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_fastapi_app()
