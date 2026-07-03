# Pendências dos fluxos — mudanças sugeridas aguardando decisão

> Este documento registra as mudanças que EU (Code) sugeri em cada análise de fluxo e
> que **ainda não foram aprovadas nem implementadas**. Serve para consolidar depois.
> Nada aqui foi mexido no código — é só o backlog de decisões.
>
> Legenda de prioridade: 🔴 LGPD/base legal · 🟠 furo de UX (mensagem sem saída) ·
> 🟡 divergência de fluxo/regra · ⚪ modelagem/refinamento.
>
> Última atualização: análise de "Minha conta + SAIR".

---

## 1) INDICAR PROFISSIONAL — (analisado, não implementado)

**Falta:**
- 🟡 Ramificação A/B/C no dedupe (hoje tudo cai em FIM_A). Não existem FIM_B nem FIM_C.
- 🟡 **FIM_B (profissional já ativo):** deveria registrar a recomendação + conexão pendente,
  SEM gerar link, e dizer "já está na Dorote.ia". Hoje gera link genérico e **não registra
  recomendação**.
- 🟡 **FIM_C (já indicado por outra pessoa):** deveria somar a recomendação e reusar o
  MESMO link. Hoje **sobrescreve** os dados do 1º indicador (perde quem indicou primeiro).
- 🟡 Aviso "já está registrado" quando a mesma pessoa indica o mesmo profissional 2×.
- 🟡 "Continuar a indicação de [Nome]?" ao voltar depois de abandonar.
- 🟡 Tratamento de texto impróprio/sensível (hoje grava cru em `descricao`).

**Diverge / LGPD:**
- 🔴 **Dedupe por telefone CRU** (`providers.telefone`), não por hash. E o telefone do
  profissional indicado fica **gravado em claro** já na indicação (antes de ele entrar/
  consentir). É decisão de produto: o número precisa ser recuperável para ser
  compartilhado quando ele vira `ativo`. Caminho sugerido: guardar só o hash enquanto
  `convidado` e o número cru só após o consentimento (muda o modelo — precisa seu aval).
- 🟡 Dois gatilhos de entrada (botão + IA por texto livre) em vez de só o botão.

---

## 2) BUSCAR PROFISSIONAL — (implementado; 1 questão em aberto)

Implementado (commit `9fd2e21`): resultado determinístico com botões, BUSCA_FALTA com
botões de região, RES_GERAL (rede pequena), ordenação por nº de indicações.

**Questão em aberto (aguardando sua decisão):**
- 🟡 **Botões do RES_VAZIO.** Hoje: `[Perguntar a amigos] [Convidar rede] [Menu]`.
  A tabela pedia `[Indicar] [Convidar] [Menu]`. Mantive o atual de propósito para **não
  reintroduzir** o anti-padrão de pedir a quem busca que ela mesma indique. **Decisão:**
  manter "Perguntar a amigos" ou trocar por "Indicar"?

---

## 3) SER PROFISSIONAL / CONFIGURAR PERFIL — (analisado, não implementado)

**LGPD / UX imediatos:**
- 🟠 **Furo do `prest_pausar`:** ao pausar/ativar, responde só com TEXTO, sem botão nem
  menu depois — a pessoa fica sem navegação.
- 🔴 **Link dos termos profissionais faltando** no autocadastro do cliente já aceito
  (`quero_ser_prof` → `prest_self`): a tela diz "aceite os termos profissionais" mas **não
  mostra o link** (diferente de PROF_DUAL/PROF_SO). O aceite é gravado, mas sem exibir o
  documento nesse caminho.

**Falta / diverge:**
- 🟡 Linha de abertura dupla ("Perfil profissional iniciado!" vs "Que bom ter você
  **também** como profissional!"), decidida pelo código conforme já-ser-cliente.
- 🟡 "Remover" com confirmação no menu do profissional (hoje só Pausar/Ativar; remoção só
  via SAIR ou `prest_nao`).
- 🟡 "Quer continuar a configuração do seu perfil?" ao voltar depois de abandonar.
- 🟡 Normalização de texto impróprio nos campos do perfil (hoje vai cru p/ `descricao`/`raw`).
- ⚪ Botão `[Concluir]` no PROF_COLETA (hoje é `[Menu]`; conclui-se enviando o texto).
- ⚪ Estado explícito `AUTOCADASTRO_INVISIVEL` (hoje grava `status="ativo"`; fica invisível
  só porque não há recomendação — efeito correto, modelagem que poderia ser explícita).
- 🟡 "Já tem perfil e toca Ser profissional" → oferecer o exato `[Editar] [Menu]`.

---

## 4) ONBOARDING + CONSENTIMENTO — (analisado, não implementado)

**LGPD:**
- 🔴 **Versão dos termos no consentimento do CLIENTE.** Hoje grava `consent_at` (data/hora)
  mas **não** a versão dos termos aceita. Precisa: coluna nova (ex.: `consent_version`) +
  gravar `termos.DATA_VIGENCIA` no `registrar_consentimento`. **Exige migração no Supabase.**
- 🔴 **Texto cru pré-aceite salvo no histórico.** A 1ª mensagem da pessoa é persistida em
  `members.historico` antes do aceite (`cerebro.py:501`). Sugerido: não salvar histórico
  antes do consentimento (ou salvar só a categoria da intenção).

**Furos / falta:**
- 🟠 **Botões na apresentação** (`BOAS_VINDAS` é enviada como texto, pedindo pra digitar
  SIM/SABER MAIS) e no **catch-all pré-aceite** (`app.py:3199`, sem botões). `ADIAR` também
  sem botão.
- 🟡 **Retomar o pedido após o aceite** (quem chega pedindo "eletricista" tem que repetir
  depois do SIM).
- 🟡 Botões do SABER_MAIS diferentes da tabela (3 botões, inclui caminho profissional).

**Cumprido (não mexer):** IA não conversa livre antes do aceite (mensagem fixa, sem chamar
o modelo; roteador determinístico; trava defensiva no cérebro).

---

## 5) MINHA CONTA + SAIR — (analisado, não implementado)

**LGPD:**
- 🔴 **Mensagem final do SAIR desonesta.** `ADEUS` diz *"Pronto, apaguei tudo certinho 💛"*,
  mas as indicações são **anonimizadas, não apagadas**. A tela de CONFIRMAÇÃO
  (`SAIR_CLIENTE`) é honesta; o problema é só a mensagem final. Trocar para algo como
  "Pronto, sua conta foi apagada. Se um dia quiser voltar, é só mandar um oi 💛".
- 🔴 **SAIR não remove o rastro da pessoa nas redes de OUTROS.** `excluir_membro` anonimiza
  as recomendações ✅ e apaga o cadastro ✅, mas **não** remove o hash do número dela em
  `edges` de outras pessoas, **nem** limpa o `nome` dela guardado em `edges`/
  `pending_invites` de terceiros. A regra manda "apagar o nome" e "remover o contato dela
  guardado em outras redes (hash)".

**Cumprido (não mexer):**
- ✅ Confirmação obrigatória antes de apagar (`enviar_confirmar_exclusao`).
- ✅ Indicações anonimizadas (`recommendations.member_id = NULL`), não deletadas.
- ✅ Contadores vêm do banco (`contar()`), não da IA.
- ✅ "Minha rede" não expõe números de telefone (só nomes/quantidades).
- ✅ "Minha conta" adapta o conteúdo ao perfil ativo (código, não IA).

**Falta / diverge (fluxo):**
- 🟡 Botão **"Ver o outro perfil"** no CONTA_DADOS de contas híbridas (hoje só via TROCAR).
- 🟡 O menu de conta já vem **quebrado** em vários itens (Minha rede / Indicações / etc.)
  em vez de um único "Ver meus dados" — é mais rico que a tabela, decidir se mantém.
