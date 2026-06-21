-- ============================================================================
-- ESQUEMA DO BANCO DA DOROTEIA  (item 4 do briefing)
-- ----------------------------------------------------------------------------
-- Como usar: copie este arquivo INTEIRO e cole no "SQL Editor" do Supabase,
-- depois clique em "Run". Ele cria as 4 tabelas de uma vez.
-- "SQL" é só a linguagem que usamos pra conversar com o banco de dados.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- TABELA members  →  as PESSOAS que usam a Doroteia
-- ----------------------------------------------------------------------------
create table if not exists members (
    id          uuid primary key default gen_random_uuid(), -- código único de cada membro (gerado sozinho)
    wa_id       text unique not null,                       -- id do WhatsApp da pessoa (identifica o número)
    nome_perfil text,                                       -- nome que aparece no perfil do WhatsApp
    consent     boolean not null default false,             -- deu o "ok" de privacidade? (tela 7.1) - começa como "não"
    consent_at  timestamptz,                                -- data/hora em que deu o ok
    invited_by  uuid references members(id) on delete set null, -- qual outro membro convidou essa pessoa
    estado      text,                                       -- em que ponto da conversa a pessoa esta (ex: "recomendando")
    invite_code text unique,                                -- codigo unico do link de convite dessa pessoa
    created_at  timestamptz not null default now()          -- quando essa pessoa entrou
);


-- ----------------------------------------------------------------------------
-- TABELA providers  →  os PRESTADORES de serviço indicados
-- ----------------------------------------------------------------------------
create table if not exists providers (
    id         uuid primary key default gen_random_uuid(),
    nome       text not null,                  -- nome do prestador
    telefone   text not null,                  -- telefone em formato E.164 (ESTE é o dado que se entrega a quem pede)
    servico    text not null,                  -- ex.: "encanador"
    bairro     text not null,                  -- ex.: "Perdizes"
    created_at timestamptz not null default now()
);


-- ----------------------------------------------------------------------------
-- TABELA recommendations  →  as INDICAÇÕES (quem indicou qual prestador)
-- ----------------------------------------------------------------------------
create table if not exists recommendations (
    id          uuid primary key default gen_random_uuid(),
    member_id   uuid not null references members(id)   on delete cascade, -- quem fez a indicação
    provider_id uuid not null references providers(id) on delete cascade, -- o prestador indicado
    servico     text not null,
    bairro      text not null,
    nota        text,                            -- comentário opcional ("muito pontual", etc.)
    created_at  timestamptz not null default now()
);


-- ----------------------------------------------------------------------------
-- TABELA edges  →  o GRAFO de quem-conhece-quem, guardado em HASH (item 5)
-- IMPORTANTE: aqui NÃO guardamos número nem nome do contato. Só um código
-- irreversível (o "contact_hash"). O cálculo desse hash entra na Camada 4.
-- ----------------------------------------------------------------------------
create table if not exists edges (
    id           uuid primary key default gen_random_uuid(),
    member_id    uuid not null references members(id) on delete cascade, -- o membro que compartilhou o contato
    contact_hash text not null,                  -- HMAC-SHA256 do número (não dá pra reverter pro número)
    created_at   timestamptz not null default now(),
    unique (member_id, contact_hash)             -- impede guardar o mesmo contato repetido pro mesmo membro
);


-- ----------------------------------------------------------------------------
-- ÍNDICES  →  deixam as buscas mais rápidas (como o índice no fim de um livro)
-- ----------------------------------------------------------------------------
-- Busca de indicações por serviço + bairro (o que o pedidor procura):
create index if not exists idx_recommendations_servico_bairro on recommendations (servico, bairro);

-- Busca no grafo pelo hash do contato (usada no "casamento" do item 5):
create index if not exists idx_edges_contact_hash on edges (contact_hash);


-- ----------------------------------------------------------------------------
-- TABELA searches  ->  METRICAS de demanda (sem dado pessoal)
-- Anota cada pedido de servico: o que, o bairro e a cor da resposta.
-- ----------------------------------------------------------------------------
create table if not exists searches (
    id         uuid primary key default gen_random_uuid(),
    servico    text,
    bairro     text,
    resultado  text,   -- 'verde' | 'amarelo' | 'vermelho'
    created_at timestamptz not null default now()
);


-- ----------------------------------------------------------------------------
-- TABELA pending_invites  ->  convites por numero, aguardando a pessoa entrar
-- Guarda so o HASH do numero convidado (nunca o numero cru). Quando a pessoa
-- entra, ligamos ela ao convidante (invited_by) e apagamos o convite.
-- ----------------------------------------------------------------------------
create table if not exists pending_invites (
    id           uuid primary key default gen_random_uuid(),
    inviter_id   uuid not null references members(id) on delete cascade,
    contact_hash text not null,
    created_at   timestamptz not null default now(),
    unique (inviter_id, contact_hash)
);


-- ----------------------------------------------------------------------------
-- SEGURANCA: Row Level Security (RLS)
-- Tranca todas as tabelas: por padrao, ninguem de FORA le/escreve. O nosso
-- servidor usa a chave service_role, que passa por cima do RLS - entao o bot
-- continua funcionando normalmente. E so protecao extra contra vazamento da
-- chave publica.
-- ----------------------------------------------------------------------------
alter table members         enable row level security;
alter table providers       enable row level security;
alter table recommendations enable row level security;
alter table edges           enable row level security;
alter table searches        enable row level security;
alter table pending_invites enable row level security;
