-- ============================================================================
-- MIGRAÇÃO v9 — comunidades (etiquetar membros por grupo de WhatsApp)
-- ----------------------------------------------------------------------------
-- Cada comunidade representa um grupo real (escola, prédio, bairro). Quem entra
-- pelo link exclusivo da comunidade é vinculado a ela em comunidade_membros.
-- A Doroteia NUNCA lê membros de grupo — a barreira de entrada é o próprio link,
-- que só circula dentro do grupo. 100% legal/LGPD.
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

create table if not exists comunidades (
    id          uuid primary key default gen_random_uuid(),
    slug        text not null unique,            -- usado no link, ex.: 'plato-perdizes'
    nome        text not null,                   -- exibição, ex.: 'Plato Perdizes'
    criada_por  uuid references members(id) on delete set null,
    created_at  timestamptz not null default now()
);

create table if not exists comunidade_membros (
    id            uuid primary key default gen_random_uuid(),
    comunidade_id uuid not null references comunidades(id) on delete cascade,
    member_id     uuid not null references members(id)     on delete cascade,
    created_at    timestamptz not null default now(),
    unique (comunidade_id, member_id)
);

create index if not exists idx_comunidade_membros_member
    on comunidade_membros (member_id);
create index if not exists idx_comunidade_membros_comunidade
    on comunidade_membros (comunidade_id);
