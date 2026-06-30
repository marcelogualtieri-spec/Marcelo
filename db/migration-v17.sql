-- ============================================================================
-- MIGRAÇÃO v17 — bloquear pessoas (§7 / guardrails)
-- ----------------------------------------------------------------------------
-- A pessoa pode BLOQUEAR alguém a qualquer momento. Quem é bloqueado:
--   - não fica conectado (qualquer conexão entre os dois vira 'recusada');
--   - não aparece nas buscas um do outro (some dos resultados, nos dois sentidos);
--   - não consegue mandar pedido de conexão nem "perguntar a amigos" pra quem bloqueou.
-- O bloqueio é desfeito quando a pessoa desbloquear.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

create table if not exists bloqueios (
    id           uuid primary key default gen_random_uuid(),
    member_id    uuid not null references members(id) on delete cascade,   -- quem bloqueou
    bloqueado_id uuid not null references members(id) on delete cascade,    -- quem foi bloqueado
    created_at   timestamptz not null default now(),
    unique (member_id, bloqueado_id)
);

create index if not exists idx_bloqueios_member on bloqueios (member_id);
create index if not exists idx_bloqueios_alvo   on bloqueios (bloqueado_id);

alter table bloqueios enable row level security;
