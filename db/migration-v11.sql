-- ============================================================================
-- MIGRAÇÃO v11 — canal de ajuda/suporte (encaminhar problema para a equipe)
-- ----------------------------------------------------------------------------
-- Quando a pessoa pede AJUDA e relata um problema, a Doroteia registra aqui
-- (e avisa a equipe). Assim nada se perde, mesmo fora da janela de mensagem.
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

create table if not exists suporte (
    id         uuid primary key default gen_random_uuid(),
    member_id  uuid references members(id) on delete set null,
    wa_id      text,
    nome       text,
    mensagem   text not null,
    status     text not null default 'aberto',   -- 'aberto' | 'resolvido'
    created_at timestamptz not null default now()
);

create index if not exists idx_suporte_status on suporte (status, created_at desc);
