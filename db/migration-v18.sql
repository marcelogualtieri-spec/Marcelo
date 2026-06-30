-- ============================================================================
-- MIGRAÇÃO v18 — ligar a indicação a QUEM indicou (para "Indicações que fiz")
-- ----------------------------------------------------------------------------
-- Quando um cliente indica um profissional, guardamos quem indicou direto no
-- registro do profissional. Assim a pessoa consegue ver, em "Indicações que fiz",
-- os profissionais que ela indicou e que ainda estão pendentes de entrar/confirmar.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table providers add column if not exists indicado_por uuid references members(id) on delete set null;
create index if not exists idx_providers_indicado_por on providers (indicado_por);
