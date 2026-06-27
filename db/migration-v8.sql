-- ============================================================================
-- MIGRAÇÃO v8 — nudge pós-onboarding para adicionar contatos
-- ----------------------------------------------------------------------------
-- Adiciona nudge_contatos_at em members para registrar quando o lembrete
-- foi enviado e evitar envios duplicados.
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table members
    add column if not exists nudge_contatos_at timestamptz;
