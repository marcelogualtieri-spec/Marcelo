-- ============================================================================
-- MIGRAÇÃO v15 — nome do contato na agenda (para a pessoa ver a PRÓPRIA agenda)
-- ----------------------------------------------------------------------------
-- A pessoa pode ver, na "Minha rede", quem ela convidou e ainda não respondeu.
-- Para isso, guardamos o NOME que veio no cartão de contato (que ela mesma já tem
-- na agenda do telefone). O NÚMERO continua só como hash irreversível (LGPD) —
-- nunca guardamos o telefone em claro.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table pending_invites add column if not exists nome text;
alter table edges          add column if not exists nome text;
