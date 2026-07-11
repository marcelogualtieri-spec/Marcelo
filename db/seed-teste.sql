-- ============================================================================
-- SEED DE TESTE — provedores fictícios + recomendações (para testar a busca)
-- ----------------------------------------------------------------------------
-- Cole no SQL Editor do Supabase e clique em RUN. Seguro rodar mais de uma vez
-- (limpa o seed anterior antes de reinserir — só mexe nos dados de teste).
--
-- PARTE A  → 12 provedores "ativos" com recomendações ANÔNIMAS (⚪ rede geral).
--            Aparecem para QUALQUER pessoa que buscar, sem precisar de rede.
-- PARTE B  → (opcional) faz 3 desses aparecerem 🟢 COM NOME para o SEU número,
--            criando conexões validadas. Edite o número no topo da Parte B.
--
-- Como testar depois: no WhatsApp, busque por ex. "encanador em Perdizes",
-- "eletricista em Pinheiros", "diarista", "pediatra em Vila Mariana", ou use
-- "buscar na cidade toda".
-- ============================================================================


-- ----------------------------------------------------------------------------
-- LIMPEZA do seed anterior (só remove os registros de teste, pelos UUIDs fixos)
-- ----------------------------------------------------------------------------
delete from recommendations where provider_id in (
    '00000000-0000-4000-a000-000000000001','00000000-0000-4000-a000-000000000002',
    '00000000-0000-4000-a000-000000000003','00000000-0000-4000-a000-000000000004',
    '00000000-0000-4000-a000-000000000005','00000000-0000-4000-a000-000000000006',
    '00000000-0000-4000-a000-000000000007','00000000-0000-4000-a000-000000000008',
    '00000000-0000-4000-a000-000000000009','00000000-0000-4000-a000-000000000010',
    '00000000-0000-4000-a000-000000000011','00000000-0000-4000-a000-000000000012'
);
delete from providers where id in (
    '00000000-0000-4000-a000-000000000001','00000000-0000-4000-a000-000000000002',
    '00000000-0000-4000-a000-000000000003','00000000-0000-4000-a000-000000000004',
    '00000000-0000-4000-a000-000000000005','00000000-0000-4000-a000-000000000006',
    '00000000-0000-4000-a000-000000000007','00000000-0000-4000-a000-000000000008',
    '00000000-0000-4000-a000-000000000009','00000000-0000-4000-a000-000000000010',
    '00000000-0000-4000-a000-000000000011','00000000-0000-4000-a000-000000000012'
);


-- ============================================================================
-- PARTE A — PROVEDORES (status 'ativo' = aparecem na busca)
-- ============================================================================
insert into providers (id, nome, telefone, servico, bairro, cidade, estado, status, nota_media, qtd_avaliacoes) values
('00000000-0000-4000-a000-000000000001','Roberto Encanador 24h','+5511911110001','encanador','Perdizes','São Paulo','SP','ativo',4.8,12),
('00000000-0000-4000-a000-000000000002','Aparecida Conserta Tudo','+5511911110002','encanador','Pinheiros','São Paulo','SP','ativo',4.5,8),
('00000000-0000-4000-a000-000000000003','Marcos Elétrica Segura','+5511911110003','eletricista','Pinheiros','São Paulo','SP','ativo',4.9,20),
('00000000-0000-4000-a000-000000000004','Dona Cida Diarista','+5511911110004','diarista','Tatuapé','São Paulo','SP','ativo',5.0,15),
('00000000-0000-4000-a000-000000000005','Fernanda Limpeza','+5511911110005','diarista','Perdizes','São Paulo','SP','ativo',4.7,9),
('00000000-0000-4000-a000-000000000006','João Pintor Caprichoso','+5511911110006','pintor','Moema','São Paulo','SP','ativo',4.6,11),
('00000000-0000-4000-a000-000000000007','Dra. Helena Souza','+5511911110007','pediatra','Vila Mariana','São Paulo','SP','ativo',4.9,30),
('00000000-0000-4000-a000-000000000008','Bruna Nails Studio','+5511911110008','manicure','Santana','São Paulo','SP','ativo',4.8,18),
('00000000-0000-4000-a000-000000000009','Carlos Personal Trainer','+5511911110009','personal trainer','Pinheiros','São Paulo','SP','ativo',4.7,14),
('00000000-0000-4000-a000-000000000010','Teacher Paula Inglês','+5511911110010','professor de inglês','Perdizes','São Paulo','SP','ativo',5.0,10),
('00000000-0000-4000-a000-000000000011','Zé Chaveiro Rápido','+5511911110011','chaveiro','Vila Madalena','São Paulo','SP','ativo',4.4,7),
('00000000-0000-4000-a000-000000000012','Estúdio Foco Fotografia','+5511911110012','fotógrafo','Itaim Bibi','São Paulo','SP','ativo',4.9,13);


-- ============================================================================
-- PARTE A — RECOMENDAÇÕES ANÔNIMAS (member_id NULL → ⚪ rede geral, para todos)
-- Quanto mais linhas por provedor, mais "prova social" (nº de indicações).
-- ============================================================================
insert into recommendations (member_id, provider_id, servico, bairro, cidade, nota) values
-- encanador (2 profissionais; Roberto tem mais indicações)
(null,'00000000-0000-4000-a000-000000000001','encanador','Perdizes','São Paulo','Resolveu um vazamento no mesmo dia, muito pontual.'),
(null,'00000000-0000-4000-a000-000000000001','encanador','Perdizes','São Paulo','Preço justo e trabalho limpo.'),
(null,'00000000-0000-4000-a000-000000000001','encanador','Perdizes','São Paulo','Já chamei duas vezes, sempre ótimo.'),
(null,'00000000-0000-4000-a000-000000000002','encanador','Pinheiros','São Paulo','Atenciosa e explicou tudo direitinho.'),
-- eletricista
(null,'00000000-0000-4000-a000-000000000003','eletricista','Pinheiros','São Paulo','Instalou o chuveiro e revisou o quadro. Excelente.'),
(null,'00000000-0000-4000-a000-000000000003','eletricista','Pinheiros','São Paulo','Rápido e seguro, recomendo muito.'),
-- diarista (2 profissionais)
(null,'00000000-0000-4000-a000-000000000004','diarista','Tatuapé','São Paulo','Deixa a casa impecável, super caprichosa.'),
(null,'00000000-0000-4000-a000-000000000004','diarista','Tatuapé','São Paulo','Pontual e de confiança.'),
(null,'00000000-0000-4000-a000-000000000005','diarista','Perdizes','São Paulo','Trabalho caprichado e educada.'),
-- pintor
(null,'00000000-0000-4000-a000-000000000006','pintor','Moema','São Paulo','Pintou o apê todo, ficou lindo e sem sujeira.'),
-- pediatra
(null,'00000000-0000-4000-a000-000000000007','pediatra','Vila Mariana','São Paulo','Muito atenciosa com as crianças, super paciente.'),
(null,'00000000-0000-4000-a000-000000000007','pediatra','Vila Mariana','São Paulo','Excelente médica, indico de olhos fechados.'),
-- manicure
(null,'00000000-0000-4000-a000-000000000008','manicure','Santana','São Paulo','Capricha demais, ambiente limpinho.'),
-- personal trainer
(null,'00000000-0000-4000-a000-000000000009','personal trainer','Pinheiros','São Paulo','Montou um treino sob medida, muito atencioso.'),
-- professor de inglês
(null,'00000000-0000-4000-a000-000000000010','professor de inglês','Perdizes','São Paulo','Aulas dinâmicas, meu filho evoluiu muito.'),
-- chaveiro
(null,'00000000-0000-4000-a000-000000000011','chaveiro','Vila Madalena','São Paulo','Abriu a porta rapidinho de madrugada, salvou meu dia.'),
-- fotógrafo
(null,'00000000-0000-4000-a000-000000000012','fotógrafo','Itaim Bibi','São Paulo','Fez as fotos do batizado, ficaram maravilhosas.');


-- ============================================================================
-- PARTE B — (OPCIONAL) Fazer 3 provedores aparecerem 🟢 COM NOME para VOCÊ
-- ----------------------------------------------------------------------------
-- Cria 3 "amigos" fictícios já conectados a você (conexão validada). As
-- indicações deles aparecem com o nome deles quando VOCÊ buscar.
--
-- >>> EDITE o número abaixo para o SEU WhatsApp em formato E.164 (+55...) <<<
--     Ex.: +5511978290340   (DDI 55, DDD 11, número).
--     Você já precisa ter mandado ao menos um "oi" para o bot (existir em members).
-- ============================================================================
do $$
declare
    meu_wa   text := '+5511978290340';   -- <<< TROQUE PELO SEU NÚMERO
    meu_id   uuid;
    amigo1   uuid;
    amigo2   uuid;
    amigo3   uuid;
begin
    select id into meu_id from members where wa_id = meu_wa;
    if meu_id is null then
        raise notice 'Número % não encontrado em members. Mande um oi ao bot primeiro e rode a Parte B de novo.', meu_wa;
        return;
    end if;

    -- Cria (ou reaproveita) 3 amigos fictícios com consentimento.
    insert into members (wa_id, nome_perfil, consent, consent_at)
    values ('+5511900000091','Ana Teste', true, now())
    on conflict (wa_id) do update set consent = true
    returning id into amigo1;

    insert into members (wa_id, nome_perfil, consent, consent_at)
    values ('+5511900000092','Bruno Teste', true, now())
    on conflict (wa_id) do update set consent = true
    returning id into amigo2;

    insert into members (wa_id, nome_perfil, consent, consent_at)
    values ('+5511900000093','Carla Teste', true, now())
    on conflict (wa_id) do update set consent = true
    returning id into amigo3;

    -- Conexões VALIDADAS entre você e cada amigo (os dois lados confirmados).
    insert into conexoes (member_a, member_b, origem, a_confirmou, b_confirmou, status)
    values
        (amigo1, meu_id, 'cliente', true, true, 'validada'),
        (amigo2, meu_id, 'cliente', true, true, 'validada'),
        (amigo3, meu_id, 'cliente', true, true, 'validada')
    on conflict (member_a, member_b) do update
        set a_confirmou = true, b_confirmou = true, status = 'validada';

    -- Recomendações COM NOME (feitas pelos amigos) para 3 provedores do seed.
    -- Ana indica o Roberto (encanador Perdizes); Bruno o Marcos (eletricista
    -- Pinheiros); Carla a Dra. Helena (pediatra Vila Mariana).
    delete from recommendations where member_id in (amigo1, amigo2, amigo3);
    insert into recommendations (member_id, provider_id, servico, bairro, cidade, nota) values
        (amigo1,'00000000-0000-4000-a000-000000000001','encanador','Perdizes','São Paulo','Meu vizinho usou e aprovou, super honesto.'),
        (amigo2,'00000000-0000-4000-a000-000000000003','eletricista','Pinheiros','São Paulo','Fez a parte elétrica da minha reforma, top.'),
        (amigo3,'00000000-0000-4000-a000-000000000007','pediatra','Vila Mariana','São Paulo','Atende meus filhos há anos, confio muito.');

    raise notice 'Parte B aplicada para % (id %). Busque "encanador em Perdizes", "eletricista em Pinheiros" ou "pediatra em Vila Mariana" para ver 🟢 com nome.', meu_wa, meu_id;
end $$;


-- ============================================================================
-- CONFERÊNCIA rápida (opcional): quantos provedores/recos de teste existem
-- ============================================================================
-- select servico, bairro, nome, status from providers
--   where id::text like '00000000-0000-4000-a000-%' order by servico;
