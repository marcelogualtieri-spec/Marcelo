-- ============================================================================
-- MIGRAÇÃO v20 — versão dos termos no consentimento do cliente (LGPD §4.D)
-- ============================================================================
-- Regra: ao cliente aceitar os termos, o código grava QUANDO e QUAL VERSÃO.
-- Permite auditar: "Em 2026-07-11, essa pessoa consentiu com a v1.2 dos termos".
-- Sem isso, regulador não consegue rastrear qual versão foi aceita.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table members add column if not exists consent_version text;
create index if not exists idx_members_consent_version on members (consent_version);

-- Backfill: registros antigos sem versão ficam NULL (código não usa pré-v20).
-- Novos registros gravam a versão ao aceitar (app.py:registrar_consentimento).
