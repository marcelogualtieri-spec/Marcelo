-- ============================================================================
-- MIGRAÇÃO v5 — follow-up proativo de avaliação
-- ----------------------------------------------------------------------------
-- Adiciona a coluna follow_up_at em indicacoes_recebidas para registrar
-- quando a mensagem de follow-up foi enviada. Sem ela, o cron não saberia
-- quais indicações já receberam mensagem e enviaria duplicatas.
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table indicacoes_recebidas
    add column if not exists follow_up_at timestamptz;
