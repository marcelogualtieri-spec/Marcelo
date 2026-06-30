-- ============================================================================
-- MIGRAÇÃO v14 — perfil ATIVO e troca de perfil (TROCAR) — §5 / navegação
-- ----------------------------------------------------------------------------
-- Quem tem os dois perfis (Cliente + Profissional) navega num de cada vez. O
-- sistema LEMBRA qual está ativo entre conversas (padrão: cliente) e a pessoa
-- alterna com o comando TROCAR. Guardamos isso na própria pessoa.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

-- Qual perfil a pessoa está usando agora ('cliente' | 'profissional').
alter table members add column if not exists perfil_ativo text not null default 'cliente';

-- Já avisamos UMA vez que ela pode escrever TROCAR? (para não repetir sempre)
alter table members add column if not exists avisou_troca boolean not null default false;
