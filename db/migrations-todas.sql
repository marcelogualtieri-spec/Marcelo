-- ============================================================================
-- MIGRAÇÕES v2 → v11 — cole TUDO de uma vez no SQL Editor do Supabase
-- ----------------------------------------------------------------------------
-- Execute ANTES do deploy do código novo. É seguro rodar mais de uma vez
-- (tudo usa IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
--
-- Resumo do que cria:
--   v2 -> cidade/estado nos prestadores e nas indicações (app nacional)
--   v3 -> memória de conversa da Doroteia (IA conversacional)
--   v4 -> avaliação das indicações (1 a 5 estrelas) + relevância na rede
--   v5 -> follow-up proativo (coluna follow_up_at em indicacoes_recebidas)
--   v6 -> histórico de buscas por membro (painel do usuário)
--   v7 -> alerta quando busca vermelha recebe nova indicação
--   v8 -> nudge pós-onboarding para adicionar contatos
--   v9 -> comunidades (etiquetar membros por grupo de WhatsApp)
--   v10 -> perfil de prestador de serviço (cadastro ativo + consentimento)
--   v11 -> canal de ajuda/suporte (encaminhar problema para a equipe)
-- ============================================================================


-- ============================================================================
-- v2 — suporte a cidade + estado
-- ============================================================================

-- providers: cidade e estado do prestador
alter table providers add column if not exists cidade text not null default '';
alter table providers add column if not exists estado text not null default '';

-- recommendations: replica cidade para facilitar buscas diretas
alter table recommendations add column if not exists cidade text not null default '';

-- searches: registra a cidade da busca nas métricas
alter table searches add column if not exists cidade text;

-- índice para busca por serviço + bairro + cidade
create index if not exists idx_recommendations_servico_cidade
    on recommendations (servico, cidade, bairro);


-- ============================================================================
-- v3 — memória de conversa (IA)
-- ============================================================================

-- members: guarda as últimas trocas de mensagem (só texto), pra IA ter memória.
alter table members add column if not exists historico jsonb not null default '[]'::jsonb;


-- ============================================================================
-- v4 — avaliação das indicações (qualifica depois do uso -> relevância)
-- ============================================================================

-- providers: agregados de avaliação (denormalizados para ranquear rápido).
alter table providers add column if not exists nota_media     numeric not null default 0;
alter table providers add column if not exists qtd_avaliacoes integer not null default 0;

-- avaliacoes: a NOTA (1 a 5) que cada pessoa deu a um prestador.
create table if not exists avaliacoes (
    id          uuid primary key default gen_random_uuid(),
    member_id   uuid not null references members(id)   on delete cascade,
    provider_id uuid not null references providers(id) on delete cascade,
    nota        integer not null check (nota between 1 and 5),
    comentario  text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    unique (member_id, provider_id)
);
create index if not exists idx_avaliacoes_provider on avaliacoes (provider_id);

-- indicacoes_recebidas: prestadores MOSTRADOS a uma pessoa (base do follow-up).
-- status: 'pendente' | 'avaliada' | 'dispensada'
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


-- ============================================================================
-- v5 — follow-up proativo de avaliação
-- ============================================================================

-- indicacoes_recebidas: registra quando o follow-up foi enviado (evita duplicatas).
alter table indicacoes_recebidas
    add column if not exists follow_up_at timestamptz;


-- ============================================================================
-- v6 — histórico de buscas por membro (painel do usuário)
-- ============================================================================

alter table searches
    add column if not exists member_id uuid references members(id) on delete set null;

create index if not exists idx_searches_member
    on searches (member_id, created_at desc);


-- ============================================================================
-- v7 — alerta de busca vermelha
-- ============================================================================

-- searches: rastreia quem ja foi notificado quando uma nova indicacao aparece
-- para um servico que buscou sem resultado (vermelho).
alter table searches
    add column if not exists alerta_enviado boolean not null default false;

create index if not exists idx_searches_alerta
    on searches (resultado, alerta_enviado, servico, cidade)
    where resultado = 'vermelho' and alerta_enviado = false;


-- ============================================================================
-- v8 — nudge pós-onboarding para adicionar contatos
-- ============================================================================

-- members: registra quando o lembrete de adicionar contatos foi enviado.
alter table members
    add column if not exists nudge_contatos_at timestamptz;


-- ============================================================================
-- v9 — comunidades (etiquetar membros por grupo de WhatsApp)
-- ============================================================================

-- Cada comunidade representa um grupo real (escola, prédio, bairro). Quem entra
-- pelo link exclusivo da comunidade é vinculado a ela em comunidade_membros.
-- A Doroteia NUNCA lê membros de grupo — a barreira é o próprio link, que só
-- circula dentro do grupo.

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


-- ============================================================================
-- v10 — perfil de prestador de serviço (cadastro ativo + consentimento)
-- ============================================================================

alter table providers add column if not exists member_id uuid references members(id) on delete set null;
alter table providers add column if not exists status text not null default 'convidado';
alter table providers add column if not exists regiao            text;
alter table providers add column if not exists diferenciais      text;
alter table providers add column if not exists descricao         text;
alter table providers add column if not exists termos_aceitos_em timestamptz;
alter table providers add column if not exists termos_versao     text;

create index if not exists idx_providers_member on providers (member_id);
create index if not exists idx_providers_status on providers (status);


-- ============================================================================
-- v11 — canal de ajuda/suporte (encaminhar problema para a equipe)
-- ============================================================================

create table if not exists suporte (
    id         uuid primary key default gen_random_uuid(),
    member_id  uuid references members(id) on delete set null,
    wa_id      text,
    nome       text,
    mensagem   text not null,
    status     text not null default 'aberto',
    created_at timestamptz not null default now()
);

create index if not exists idx_suporte_status on suporte (status, created_at desc);


-- ============================================================================
-- v12 — SAIR anonimiza as indicações (não apaga) — LGPD §4.5
-- ============================================================================
alter table recommendations alter column member_id drop not null;
alter table recommendations drop constraint if exists recommendations_member_id_fkey;
alter table recommendations
    add constraint recommendations_member_id_fkey
    foreign key (member_id) references members(id) on delete set null;


-- ============================================================================
-- v13 — conexões mútuas (os dois lados confirmam que se conhecem) §6/§7.5
-- ============================================================================
create table if not exists conexoes (
    id          uuid primary key default gen_random_uuid(),
    member_a    uuid references members(id) on delete cascade,
    member_b    uuid references members(id) on delete cascade,
    origem      text not null,
    provider_id uuid references providers(id) on delete set null,
    a_confirmou boolean not null default false,
    b_confirmou boolean not null default false,
    status      text not null default 'pendente',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz,
    unique (member_a, member_b)
);
create index if not exists idx_conexoes_a on conexoes (member_a, status);
create index if not exists idx_conexoes_b on conexoes (member_b, status);
alter table conexoes enable row level security;
