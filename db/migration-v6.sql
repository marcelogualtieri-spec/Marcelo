-- ============================================================================
-- MIGRAÇÃO v6 — histórico de buscas por membro
-- ----------------------------------------------------------------------------
-- Adiciona member_id em searches para permitir "ver minhas buscas recentes".
-- O índice acelera a consulta do painel do usuário.
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table searches
    add column if not exists member_id uuid references members(id) on delete set null;

create index if not exists idx_searches_member
    on searches (member_id, created_at desc);
