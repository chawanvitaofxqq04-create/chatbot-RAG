-- This file is a reference copy of the schema.
-- The actual initialization is done by infra/init_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS doc_chunks (
    chunk_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id      TEXT NOT NULL,
    chunk_index INT NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding   vector(3072) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding
    ON doc_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS customers (
    customer_id   SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT,
    region        TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    product_id    SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT,
    price         NUMERIC(10,2) NOT NULL,
    stock         INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    order_id      SERIAL PRIMARY KEY,
    customer_id   INT REFERENCES customers(customer_id),
    order_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    total_amount  NUMERIC(12,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id       SERIAL PRIMARY KEY,
    order_id      INT REFERENCES orders(order_id),
    product_id    INT REFERENCES products(product_id),
    quantity      INT NOT NULL,
    unit_price    NUMERIC(10,2) NOT NULL,
    line_total    NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

-- ==========================================
-- ตารางใหม่: สำหรับเก็บคำถามของผู้ใช้งาน (ตารางโล่งๆ)
-- ==========================================
CREATE TABLE IF NOT EXISTS user_questions_log (
    log_id        SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);