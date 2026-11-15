-- ================================================================
-- MIGRACIÓN 002: Seguridad (RLS) y control de acceso
-- Ejecutar en: Supabase Dashboard > SQL Editor (después de la 001)
-- ================================================================

-- ----------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------
-- Sin RLS, cualquiera con la clave pública "anon" del proyecto puede leer
-- y escribir estas tablas vía la REST API. Al activarlo sin políticas,
-- solo la service_role key (la que usa el bot) puede acceder.
ALTER TABLE socios              ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversaciones      ENABLE ROW LEVEL SECURITY;
ALTER TABLE mensajes            ENABLE ROW LEVEL SECURITY;
ALTER TABLE updates_procesados  ENABLE ROW LEVEL SECURITY;

-- La función de limpieza solo debe poder ejecutarla el backend.
REVOKE EXECUTE ON FUNCTION limpiar_updates_viejos() FROM PUBLIC, anon, authenticated;

-- ----------------------------------------------------------------
-- Control de acceso
-- ----------------------------------------------------------------
-- Los socios nuevos quedan pendientes de aprobación por defecto.
-- (El bot igual setea el valor explícitamente; esto cubre inserts manuales.)
ALTER TABLE socios ALTER COLUMN activo SET DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_socios_pendientes
    ON socios(creado_en DESC) WHERE activo = false;

DO $$
BEGIN
    RAISE NOTICE '✅ Migración 002 completada: RLS activo y acceso por aprobación';
END $$;
