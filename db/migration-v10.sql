-- ============================================================================
-- MIGRAÇÃO v10 — perfil de prestador de serviço (Fase 3)
-- ----------------------------------------------------------------------------
-- Transforma o prestador de "registro passivo" em participante: vincula o
-- profissional a um membro, guarda o status do cadastro, o consentimento (LGPD
-- com data/hora e versão dos Termos) e os campos do perfil (região, etc.).
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table providers add column if not exists member_id uuid references members(id) on delete set null;

-- status do cadastro do prestador:
--   'convidado'        -> indicado por alguem, ainda nao entrou
--   'onboarding'       -> clicou no link, falta aceitar os termos
--   'aguardando_perfil'-> aceitou os termos, falta refinar o perfil
--   'ativo'            -> cadastro completo
--   'pausado'          -> nao quer receber indicacoes por ora
--   'removido'         -> pediu para sair
alter table providers add column if not exists status text not null default 'convidado';

alter table providers add column if not exists regiao            text;
alter table providers add column if not exists diferenciais      text;
alter table providers add column if not exists descricao         text;
alter table providers add column if not exists termos_aceitos_em timestamptz;
alter table providers add column if not exists termos_versao     text;

create index if not exists idx_providers_member on providers (member_id);
create index if not exists idx_providers_status on providers (status);
