-- ================================================================
-- MIGRACIÓN 003: Documentación institucional (RAG con pgvector)
-- Ejecutar en: Supabase Dashboard > SQL Editor (después de la 002)
-- ================================================================

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- ----------------------------------------------------------------
-- Documentos cargados (un registro por PDF)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documentos (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo            TEXT NOT NULL,                -- se muestra como fuente en las respuestas
    archivo           TEXT UNIQUE NOT NULL,         -- nombre del archivo PDF original
    hash              TEXT NOT NULL,                -- SHA-256 del PDF, para detectar cambios
    paginas           INT,
    total_fragmentos  INT NOT NULL DEFAULT 0,
    cargado_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE documentos IS 'Documentos institucionales disponibles para que Rody consulte';

-- ----------------------------------------------------------------
-- Fragmentos con su embedding (gemini-embedding-001, 768 dimensiones)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documento_fragmentos (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    documento_id  UUID NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    orden         INT NOT NULL,
    pagina        INT,
    contenido     TEXT NOT NULL,
    embedding     extensions.vector(768) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fragmentos_embedding
    ON documento_fragmentos USING hnsw (embedding extensions.vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_fragmentos_documento
    ON documento_fragmentos(documento_id, orden);

-- Solo el backend (service role) accede a estas tablas
ALTER TABLE documentos            ENABLE ROW LEVEL SECURITY;
ALTER TABLE documento_fragmentos  ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------
-- Búsqueda semántica: fragmentos más parecidos a la consulta
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_fragmentos(
    query_embedding  extensions.vector(768),
    match_count      INT DEFAULT 5,
    min_similarity   FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    id            UUID,
    documento_id  UUID,
    titulo        TEXT,
    pagina        INT,
    contenido     TEXT,
    similitud     FLOAT
)
LANGUAGE sql STABLE
SET search_path = public, extensions
AS $$
    SELECT f.id, f.documento_id, d.titulo, f.pagina, f.contenido,
           1 - (f.embedding <=> query_embedding) AS similitud
    FROM documento_fragmentos f
    JOIN documentos d ON d.id = f.documento_id
    WHERE 1 - (f.embedding <=> query_embedding) >= min_similarity
    ORDER BY f.embedding <=> query_embedding
    LIMIT match_count;
$$;

REVOKE EXECUTE ON FUNCTION match_fragmentos(extensions.vector, INT, FLOAT)
    FROM PUBLIC, anon, authenticated;

DO $$
BEGIN
    RAISE NOTICE '✅ Migración 003 completada: tablas de documentos y búsqueda semántica';
END $$;
