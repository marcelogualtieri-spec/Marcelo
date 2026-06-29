-- ============================================================================
-- MIGRAÇÃO v13 — conexões mútuas (os DOIS lados confirmam que se conhecem) §6/§7.5
-- ----------------------------------------------------------------------------
-- A confiança 🟢 só nasce quando AS DUAS pessoas confirmam que se conhecem.
-- Esta tabela guarda a conexão entre quem convidou/indicou (member_a) e quem
-- entrou (member_b), com a confirmação de cada lado. Quando os dois confirmam,
-- a conexão fica 'validada' e:
--   - origem 'cliente'      -> os dois passam a ser rede de confiança um do outro;
--   - origem 'profissional' -> a indicação (recomendação) de A sobre o profissional
--                              passa a valer (🟢, com o nome de A).
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

create table if not exists conexoes (
    id          uuid primary key default gen_random_uuid(),
    member_a    uuid references members(id) on delete cascade,   -- quem convidou/indicou
    member_b    uuid references members(id) on delete cascade,   -- quem entrou
    origem      text not null,                                   -- 'cliente' | 'profissional'
    provider_id uuid references providers(id) on delete set null,-- preenchido se origem profissional
    a_confirmou boolean not null default false,
    b_confirmou boolean not null default false,
    status      text not null default 'pendente',                -- 'pendente'|'validada'|'recusada'
    created_at  timestamptz not null default now(),
    updated_at  timestamptz,
    unique (member_a, member_b)
);

create index if not exists idx_conexoes_a on conexoes (member_a, status);
create index if not exists idx_conexoes_b on conexoes (member_b, status);

alter table conexoes enable row level security;
