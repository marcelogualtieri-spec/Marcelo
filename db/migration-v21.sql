-- ============================================================================
-- MIGRAÇÃO v21 — confirmação de indicação por LINK (página web, sem entrar no bot)
-- ----------------------------------------------------------------------------
-- Cada pessoa indicada (mas que ainda não confirmou a conexão) recebe um link
-- curto /confirmar/<token>. Ao responder Sim/Não numa página simples, gravamos
-- o status aqui. Quando dá para casar com um profissional já no banco (pelo hash
-- do telefone), a resposta "Sim" também VALIDA a conexão em `conexoes` (fonte de
-- verdade do grafo) — a indicação passa a valer (🟢) e o profissional vira ativo.
--
-- LGPD: guardamos o telefone só como HASH (nunca o número cru). O número cru só
-- trafega na resposta ao admin (para montar o link wa.me) — não é persistido.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

create table if not exists confirm_tokens (
    token          text primary key,                          -- secrets.token_urlsafe(6): curto e aleatório
    conexao_id     uuid references conexoes(id)  on delete set null,  -- conexão no grafo (quando existe)
    provider_id    uuid references providers(id) on delete set null,  -- profissional casado pelo hash (quando existe)
    nome_indicado  text,                                       -- nome de quem foi indicado (do lote)
    nome_indicador text,                                       -- nome de quem indicou (mostrado na página)
    telefone_hash  text,                                       -- LGPD: só o hash, nunca o número cru
    status         text not null default 'pendente',           -- pendente | confirmado | negado
    respondido_em  timestamptz,
    created_at     timestamptz not null default now()
);

create index if not exists idx_confirm_tokens_status on confirm_tokens (status);
create index if not exists idx_confirm_tokens_hash   on confirm_tokens (telefone_hash);

alter table confirm_tokens enable row level security;
