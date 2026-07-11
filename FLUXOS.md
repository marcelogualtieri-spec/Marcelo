# FLUXOS.md — Mapa dos fluxos, mensagens e botões da Dorote.ia

> **Fonte de verdade operacional.** Este documento lista, para cada fluxo, a mensagem
> padrão de hoje (constante em `textos.py`), os botões (id técnico → rótulo visível) e o
> tipo de menu. Onde uma possibilidade ainda **não existe** no código, está marcada como
> `⚠️ GAP` com a mensagem proposta.
>
> Regras de UX (do CLAUDE.md) que valem em toda tabela: **máx. 3 botões**, rótulo ≤ 20
> caracteres, decisão sempre por botão, linguagem neutra de gênero, a pessoa **nunca fica
> sem ação**.

---

## Legenda

**Tipo de menu:**
- `BOTÕES` — mensagem interativa com até 3 botões (`enviar_botoes_meta`).
- `LISTA` — *list message* com até 10 itens (`enviar_lista_meta`), abre ao tocar em "Ver opções".
- `TEXTO` — texto simples, sem botão (`resposta_whatsapp`). **Evitar** (viola "nunca sem ação").

**Estados de profissional (`providers.status`):**
`onboarding` → `aguardando_perfil` → `ativo` (aparece na busca) · `pausado` · `removido`

**Estados de conexão (`conexoes.status`):** `pendente` → `validada` / `recusada`

**Fluxos com estado (`members.estado`):** `busca`, `sem_resultado`, `indicar`, `perfil_prof`,
`ajuda`, `busca_retomada`, `entrada_rec`

---

## 0. ENTRADA — como o bot decide o que fazer (`_processar_mensagem`)

Ordem de decisão a cada mensagem recebida:

| # | Condição | Ação |
|---|---|---|
| 1 | Membro não existe | Cria cadastro (`consent=False`); casa convite por código ou por número (convite pendente) |
| 2 | Sem consent + tem `invited_by` | Marca nome de quem convidou (para citar nas boas-vindas) |
| 3 | Texto tem `(prestador: X)` | **Onboarding profissional** (prioridade máxima) → tabela 4 |
| 4 | Texto tem `(recomendar: X)` | **Entrada por link de recomendar** → tabela 0.3 |
| 5 | Já consentiu + texto tem `(convite: X)` | Cria/valida conexão de cliente na hora |
| 6 | Primeiro contato (sem consent, sem histórico) | Boas-vindas fixa → tabela 0.1 |
| 7 | Botão/comando de menu | Navegação determinística (`rotear_menu`) |
| 8 | Texto livre | Vai para a IA (só extrai campos) |
| — | Fechamento | Se consentiu e nada mandou botão → mostra menu do perfil ativo |

### Tipos de link

| Link | Marcador no texto | Mensagem pré-escrita | Ao abrir |
|---|---|---|---|
| **Convite cliente** | `(convite: ABC123)` (só no genérico) | "Oi! Quero fazer parte da Central de indicações de confiança Dorote.ia 💛" | Traz cliente; abre conexão mútua |
| **Prestador** | `(prestador: encanador)` | "Olá! Quero fazer parte da Dorote.ia como profissional…" | Onboarding profissional |
| **Recomendar** | `(recomendar: ABC123)` | "Oi! Vim recomendar um trabalho na Dorote.ia 💛…" | Registra recomendação; profissional confirma |

---

## 0.1. BOAS-VINDAS — primeiro contato

| Situação | Mensagem (constante) | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Chegou sozinho | `BOAS_VINDAS` | `consent_sim` → ✅ Aceito e começar · `consent_saber_mais` → ℹ️ Saber mais | BOTÕES |
| Chegou por convite pessoal | `BOAS_VINDAS_CONVIDADO` (cita quem convidou) | `consent_sim` → ✅ Aceito e começar · `consent_saber_mais` → ℹ️ Saber mais | BOTÕES |
| Chegou por link de recomendar | `BOAS_VINDAS_RECOMENDAR` | ⚠️ **GAP: enviada sem botões** (ver §Gaps) | TEXTO |

> Detecção robusta: qualquer texto de boas-vindas que cite "Termos" recebe os botões
> automaticamente (`enviar_texto_com_botoes_boas_vindas`).

## 0.2. Caminhos a partir do "Saber mais" / aceite

| Gatilho (id) | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| `consent_saber_mais` | `SABER_MAIS` | `consent_sim` → SIM, aceito · `prof_quero` → Quero ser prof. · `adiar` → Deixa pra depois | BOTÕES |
| `prof_quero` | `PROF_ESCOLHA` | `prof_dual` → Cliente e prof. · `prof_so` → Só profissional · `voltar_saber` → Voltar | BOTÕES |
| `prof_dual` | `PROF_DUAL` (2 termos) | `prest_self_ok` → Aceito os dois · `voltar_saber` → Voltar | BOTÕES |
| `prof_so` | `PROF_SO` (termos prof) | `prest_self_ok` → Aceito os termos · `voltar_saber` → Voltar | BOTÕES |
| `adiar` | `ADIAR` | `consent_sim` → ✅ Começar agora · `consent_saber_mais` → ℹ️ Saber mais | BOTÕES |
| `consent_sim` / texto de aceite | `CLIENTE_ATIVO` + menu principal | (menu principal) | LISTA |
| Texto que parece pedido | "Posso te ajudar com isso 💛…" (guarda o pedido) | `consent_sim` → ✅ Aceito e começar · `consent_saber_mais` → ℹ️ Saber mais | BOTÕES |
| Texto aleatório | `PRECISA_CONSENTIR` | `consent_sim` → ✅ Aceito e começar · `consent_saber_mais` → ℹ️ Saber mais | BOTÕES |

## 0.3. Entrada por link de recomendar (`entrada_rec`)

| Passo | Mensagem | Botões | Tipo |
|---|---|---|---|
| Ainda não consentiu | `BOAS_VINDAS_RECOMENDAR` (cita profissional) | ⚠️ **GAP: sem botões** | TEXTO |
| Ao aceitar | `REC_ENTROU_OK` + menu principal | (menu) | LISTA |
| Abriu o próprio link | `INDICAR_SI_MESMO` | `menu` → 🏠 Menu | BOTÕES |

---

## 1. MENU PRINCIPAL e navegação (pós-aceite)

### Menu principal — `enviar_menu_principal` — LISTA ("Ver opções")
Texto padrão: "O que você deseja fazer? 💛"

| id | Título | Descrição | Quando aparece |
|---|---|---|---|
| `buscar` | 🔍 Buscar uma indicação | Achar um profissional de confiança | sempre |
| `rede_indicar` | 💛 Indicar profissional | Recomendar alguém bom que você conhece | sempre |
| `rede_convidar` | 🤝 Convidar rede | Trazer gente de sua confiança | sempre |
| `trocar` | 🔁 Trocar de perfil | Ir para o seu perfil profissional | só se tem perfil prof |
| `quero_ser_prof` | 💼 Ser profissional | Criar o seu perfil para ser recomendado | só se NÃO tem prof |
| `dados` | ⚙️ Minha conta | Sua rede e indicações que você fez | sempre |

### Menu do prestador — `enviar_menu_prestador` — BOTÕES
Texto: "💼 Visão Profissional. O que você quer fazer?"

| id | Rótulo |
|---|---|
| `prest_editar` | ✏️ Editar perfil |
| `prest_pausar` | ⏸️ Pausar/Ativar |
| `outras_opcoes` | ☰ Outras opções |

### Gatilhos de reabertura (`MENU_TRIGGERS`)
`menu, inicio, voltar, home, oi, ola, olá, oie, opa, bom dia, boa tarde, boa noite, menu principal`
→ Antes do menu, mostra pendências **nesta ordem**: 1º confirmação de conexão, 2º avaliação
pendente, depois o menu. (Padrão da janela de 24h — §7.5 do CLAUDE.md.)

---

## 2. FLUXO "BUSCAR" (estado `busca`)

| Passo | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Cliente novo (rede vazia) | `BUSCAR_SEM_REDE` | `gerar_link` → 🔗 Gerar meu link · `buscar_geral` → 🔍 Buscar rede geral | BOTÕES |
| Pediu busca (tem rede) | "Me conta o que você precisa e em qual bairro…" | `menu` → 🏠 Menu | BOTÕES |
| Faltou a região | `BUSCA_FALTA_REGIAO` | `busca_cidade_toda` → 🏙️ Toda a cidade · `busca_bairro` → 📍 Escrever bairro · `menu` → 🏠 Menu | BOTÕES |
| Escolheu "escrever bairro" | `BUSCA_PEDIR_BAIRRO` | `busca_cidade_toda` → 🏙️ Toda a cidade · `menu` → 🏠 Menu | BOTÕES |
| **Resultado 🟢/🟡** (com nome) | corpo do resultado | `buscar` → 🔍 Buscar outro · `rede_indicar` → 💛 Indicar · `menu` → 🏠 Menu | BOTÕES |
| **Resultado ⚪** (rede grande) | corpo | `buscar` → 🔍 Buscar outro · `rede_indicar` → 💛 Indicar · `menu` → 🏠 Menu | BOTÕES |
| **Resultado ⚪** (rede pequena < 5) | corpo + `BUSCA_REDE_PEQUENA` | `rede_convidar` → 🤝 Convidar · `buscar` → 🔍 Buscar outro · `menu` → 🏠 Menu | BOTÕES |
| **Sem resultado** (estado `sem_resultado`) | `BUSCA_SEM_RESULTADO` | `pedir_amigos` → 👋 Perguntar a amigos · `gerar_link` → ➕ Convidar rede · `menu` → 🏠 Menu | BOTÕES |

### Perguntar a amigos (a partir de "sem resultado")

| Passo | Mensagem | Botões | Tipo |
|---|---|---|---|
| Escolher amigo | `PEDIR_AMIGOS_LISTA` | itens `ask:{id}` (nome do amigo) | LISTA |
| Sem amigos confirmados | `PEDIR_AMIGOS_SEM_REDE` | `gerar_link` → 🔗 Gerar meu link · `menu` → 🏠 Menu | BOTÕES |
| Mensagem que o amigo recebe | `ASK_PARA_AMIGO` | `rede_indicar` → 💛 Indicar alguém · `menu` → Agora não | BOTÕES |
| Confirmação a quem pediu | `ASK_ENVIADO` | `pedir_amigos` → 👋 Perguntar a outro · `menu` → 🏠 Menu | BOTÕES |

---

## 3. FLUXO "INDICAR PROFISSIONAL" (estado `indicar`)

| Passo (`passo`) | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Início (`contato`) | `INDICAR_INICIO` | `menu` → 🏠 Menu | BOTÕES |
| Contato sem telefone | `INDICAR_PEDIR_TELEFONE` | `menu` → 🏠 Menu | BOTÕES |
| Indicou o próprio número | `INDICAR_SI_MESMO` | `quero_ser_prof` → 💼 Ser profissional · `menu` → 🏠 Menu | BOTÕES |
| Pedir detalhes (`detalhes`) | `INDICAR_DETALHES` | `menu` → 🏠 Menu | BOTÕES |
| Validar (`validar`) | `INDICAR_VALIDAR` | `ind_certo` → ✅ Está certo · `ind_corrigir` → ✏️ Corrigir | BOTÕES |
| Corrigir | `INDICAR_CORRIGIR` + `INDICAR_CORRIGIR_LINHA` | `menu` → 🏠 Menu | BOTÕES |
| Concluído | `INDICAR_LINK` (link 1 toque) + menu | (menu) | LISTA |
| Limite diário atingido | `LIMITE_INDICACOES` | `menu` → 🏠 Menu | BOTÕES |

Mensagem pré-escrita que vai para o profissional indicado: `PRESTADOR_CONVITE_MENSAGEM`.

---

## 4. FLUXO "SER PROFISSIONAL" — onboarding + perfil (estado `perfil_prof`)

### 4.1. Onboarding (via link de indicação OU autocadastro)

| Passo | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Acolhida (chegou por indicação) | `PRESTADOR_ACOLHIDA` | `prest_aceito` → ✅ Aceito e confirmo · `prest_ajustar` → ✏️ Ajustar serviço · `prest_nao` → ⛔ Não desejo | BOTÕES |
| Ajustar serviço | `PRESTADOR_AJUSTAR` | `menu` → 🏠 Menu | BOTÕES |
| Recusou | `PRESTADOR_NAO` + menu | (menu) | LISTA/BOTÕES |
| Autocadastro (menu) | `PRESTADOR_QUERO_SER` | `prest_self` → ✅ Aceito e configuro · `menu` → 🔙 Voltar | BOTÕES |
| Já tem perfil (tentou de novo) | "Você já tem um perfil profissional 💛…" | `prest_editar` → ✏️ Editar perfil · `menu` → 🏠 Menu | BOTÕES |

### 4.2. Configuração do perfil

| Passo | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Pedir descrição | `PRESTADOR_QUERO_SER_OK` (ou `_DUAL` se já era cliente) | `menu` → ✅ Concluir · `outras_opcoes` → ☰ Outras opções | BOTÕES |
| Validar perfil | `PRESTADOR_VALIDAR` | `perfil_ok` → ✅ Confirmar · `perfil_corrigir` → ✏️ Corrigir · `outras_opcoes` → ☰ Outras opções | BOTÕES |
| Corrigir | `PRESTADOR_CORRIGIR` + texto original | `menu` → 🏠 Menu | BOTÕES |
| Salvo — com recomendação | `PRESTADOR_PERFIL_OK` + menu | (menu) | BOTÕES |
| Salvo — sem recomendação (invisível) | `PRESTADOR_PERFIL_INVISIVEL` + menu | (menu) | BOTÕES |

### 4.3. Gestão do perfil (menu do prestador)

| Gatilho (id) | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| `prof_pedir_rec` | `REC_PEDIR_VOCE` + `REC_MENSAGEM_CLIENTE` + menu prestador | (menu) | BOTÕES |
| `prest_pausar` (→ pausado) | "Cadastro *pausado*…" | `prest_pausar` → ▶️ Reativar · `menu` → 🏠 Menu | BOTÕES |
| `prest_pausar` (→ ativo) | "Cadastro *reativado*!…" | `prest_pausar` → ⏸️ Pausar · `menu` → 🏠 Menu | BOTÕES |

---

## 5. FLUXO "CONVIDAR REDE"

| Passo | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Início | "Compartilhe pelo clipe 📎 o contato…" | `gerar_link` → 🔗 Gerar meu link · `menu` → 🏠 Menu | BOTÕES |
| Gerou link genérico | `CONVIDAR_CLIENTE_VOCE` + `CONVITE_MENSAGEM_AMIGO` | (menu principal) | LISTA |
| Compartilhou contatos (links 1 toque) | "Pronto! 💛 Links prontos para N convite(s)…" | `rede_convidar` → 🤝 Convidar mais · `menu` → 🏠 Menu | BOTÕES |

---

## 6. FLUXO "CONFIRMAÇÃO DE CONEXÃO" (vocês se conhecem?)

Aparece na **reabertura do chat** (regra da janela de 24h). Sempre para quem convidou/indicou.

| Origem da conexão | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Convite de cliente | `CONEXAO_PERGUNTA_CONVIDOU` | `conf_sim:{id}` → ✅ Sim, confirmo · `conf_nao:{id}` → ❌ Não conheço | BOTÕES |
| Indicação de profissional | `INDICAR_CONFIRMA_CLIENTE` | `conf_sim:{id}` → ✅ Sim, confirmo · `conf_nao:{id}` → ❌ Não conheço | BOTÕES |
| Recomendar (cliente entrou) | `REC_CONFIRMA_PROF` | `conf_sim:{id}` → ✅ Sim, confirmo · `conf_nao:{id}` → ❌ Não conheço | BOTÕES |
| **Resultado — ambos confirmaram** | `CONEXAO_VALIDADA` + menu | (menu) | LISTA |
| **Resultado — só um confirmou** | `CONEXAO_AGUARDA_OUTRO` + menu | (menu) | LISTA |
| **Resultado — recusou** | `CONEXAO_RECUSADA` + menu | (menu) | LISTA |
| Aviso a quem entrou (não é perguntado) | `CONEXAO_ENTROU_LIGADO` | — | TEXTO |

> Ao validar (ambos os lados), a indicação vira 🟢 e o profissional passa a `ativo`
> (aparece nas buscas).

---

## 7. FLUXO "AVALIAÇÃO" (a IA nunca dá nota)

Aparece na reabertura, depois da confirmação de conexão, só para indicações com ≥ 48h.

| Passo | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Perguntar se usou | `AVALIAR_USOU` | `aval_usei:{id}` → ✅ Usei · `aval_ainda:{id}` → ⏳ Ainda não | BOTÕES |
| Dar nota | `AVALIAR_NOTA` | itens `aval_nota:{id}:5..1` (⭐⭐⭐⭐⭐ 5 … ⭐ 1) | LISTA |
| Agradecer nota | `AVALIAR_OBRIGADA` + menu | (menu) | LISTA |
| Ainda não usou | `AVALIAR_AINDA` + menu | (menu) | LISTA |

---

## 8. FLUXO "MINHA CONTA"

### Submenu — `enviar_submenu_dados` — LISTA ("Abrir")

**Cliente** (texto "Minha conta ⚙️"):

| id | Título | Descrição |
|---|---|---|
| `dados_rede` | 🤝 Minha rede | Suas conexões e o status de cada uma |
| `dados_indicacoes` | 📤 Indicações que fiz | Profissionais que você indicou |
| `gerenciar_rede` | 🚫 Bloquear e gerenciar | Bloquear, remover ou desbloquear |
| `dados_apagar` | 🗑️ Sair / apagar | Encerrar a sua conta |
| `menu` | 🏠 Menu | Voltar ao início |

**Profissional** (texto "Minha conta 💼"): `dados_meu_perfil` (💼 Meu perfil) ·
`dados_recomend` (⭐ Quem me recomendou) · `dados_apagar` (🗑️ Sair / apagar) · `menu` (🏠 Menu)

### Minha rede / gerenciar

| Tela | Mensagem | Botões / itens | Tipo |
|---|---|---|---|
| Minha rede (com pendências) | resumo da rede | `gerenciar_rede` → ✏️ Gerenciar · `dados` → ⚙️ Minha conta · `menu` → 🏠 Menu | BOTÕES |
| Minha rede (sem pendência) | resumo | `dados` → ⚙️ Minha conta · `menu` → 🏠 Menu | BOTÕES |
| Gerenciar rede | "👥 Gerenciar rede" | itens `gerir_aguarda:{id}`, `gerir_convite:{id}`, `dados_rede` → 🏠 Voltar | LISTA |
| Gerenciar pessoa | "O que você quer fazer com *{nome}*?" | `bloquear:{id}` → 🚫 Bloquear · `remover:{id}` → 🗑️ Remover · `gerenciar_rede` → 🔙 Voltar | BOTÕES |
| Aguardando confirmação | "*{nome}* — aguardando confirmação" | `remover:{id}` → 🗑️ Remover · `gerenciar_rede` → 🔙 Voltar | BOTÕES |
| Convite não entrou | "*{nome}* — ainda não entrou" | `deletar_convite:{id}` → 🗑️ Remover · `gerenciar_rede` → 🔙 Voltar | BOTÕES |
| Bloqueados | "🔓 Bloqueados — toque para desbloquear" | itens `desbloquear:{id}` | LISTA |
| Resultado de bloquear/remover/desbloquear | `BLOQUEAR_OK` / `REMOVER_OK` / `DESBLOQUEAR_OK` + menu | (menu) | LISTA |

---

## 9. FLUXO "SAIR / APAGAR" + "Preciso de ajuda"

| Passo | Mensagem | Botões (id → rótulo) | Tipo |
|---|---|---|---|
| Confirmar (cliente/prof) | `SAIR_CLIENTE` / `SAIR_PROFISSIONAL` | `apagar_sim` → ✅ Confirmar saída · `apagar_nao` → 💛 Quero ficar · `ajuda_duracao` → ❓ Preciso de ajuda | BOTÕES |
| Confirmar (híbrido) | `SAIR_HIBRIDO` | `apagar_sim` → ✅ Sair de tudo · `sair_um_perfil` → ⚙️ Ficar com 1 perfil · `apagar_nao` → 💛 Quero ficar | BOTÕES |
| Ficar com 1 perfil | "Qual perfil você quer manter?" | `sair_so_cliente` → 🔍 Só Cliente · `sair_so_prof` → 💼 Só Profissional · `apagar_nao` → 🔙 Voltar | BOTÕES |
| Apagou | `ADEUS` | — | TEXTO |
| Cancelou | "Ufa, não apaguei nada! 😌…" + menu | (menu) | LISTA |
| **Preciso de ajuda** (estado `ajuda`) | `AJUDA_PEDIR_DURACAO` | (espera texto livre) | TEXTO |
| Depois do texto de ajuda | `AJUDA_AGRADECIDA` | `voltar_ajuda` → 🏠 Voltar e continuar · `sair_mesmo` → 🚪 Sair mesmo assim | BOTÕES |

---

## ⚠️ GAPS — possibilidades mapeadas ainda NÃO tratadas (com mensagem proposta)

Estas situações estão previstas no CLAUDE.md (§10 casos de borda) ou surgiram no mapeamento,
mas **ainda não existem no código** — ou existem com problema. Mensagem proposta em cada uma.

| # | Situação | Estado hoje | Mensagem proposta | Botões propostos |
|---|---|---|---|---|
| G1 | **`BOAS_VINDAS_RECOMENDAR` sem botões** | Enviada como TEXTO puro | (manter texto) | `consent_sim` → ✅ Aceito e recomendar · `consent_saber_mais` → ℹ️ Saber mais |
| G2 | **`BOAS_VINDAS_RECOMENDAR` no estilo antigo** (números, "Responda SIM") | Desalinhada das demais | Reescrever no padrão novo (blocos 🔍🤝🙋, sem números) | (idem G1) |
| G3 | **Abandono no meio da indicação** (§10) | Estado fica salvo, mas ao voltar cai no menu | "Você estava indicando *{nome}*. Quer continuar?" | `retomar_indicar` → ▶️ Continuar · `menu` → 🏠 Menu |
| G4 | **Indicar o mesmo profissional 2x** (§10) | Cria/atualiza sem avisar | "Você já indicou *{nome}* 💛 A indicação continua valendo." | `menu` → 🏠 Menu |
| G5 | **"Não conheço" numa confirmação** (possível fraude) | Só marca recusada + `CONEXAO_RECUSADA` | Acolher + registrar sinal: "Obrigada por avisar 💛 Não vou ligar vocês." (já ok) — falta o **sinal anti-fraude** ser logado | — |
| G6 | **Anti-spam de convites** (§10) | Só indicações têm teto (`LIMITE_INDICACOES`) | Reusar `LIMITE_INDICACOES` para convites | `menu` → 🏠 Menu |
| G7 | **k-anonimato do sinal 🟡 pendente** (§6) | Verificar se sinais anônimos respeitam k≥5 | (sem mensagem — regra de exibição) | — |
| G8 | **Contato com só nome, sem número** (§10) | Repergunta o telefone (ok) | `INDICAR_PEDIR_TELEFONE` (já existe) | `menu` → 🏠 Menu |
| G9 | **Texto impróprio/sensível no serviço** (§10) | Não normaliza nem recusa | "Não consegui entender esse serviço 💛 Pode escrever de outro jeito?" | `menu` → 🏠 Menu |
| G10 | **Reabertura com MÚLTIPLAS pendências** | Mostra só a 1ª por vez | (ok por design — uma de cada vez) | — |

---

## Referência rápida — todos os IDs de botão

**Onboarding/consent:** `consent_sim`, `consent_saber_mais`, `prof_quero`, `prof_dual`,
`prof_so`, `prest_self_ok`, `adiar`, `voltar_saber`
**Menu:** `buscar`, `buscar_geral`, `rede_indicar`, `rede_convidar`, `quero_ser_prof`,
`trocar`, `dados`, `outras_opcoes`, `perfil_cliente`, `perfil_profissional`, `menu`,
`gerar_link`
**Busca:** `busca_cidade_toda`, `busca_bairro`, `pedir_amigos`, `ask:{id}`
**Indicar:** `ind_certo`, `ind_corrigir`
**Profissional:** `prest_aceito`, `prest_ajustar`, `prest_nao`, `prest_self`, `prest_editar`,
`prest_pausar`, `prof_pedir_rec`, `perfil_ok`, `perfil_corrigir`
**Conexão/avaliação:** `conf_sim:{id}`, `conf_nao:{id}`, `aval_usei:{id}`, `aval_ainda:{id}`,
`aval_nota:{id}:{1-5}`
**Conta/rede:** `dados_rede`, `dados_indicacoes`, `dados_meu_perfil`, `dados_recomend`,
`gerenciar_rede`, `gerir:{id}`, `gerir_aguarda:{id}`, `gerir_convite:{id}`,
`deletar_convite:{id}`, `bloquear:{id}`, `remover:{id}`, `desbloquear:{id}`, `ver_bloqueados`
**Sair/ajuda:** `apagar_sim`, `apagar_nao`, `sair_um_perfil`, `sair_so_cliente`,
`sair_so_prof`, `ajuda_duracao`, `voltar_ajuda`, `sair_mesmo`
