-- ============================================================================
-- MIGRAÇÃO v4 — avaliação das indicações (qualifica depois do uso)
-- ----------------------------------------------------------------------------
-- Permite que quem RECEBEU uma indicação avalie de 1 a 5 estrelas depois de
-- usar o serviço. A nota faz o prestador ganhar relevância nas buscas futuras.
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

-- providers: agregados de avaliação (denormalizados para ranquear rápido).
alter table providers add column if not exists nota_media     numeric not null default 0;
alter table providers add column if not exists qtd_avaliacoes integer not null default 0;

-- ----------------------------------------------------------------------------
-- TABELA avaliacoes  →  a NOTA que cada pessoa deu a um prestador (1 a 5)
-- Uma avaliação por pessoa por prestador (ela pode reavaliar = atualiza).
-- ----------------------------------------------------------------------------
create table if not exists avaliacoes (
    id          uuid primary key default gen_random_uuid(),
    member_id   uuid not null references members(id)   on delete cascade, -- quem avaliou
    provider_id uuid not null references providers(id) on delete cascade, -- prestador avaliado
    nota        integer not null check (nota between 1 and 5),
    comentario  text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    unique (member_id, provider_id)
);
create index if not exists idx_avaliacoes_provider on avaliacoes (provider_id);

-- ----------------------------------------------------------------------------
-- TABELA indicacoes_recebidas  →  prestadores MOSTRADOS a uma pessoa numa busca
-- É a base do follow-up: a Doroteia volta e pergunta "usou? como foi?".
-- status: 'pendente' (ainda não avaliou) | 'avaliada' | 'dispensada' (não usou)
-- ----------------------------------------------------------------------------
create table if not exists indicacoes_recebidas (
    id          uuid primary key default gen_random_uuid(),
    member_id   uuid not null references members(id)   on delete cascade,
    provider_id uuid not null references providers(id) on delete cascade,
    servico     text,
    bairro      text,
    cidade      text,
    status      text not null default 'pendente',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    unique (member_id, provider_id)
);
create index if not exists idx_indic_receb_member_status
    on indicacoes_recebidas (member_id, status);
