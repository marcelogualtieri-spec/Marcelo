# CLAUDE.md — Dorote.ia (correção de fluxos, UX e LGPD)

> Este documento é a **fonte de verdade** dos fluxos da Dorote.ia. Sempre que
> houver conflito entre o código atual e este documento, **este documento vence**.
> Antes de editar qualquer coisa, leia a seção "COMO TRABALHAR NESTE REPO".

---

## COMO TRABALHAR NESTE REPO (leia primeiro)

1. **NÃO gere código antes de mapear o que existe.** Primeiro leia o código
   atual e identifique: onde mora a máquina de estados, o schema do banco
   (Supabase), o parser de contato/vCard, e onde a IA (Haiku) é chamada.
2. Depois de mapear, **produza um plano de alterações** (lista de "arquivo →
   o que muda → por quê") e **pare para eu validar** antes de editar em massa.
3. **Não invente regra de negócio.** Se algo não estiver neste documento,
   pergunte — não preencha o buraco sozinho.
4. Ao final de cada alteração, liste: (a) suposições que fez, (b) pontos onde
   faltou regra, (c) onde a janela de 24h exigirá Template no futuro.

---

## 0. CONTEXTO DO PRODUTO (resumo)

Dorote.ia (sempre com o ponto, nunca "Doroteia") é uma **central de indicações
de confiança no WhatsApp**. A pessoa pede um serviço e o sistema busca
recomendações feitas por quem ela conhece. Piloto: **São Paulo/SP**.
Stack: WhatsApp Cloud API + Python/Flask (Render) + Supabase + IA Claude Haiku.

---

## 1. REGRA-MÃE DE ARQUITETURA (a mais importante)

**O CÓDIGO manda. A IA só interpreta texto livre.**

- O **código** é dono do fluxo, do estado, das transições, das regras de negócio,
  dos contadores e de toda ação sensível (registrar indicação, gerar link,
  confirmar conexão, apagar dados).
- A **IA (Haiku)** faz **apenas uma coisa**: receber um texto livre do usuário e
  devolver **campos estruturados** (ex.: `{servico, bairro, detalhe}`). Nada além
  disso.
- A IA **NUNCA**: dá nota/avaliação, confirma cadastro, avança etapa, decide o que
  o produto faz ou não faz, calcula contador, escolhe caminho de navegação,
  inventa link.

> ❌ Sintomas atuais a eliminar: bot deu "nota 5 ⭐" sozinho; cadastro de uma
> pessoa vazou para o fluxo de outra; contador "Indicações: 1" errado; bot se
> contradiz sobre existir ou não autocadastro. Tudo isso é IA no controle —
> deve sair.

---

## 2. PRINCÍPIOS DE UX INEGOCIÁVEIS (valem em TODO passo)

1. **Navegação e decisão = sempre botão ou comando claro.** A IA nunca deixa a
   pessoa "no escuro" digitando à toa para escolher um caminho.
2. **Texto livre só para CONTEÚDO** (descrever o serviço, o porquê da indicação,
   o que busca). **Nunca** para decidir caminho. Decisão é botão.
3. **Mensagens curtas, organização simples**, legíveis por qualquer público
   (todas as classes sociais). Frases curtas, palavras concretas, zero jargão,
   zero anglicismo.
4. **Linguagem 100% neutra de gênero.** Proibido: "o/a profissional", "ele/ela",
   "prestadora", "artesã", "conectadas", "registrada", "indicado/a". Use:
   "a pessoa", "quem presta o serviço", "esse contato", "quem você indicou",
   construções impessoais. Só use a forma "(a)" quando NÃO houver alternativa
   neutra (raro).
5. **SAIR**: funciona como comando digitado **a qualquer momento** E fica visível
   em **Outras opções → Minha conta → Sair/apagar**. Fácil de achar, mas **não**
   aparece em toda mensagem.
6. Emojis com moderação. 💛 é o principal (😊 🤝 🔒 🔍 💼 quando fizer sentido).

---

## 3. REGRAS DO WHATSAPP BUSINESS (técnicas, obrigatórias)

- **Máximo 3 botões** de resposta rápida por mensagem. Rótulos **≤ 20 caracteres**.
- Quando precisar de mais de 3 opções, use **list message** (até 10 itens).
- **Janela de 24h**: notificações proativas só chegam livremente dentro de 24h da
  última mensagem da pessoa. Fora disso, exigiria Template aprovado pela Meta.
  **No piloto NÃO usamos Template** → ver regra de "confirmação pendente" (seção 7).
- Usar indicador de "digitando…" para o chat não parecer travado.

---

## 4. REGRAS DE LGPD INEGOCIÁVEIS

1. **A IA nunca recebe número de telefone.** Antes de qualquer chamada ao modelo,
   o telefone é extraído pelo código e substituído por uma ficha (`[CONTATO_1]`).
   O número cru só trafega no código determinístico.
2. **Telefone guardado via hash com PEPPER secreto** (chave fora do banco, em
   variável de ambiente no Render — idealmente secret manager). **Não** usar
   SHA256 puro nem HMAC com a chave no mesmo banco: número de celular BR é
   enumerável e seria reversível por força bruta. O hash é a chave de dedupe.
3. **Consentimento travado** (ver seção 6.D): dado de pessoa que ainda não entrou
   nunca é exposto.
4. **Telefone pessoal nunca é repassado.** O único telefone compartilhado em
   busca é o de quem presta serviço **e já aceitou os termos**.
5. **SAIR**: apaga o cadastro da pessoa e o nome dela. Indicações que ela fez
   **não são deletadas** — são **anonimizadas** (perdem o nome de quem indicou e
   viram ⚪ rede geral). A mensagem do SAIR deve dizer isso com honestidade
   (ver seção 9), nunca prometer "apago tudo" se o dado persiste anonimizado.
6. **Bloquear autoindicação**: ninguém pode indicar o próprio número.

---

## 5. MODELO DE PERFIL E DADOS

### 5.1 Perfis
- Toda conta nasce **Cliente** (busca, indica, convida, monta rede).
- **Profissional** é um perfil adicional na **mesma conta/mesmo chat**. No menu,
  a pessoa alterna entre as visões 🔍 Cliente e 💼 Profissional.
- **Decisão fixa:** autocadastro de Profissional **EXISTE**, MAS o perfil fica
  **INVISÍVEL na busca até receber a 1ª recomendação real de cliente.**

### 5.2 Duas portas para virar Profissional
- **Porta A — Autocadastro:** a pessoa escolhe "Ser profissional", aceita os
  termos profissionais e configura o perfil. Fica **invisível** na busca até a
  1ª recomendação de cliente.
- **Porta B — Indicação:** um cliente indica a pessoa. Cria um profissional em
  estado **PENDENTE** (ver seção 6).
- **Dedupe pelo hash do telefone:** se a pessoa já se autocadastrou (Porta A) e
  depois é indicada (Porta B), **não criar registro novo** — a indicação conta
  como a "1ª recomendação" que a torna visível. Mesma regra ao contrário.

### 5.3 Estados de um profissional
- `AUTOCADASTRO_INVISIVEL` — criou perfil, ainda sem recomendação → não aparece.
- `PENDENTE_ENTRADA` — foi indicado, ainda não entrou pelo link → só "sinal
  anônimo" (seção 6.D), sem nome, sem telefone.
- `ATIVO` — entrou/consentiu e tem ao menos 1 recomendação → aparece com contato.

---

## 6. OS NÍVEIS DE CONFIANÇA NA BUSCA

Resultado de busca tem dois tipos de item:

**(a) Contatos liberados** (profissional `ATIVO`), com nível de confiança:
- 🟢 **Conexão mútua validada** — quem indicou tem conexão confirmada com quem
  busca → mostra o **nome** de quem indicou.
- 🟡 **Da rede, pendente (anônimo)** — alguém que a pessoa adicionou mas que ainda
  não confirmou conexão → anônimo. **Só aparece com k-anonimato: mínimo ~5
  contatos pendentes na rede.** Abaixo disso, não exibir este nível.
- ⚪ **Rede geral** — sem relação com quem busca → anônimo.

**(b) Sinais anônimos de indicação pendente** (profissional `PENDENTE_ENTRADA`):
- Exibir só como: *"Alguém da sua rede indicou um eletricista na zona oeste."*
  **Sem nome, sem telefone.** O contato só destrava quando a pessoa indicada
  entra e aceita os termos.
- **Também sujeito a k-anonimato (~5 conexões na rede):** abaixo disso, não
  mostrar o sinal anônimo (em rede pequena ele entregaria quem indicou).

---

## 7. MÁQUINAS DE ESTADO DOS FLUXOS

> Regra geral para TODOS os fluxos abaixo:
> - Cada fluxo é uma **transação isolada** com identificador próprio. O contexto
>   de um fluxo **nunca** respinga no próximo.
> - Se um campo falhar (ex.: telefone não veio), **reperguntar DENTRO do fluxo**.
>   **Nunca** cair no menu principal por causa de falha.
> - O menu principal só aparece por **ação explícita** (botão/comando MENU).

### 7.1 MENU PRINCIPAL
Botões (máx 3): `Indicar profissional` · `Convidar quem confio` · `Outras opções`
"Outras opções" → list message: 🔍 Buscar · 💼 Ser profissional · ⚙️ Minha conta
"Minha conta" → list: 📋 Ver meus dados · 🗑️ Sair/apagar · 🏠 Menu

> ❌ O botão JÁ define a intenção. Se a pessoa clicou "Indicar profissional",
> **NÃO** perguntar de novo "é prestador ou é pra sua rede?". Essa pergunta
> redundante (vista nos prints) deve sumir.

### 7.2 FLUXO "INDICAR PROFISSIONAL"
- `RECO_INICIO`: pede o contato (mensagem 1, seção 8). Aceita vCard do clipe
  (extrai nome+telefone) OU texto. Se não houver telefone → reperguntar gentil,
  sem sair do passo. Salva nome (visível à IA) + telefone tokenizado/hash.
- `RECO_DADOS`: mensagem 2 (seção 8) — pede serviço + região + detalhe em UM envio
  (estilo grupo). A IA extrai `{servico, bairro, detalhe}` do texto livre.
  Região: perguntar **bairro/região de São Paulo**, NUNCA "qual cidade".
- `RECO_CONFIRMA`: mensagem 3 (resumo) + botões `Está certo` / `Corrigir`.
  "Corrigir" → mensagem 3a, pessoa reenvia corrigido.
- `DEDUPE` (antes de gerar link): buscar por hash do telefone.
  - já `ATIVO`: não gerar novo link; criar só a conexão pendente + a indicação;
    seguir para confirmação quando aplicável.
  - já `PENDENTE_ENTRADA` (outra pessoa já indicou): agregar esta indicação ao
    mesmo profissional (não duplicar); reaproveitar o mesmo link.
  - não existe: criar `PENDENTE_ENTRADA` e gerar link **tipo=profissional**.
- `GERA_LINK`: mensagem 4 com o link. Estado da indicação = `PENDENTE_ENTRADA`.

### 7.3 FLUXO "CONVIDAR QUEM CONFIO" (rede / cliente)
- Pede contato pelo clipe OU o link de divulgação.
- Gera link **tipo=cliente** (abre conexão mútua, NÃO cadastro de profissional).
- Mensagens: ver seção 8 (convite cliente).
- ❌ Nunca entregar "link de cliente" quando o caso era profissional, nem o
  contrário. O tipo do link é determinado pelo fluxo, não pela IA.

### 7.4 ENTRADA VIA LINK
- Link `tipo=cliente` → onboarding de Cliente + cria conexão `PENDENTE_CONFIRMACAO`
  entre quem convidou e quem entrou (os dois precisam confirmar que se conhecem).
- Link `tipo=profissional` → onboarding profissional (aceite dos termos
  profissionais + configurar perfil). Destrava o contato e cria
  `PENDENTE_CONFIRMACAO` com quem indicou.

### 7.5 CONFIRMAÇÃO DE CONEXÃO (decisão 4 — pendente fora das 24h)
- Quando a pessoa entra, deve-se perguntar a quem indicou/convidou: mensagem 5
  (seção 8) com botões `Sim, confirmo` / `Não conheço`.
- **Se estiver fora da janela de 24h** (a pessoa pode entrar dias depois):
  **NÃO** tentar enviar proativo. **Guardar a confirmação como pendente** e
  **exibi-la assim que a pessoa reabrir o chat** (antes do menu).
- `Sim, confirmo` → conexão `VALIDADA`; indicação passa a contar como 🟢 e o
  contato pode ser entregue em buscas.
- `Não conheço` → não validar; **não** expor contato; registrar sinal (possível
  fraude/erro); tratar com acolhimento.

### 7.6 AUTOCADASTRO "SER PROFISSIONAL"
- Aceite dos termos profissionais (`Aceito e configuro` / `Voltar`).
- Coleta perfil (serviço, região, diferenciais) — **uma instrução clara**, com
  comando para encerrar (ex.: digitar `MENU` como **comando**, não enfiado no
  meio de texto livre).
- Perfil entra como `AUTOCADASTRO_INVISIVEL`. Mensagem honesta (mensagem 6).

### 7.7 BUSCAR
- Pessoa diz o que precisa (texto livre = conteúdo, ok). Região: SP por padrão,
  perguntar bairro se necessário (nunca "cidade").
- Retorna conforme seção 6: contatos liberados (com nível) + sinais anônimos
  (respeitando k≥5). Se nada → mensagem de "sem resultado" + convite para
  convidar a rede / registrar indicações.

### 7.8 MINHA CONTA
- `Ver meus dados`: nome, nº de contatos na rede (sem expor números), nº de
  indicações feitas. **Todos os contadores vêm do banco**, nunca de chute da IA.
- `Sair/apagar`: confirmar antes; aplicar regra da seção 4.5 (anonimiza
  indicações, apaga cadastro/nome).

---

## 8. COPY DOS PASSOS PRINCIPAIS (texto exato, neutro de gênero)

**Mensagem 1 — início de indicar profissional**
> Que bom! Quem você quer indicar? 💛
> Toque no clipe 📎 (ou no ➕) e envie o contato dessa pessoa.
> Se preferir, escreva aqui o nome e o telefone — assim: **(11) 98765-4321**.
> Pode mandar do seu jeito, depois eu confirmo. 💛

**Mensagem 2 — serviço + região + detalhe (um envio)**
> Anotei: **[Nome]** 💛
> Agora me conta em uma mensagem, como se estivesse indicando num grupo:
>
> 🔧 O que essa pessoa faz? (ex.: eletricista, manicure, aulas de inglês)
> 📍 Em que parte de São Paulo atende? (um bairro, vários, a cidade toda — ou "não sei")
> 💬 Por que você indica? Isso ajuda muito quem procura. (ex.: "fez os doces do batizado, caprichou e foi pontual; também faz salgados")
>
> Pode escrever do seu jeito 💛

**Mensagem 3 — validação**
> Confere pra mim? 💛
> 👤 [Nome]
> 🔧 [Serviço]
> 📍 [Região]
> 💬 "[detalhe]"
> [ Está certo ] [ Corrigir ]

**Mensagem 3a — corrigir**
> Sem problema 💛 Aqui está o que anotei — me reenvie corrigido:
> [Nome] · [Serviço] · [Região] · [detalhe]

**Mensagem 4 — link gerado (profissional)**
> Prontinho! 💛 Este é o link de convite para **[Nome]** entrar na Dorote.ia:
> [link]
> É só encaminhar para essa pessoa. Quando ela entrar, vou te chamar para
> confirmar que vocês se conhecem — aí sua indicação passa a valer na rede. 💛

**Mensagem 5 — pedir confirmação a quem indicou**
> Boa notícia! 💛 **[Nome]**, que você indicou, entrou na Dorote.ia.
> Vocês se conhecem e você confia no trabalho dessa pessoa?
> [ Sim, confirmo ] [ Não conheço ]

**Mensagem 6 — autocadastro profissional invisível (decisão 1)**
> Seu perfil de profissional está criado 💛
> Assim que a primeira pessoa recomendar o seu trabalho, você começa a aparecer
> para a rede. É a recomendação de verdade que dá força ao seu perfil aqui.

**Convite "Convidar quem confio" — mensagem que VOCÊ vê**
> Boa! 💛 Quanto mais gente de confiança na sua rede, melhores as indicações que
> você recebe.
> Encaminhe este convite para quem você confia:
> [link]
> Quando a pessoa entrar, vou perguntar se vocês se conhecem. Se as duas
> confirmarem, começam a trocar indicações. 💛

**Convite "Convidar quem confio" — texto pronto para encaminhar**
> Oi! 💛 Tô usando a Dorote.ia, uma central de indicações de confiança no
> WhatsApp. Serve pra achar gente boa — dentista, eletricista, reforço escolar… —
> indicada por quem a gente conhece, sem a bagunça dos grupos.
> Entra pelo meu convite pra gente trocar indicações:
> [link]

**SAIR — confirmação (honesta sobre o que acontece)**
> Tem certeza que quer sair? 💛
> Vou apagar o seu cadastro e o seu nome. As indicações que você fez continuam
> ajudando a rede, mas de forma anônima (sem o seu nome).
> [ Sim, sair ] [ Cancelar ]

---

## 9. CORREÇÕES ESPECÍFICAS DOS BUGS OBSERVADOS

1. **Vazamento de contexto entre fluxos** → transação isolada por fluxo (7).
2. **Falha joga no menu** → falha repergunta dentro do fluxo (7).
3. **vCard "número não veio"** → parser de vCard funcional + fallback gentil
   "manda só o número com DDD" sem sair do passo.
4. **Contadores errados** → vêm do banco, nunca da IA (7.8).
5. **Pergunta "qual cidade"** → trocar por bairro/região; piloto é só SP.
6. **Formulário em lista ("1. Nome 2. Telefone 3. Cidade")** → eliminar; usar o
   fluxo único clipe-primeiro (7.2 / mensagens 1–3).
7. **Pergunta redundante "prestador ou rede?" após o botão** → eliminar (7.1).
8. **Contradição sobre autocadastro** → resolver com a regra fixa da seção 5.
9. **"nota 5 ⭐" inventada** → IA não dá nota; nota só por fluxo explícito.
10. **Gênero vazando** → varredura de copy conforme seção 2.4.
11. **"digite MENU" no meio de texto livre** → MENU é comando/botão claro, não
    instrução solta.
12. **Indicação expõe pessoa sem consentimento** → estado PENDENTE travado (4/6).

---

## 10. CASOS DE BORDA (tratar todos)

- Clipe sem número (só nome) → pedir o telefone, sem sair do passo.
- Pessoa abandona no meio → salvar progresso; ao voltar: "Quer continuar a
  indicação de [Nome]?" com botões.
- Mesma pessoa indica o mesmo profissional 2x → não duplicar; avisar que já está
  registrado.
- Profissional indicado nunca entra → fica `PENDENTE_ENTRADA`; nunca aparece com
  contato; só sinal anônimo (se k≥5).
- Texto de serviço impróprio/sensível → não logar cru; normalizar categoria ou
  recusar com gentileza.
- Anti-spam → limite de indicações/convites por pessoa por janela de tempo.
- Rede pequena (< ~5) → não exibir 🟡 nem sinais anônimos (k-anonimato).

---

## 11. ENTREGÁVEL ESPERADO

1. Plano de alterações (arquivo → mudança → motivo) **antes** de editar em massa.
2. Implementação: máquina de estados por fluxo; IA restrita a extrair campos;
   tokenização + hash com pepper; dedupe por telefone; estados de profissional;
   k-anonimato; confirmação pendente fora das 24h; copy neutra das seções 8 e 9.
3. Relatório final: suposições feitas, regras que faltaram, pontos que exigirão
   Template no futuro.

## 12. O QUE NUNCA FAZER
- IA decidir caminho, dar nota, confirmar cadastro ou inventar contador.
- Expor nome/telefone de quem ainda não entrou e aceitou os termos.
- Cair no menu por causa de falha de campo.
- Perguntar "qual cidade" (piloto = SP) ou repetir pergunta que o botão já decidiu.
- Usar marca de gênero. Usar SHA256 puro/HMAC sem pepper para telefone.
