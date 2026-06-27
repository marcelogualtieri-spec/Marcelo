-- ============================================================================
-- MIGRAÇÃO v7 — alerta de busca vermelha
-- ----------------------------------------------------------------------------
-- Adiciona alerta_enviado em searches para rastrear quem ja foi notificado
-- quando uma nova indicacao aparece para um servico que buscou sem resultado.
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table searches
    add column if not exists alerta_enviado boolean not null default false;

create index if not exists idx_searches_alerta
    on searches (resultado, alerta_enviado, servico, cidade)
    where resultado = 'vermelho' and alerta_enviado = false;
