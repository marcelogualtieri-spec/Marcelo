-- ============================================================================
-- SEED "MINHA REDE" — indicações 🟢 COM NOME para o SEU número (teste do fluxo)
-- ----------------------------------------------------------------------------
-- Cria 3 amigos fictícios (Ana, Bruno e Carla Teste) já CONECTADOS a você
-- (conexão validada pelos dois lados) e registra indicações deles apontando
-- para provedores REAIS da base do Platô Perdizes (seed-base-real.sql).
--
-- Resultado esperado ao buscar:
--   • "dentista em Perdizes"  → 🟢 Ju Dentista — indicado por Ana e Bruno (2 pessoas!)
--   • "eletricista"           → 🟢 Vagner Eletricista — indicado por Bruno
--   • "diarista em Perdizes"  → 🟢 Didi (faxina) — indicado por Carla
--   • "chaveiro"              → 🟢 Gilberto Chaveiro — indicado por Carla
--
-- REQUISITOS: (1) rodar DEPOIS do seed-base-real.sql; (2) você já ter mandado
-- ao menos um "oi" ao bot (existir em members).
-- Idempotente: pode rodar de novo à vontade.
--
-- >>> EDITE o número abaixo se necessário (formato E.164: +55 DDD número) <<<
-- ============================================================================
do $$
declare
    meu_wa text := '+5511978200340';   -- <<< SEU número. Ajuste se preciso.
    meu_id uuid;
    amigo1 uuid;   -- Ana Teste
    amigo2 uuid;   -- Bruno Teste
    amigo3 uuid;   -- Carla Teste
begin
    -- Acha o seu cadastro (tenta o número informado e uma variação comum de digitação).
    select id into meu_id from members
     where wa_id in (meu_wa, '+5511978290340')
     limit 1;
    if meu_id is null then
        raise notice 'Número % não encontrado em members. Mande um oi ao bot e rode de novo (ou ajuste meu_wa no topo).', meu_wa;
        return;
    end if;

    -- Amigos fictícios com consentimento (reaproveita se já existirem).
    insert into members (wa_id, nome_perfil, consent, consent_at)
    values ('+5511900000091', 'Ana Teste', true, now())
    on conflict (wa_id) do update set consent = true, nome_perfil = 'Ana Teste'
    returning id into amigo1;

    insert into members (wa_id, nome_perfil, consent, consent_at)
    values ('+5511900000092', 'Bruno Teste', true, now())
    on conflict (wa_id) do update set consent = true, nome_perfil = 'Bruno Teste'
    returning id into amigo2;

    insert into members (wa_id, nome_perfil, consent, consent_at)
    values ('+5511900000093', 'Carla Teste', true, now())
    on conflict (wa_id) do update set consent = true, nome_perfil = 'Carla Teste'
    returning id into amigo3;

    -- Conexões VALIDADAS entre você e cada amigo (os dois lados confirmados).
    insert into conexoes (member_a, member_b, origem, a_confirmou, b_confirmou, status)
    values
        (amigo1, meu_id, 'cliente', true, true, 'validada'),
        (amigo2, meu_id, 'cliente', true, true, 'validada'),
        (amigo3, meu_id, 'cliente', true, true, 'validada')
    on conflict (member_a, member_b) do update
        set a_confirmou = true, b_confirmou = true, status = 'validada';

    -- Indicações COM NOME (apontam para provedores reais do seed-base-real).
    -- Limpa as anteriores destes amigos para o script ser idempotente.
    delete from recommendations where member_id in (amigo1, amigo2, amigo3);
    insert into recommendations (member_id, provider_id, servico, bairro, cidade, nota) values
        -- Ana e Bruno indicam a MESMA dentista → prova social ("2 pessoas")
        (amigo1, '00000000-0000-4000-b63a-67b8e10ed189', 'dentista', 'Perdizes', 'São Paulo',
         'Atende minha família toda, super cuidadosa e pontual.'),
        (amigo2, '00000000-0000-4000-b63a-67b8e10ed189', 'dentista', 'Perdizes', 'São Paulo',
         'Fiz um canal com ela, nem doeu. Recomendo demais.'),
        -- Bruno indica o eletricista
        (amigo2, '00000000-0000-4000-bf05-978df88fa0a1', 'eletricista', 'Perdizes', 'São Paulo',
         'Trocou o quadro de luz aqui de casa, rápido e caprichado.'),
        -- Carla indica a diarista e o chaveiro
        (amigo3, '00000000-0000-4000-b0f6-e7463d901f26', 'diarista', 'Perdizes', 'São Paulo',
         'Vem toda semana aqui em casa, confio de olhos fechados.'),
        (amigo3, '00000000-0000-4000-b45e-42367b79f266', 'chaveiro', 'Perdizes', 'São Paulo',
         'Me salvou quando perdi a chave, veio em 20 minutos.');

    raise notice 'Pronto! Rede de teste criada para % (id %). Busque "dentista em Perdizes" para ver o 🟢 com nomes.', meu_wa, meu_id;
end $$;


-- ============================================================================
-- LIMPEZA (quando terminar os testes): descomente e rode o bloco abaixo.
-- Remove os amigos fictícios; as conexões e indicações deles caem junto (cascade).
-- ============================================================================
-- delete from members where wa_id in
--     ('+5511900000091', '+5511900000092', '+5511900000093');
