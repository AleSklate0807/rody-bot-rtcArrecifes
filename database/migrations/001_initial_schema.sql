-- ================================================================
-- MIGRACIÓN 001: Esquema inicial — Fase 1 MVP
-- Ejecutar en: Supabase Dashboard > SQL Editor
-- ================================================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- MÓDULO: Identidad de socios
-- ================================================================
CREATE TABLE IF NOT EXISTS socios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id     BIGINT UNIQUE NOT NULL,
    username        TEXT,                       -- @username (puede cambiar)
    nombre_display  TEXT,                       -- nombre preferido
    es_admin        BOOLEAN NOT NULL DEFAULT false,
    activo          BOOLEAN NOT NULL DEFAULT true,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_acceso   TIMESTAMPTZ
);

COMMENT ON TABLE socios IS 'Socios del club identificados por su Telegram ID';
COMMENT ON COLUMN socios.telegram_id IS 'ID único de Telegram, nunca cambia';
COMMENT ON COLUMN socios.username IS '@username de Telegram, puede cambiar';

-- ================================================================
-- MÓDULO: Memoria conversacional
-- ================================================================
CREATE TABLE IF NOT EXISTS conversaciones (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    socio_id        UUID NOT NULL REFERENCES socios(id) ON DELETE CASCADE,
    iniciada_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    cerrada_en      TIMESTAMPTZ,
    resumen         TEXT,                       -- resumen comprimido por Gemini
    total_turnos    INT NOT NULL DEFAULT 0,
    tokens_usados   INT NOT NULL DEFAULT 0
);

COMMENT ON TABLE conversaciones IS 'Sesiones de conversación por socio';
COMMENT ON COLUMN conversaciones.resumen IS 'Resumen generado por Gemini cuando la conversación supera el límite de turnos';

CREATE TABLE IF NOT EXISTS mensajes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversacion_id UUID NOT NULL REFERENCES conversaciones(id) ON DELETE CASCADE,
    socio_id        UUID NOT NULL REFERENCES socios(id) ON DELETE CASCADE,
    rol             TEXT NOT NULL CHECK (rol IN ('user', 'assistant', 'system')),
    contenido       TEXT NOT NULL,
    tokens_entrada  INT,
    tokens_salida   INT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE mensajes IS 'Mensajes individuales dentro de cada conversación';
COMMENT ON COLUMN mensajes.rol IS 'Rol del mensaje: user (socio), assistant (bot), system (instrucciones)';

-- Índices para recuperación eficiente
CREATE INDEX IF NOT EXISTS idx_mensajes_conv_fecha
    ON mensajes(conversacion_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_conversaciones_socio
    ON conversaciones(socio_id, iniciada_en DESC);

-- ================================================================
-- MÓDULO: Idempotencia de updates de Telegram
-- ================================================================
CREATE TABLE IF NOT EXISTS updates_procesados (
    update_id       BIGINT PRIMARY KEY,
    procesado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE updates_procesados IS 'Registro de updates de Telegram ya procesados para evitar duplicados';

-- Limpiar updates viejos automáticamente (mantener solo últimas 24hs)
-- Esta función se puede invocar periódicamente si se desea
CREATE OR REPLACE FUNCTION limpiar_updates_viejos()
RETURNS void AS $$
BEGIN
    DELETE FROM updates_procesados
    WHERE procesado_en < now() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- Verificación
-- ================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ Migración 001 completada:';
    RAISE NOTICE '   - Tabla socios creada';
    RAISE NOTICE '   - Tabla conversaciones creada';
    RAISE NOTICE '   - Tabla mensajes creada';
    RAISE NOTICE '   - Tabla updates_procesados creada';
    RAISE NOTICE '   - Índices creados';
END $$;

