-- ============================================================================
-- MIGRAÇÃO v12 — SAIR anonimiza as indicações (não apaga) — LGPD §4.5
-- ----------------------------------------------------------------------------
-- Regra: quando a pessoa sai (SAIR), apagamos o cadastro e o nome dela, MAS as
-- indicações que ela fez NÃO são deletadas — viram anônimas (⚪ rede geral).
--
-- Para isso, a coluna recommendations.member_id passa a aceitar NULL e o vínculo
-- com members passa a ser ON DELETE SET NULL (em vez de ON DELETE CASCADE). Assim,
-- ao apagar o membro, o banco SOZINHO desliga o nome da indicação (member_id=NULL)
-- e a recomendação continua existindo, só que sem dono — exatamente o que a LGPD
-- pede aqui. O nome some porque ele é sempre buscado a partir do member_id.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

-- 1) member_id pode ficar sem dono (indicação anonimizada).
alter table recommendations alter column member_id drop not null;

-- 2) Troca o ON DELETE CASCADE por ON DELETE SET NULL.
--    (o nome padrão do vínculo no Postgres é '<tabela>_<coluna>_fkey'.)
alter table recommendations drop constraint if exists recommendations_member_id_fkey;
alter table recommendations
    add constraint recommendations_member_id_fkey
    foreign key (member_id) references members(id) on delete set null;
