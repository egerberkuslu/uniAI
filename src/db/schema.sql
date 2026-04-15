-- Schema for rbac_rag_db
-- Requires pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================
-- PROTECTED TABLES (RBAC — role-gated)
-- =============================================

CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(20) NOT NULL UNIQUE,
    description TEXT,
    level       INT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(255) NOT NULL UNIQUE,
    role_id    INT REFERENCES roles(id),
    department VARCHAR(50) NOT NULL,
    token      VARCHAR(100) NOT NULL UNIQUE
);

-- =============================================
-- OPEN TABLES (RAG — no access control)
-- =============================================

CREATE TABLE IF NOT EXISTS kb_documents (
    id         SERIAL PRIMARY KEY,
    title      VARCHAR(255) NOT NULL,
    content    TEXT NOT NULL,
    category   VARCHAR(50),
    user_id    INT REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id          SERIAL PRIMARY KEY,
    document_id INT REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_text  TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding   VECTOR(384)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id       SERIAL PRIMARY KEY,
    role_id  INT REFERENCES roles(id),
    resource VARCHAR(50) NOT NULL,
    action   VARCHAR(20) NOT NULL,
    scope    VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id            SERIAL PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    amount        DECIMAL(10,2) NOT NULL,
    status        VARCHAR(20) NOT NULL,
    department    VARCHAR(50) NOT NULL,
    assigned_to   INT REFERENCES users(id),
    created_at    DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
    id            SERIAL PRIMARY KEY,
    order_id      INT REFERENCES orders(id),
    customer_name VARCHAR(100) NOT NULL,
    amount        DECIMAL(10,2) NOT NULL,
    reason        VARCHAR(255),
    department    VARCHAR(50) NOT NULL,
    processed_by  INT REFERENCES users(id),
    created_at    DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS ogrenci_bilgi_sistemi (
    id              SERIAL PRIMARY KEY,
    student_number  VARCHAR(20) NOT NULL UNIQUE,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    bolum           VARCHAR(50) NOT NULL,
    sinif           INT NOT NULL,
    gpa             DECIMAL(3,2) NOT NULL,
    advisor         VARCHAR(100) NOT NULL,
    advisor_id      INT REFERENCES users(id),
    last_updated_at TIMESTAMP DEFAULT NOW()
);
