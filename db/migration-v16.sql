-- ============================================================================
-- MIGRAÇÃO v16 — guardar o MOTIVO da indicação (o "porquê" de quem indicou)
-- ----------------------------------------------------------------------------
-- Quando um cliente indica um profissional, ele conta POR QUE indica ("fez os
-- doces do batizado, caprichou e foi pontual"). Guardamos esse motivo na conexão
-- entre quem indicou e o profissional. Quando os dois confirmam, esse motivo é
-- copiado para a recomendação (recommendations.nota) e passa a enriquecer as
-- buscas — formando, com o tempo, um banco rico de recomendações de verdade.
--
-- A descrição do PRÓPRIO profissional já é guardada em providers.descricao.
--
-- Execute no SQL Editor do Supabase ANTES do deploy. Seguro rodar mais de uma vez.
-- ============================================================================

alter table conexoes add column if not exists motivo text;
