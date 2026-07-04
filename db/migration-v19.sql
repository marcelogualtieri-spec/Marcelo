-- ============================================================================
-- MIGRAÇÃO v19 — telefone do profissional com HASH+PEPPER na indicação (LGPD §4.2)
-- ----------------------------------------------------------------------------
-- Regra: enquanto o profissional é só "indicado" (status convidado — ainda NÃO
-- entrou nem aceitou os termos), o telefone dele fica guardado APENAS como hash
-- irreversível (HMAC com pepper, a mesma chave de edges/pending_invites).
-- O número em claro só é gravado QUANDO a pessoa entra e aceita os termos —
-- porque aí ele precisa ser entregável na busca (§4.4).
--
-- O dedupe de indicações passa a ser pela coluna telefone_hash.
-- O backfill dos registros antigos é feito pelo código no boot (o pepper vive
-- só no ambiente do Render — não dá para calcular o hash aqui no SQL).
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table providers add column if not exists telefone_hash text;
create index if not exists idx_providers_telefone_hash on providers (telefone_hash);

-- telefone pode ficar vazio enquanto o profissional não entrou/aceitou.
alter table providers alter column telefone drop not null;
