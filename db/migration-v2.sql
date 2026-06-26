-- ============================================================================
-- MIGRAÇÃO v2 — suporte a cidade + estado e coluna cidade em searches
-- ----------------------------------------------------------------------------
-- Execute no SQL Editor do Supabase ANTES de fazer o deploy do novo código.
-- É seguro rodar mais de uma vez (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
-- ============================================================================

-- providers: adiciona cidade e estado do prestador
alter table providers add column if not exists cidade text not null default '';
alter table providers add column if not exists estado text not null default '';

-- recommendations: replica cidade para facilitar buscas diretas
alter table recommendations add column if not exists cidade text not null default '';

-- searches: registra a cidade da busca nas métricas
alter table searches add column if not exists cidade text;

-- índice para busca por serviço + bairro + cidade
create index if not exists idx_recommendations_servico_cidade
    on recommendations (servico, cidade, bairro);
