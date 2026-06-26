-- ============================================================================
-- MIGRAÇÃO v3 — memória de conversa para a Doroteia conversacional (IA)
-- ----------------------------------------------------------------------------
-- Execute no SQL Editor do Supabase ANTES do deploy do novo código.
-- Seguro rodar mais de uma vez.
-- ============================================================================

-- members: guarda as últimas trocas de mensagem (só texto), pra IA ter memória
-- da conversa. Nada de números de telefone de contatos entra aqui.
alter table members add column if not exists historico jsonb not null default '[]'::jsonb;
