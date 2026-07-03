# CORE — Como a rede se conecta (conexões, indicações e busca)

> Este é o **coração** da Dorote.ia: sem a rede se conectando de verdade, o app não faz
> sentido. Este documento é a fonte de verdade do modelo de conexão e das garantias de
> LGPD que ele precisa respeitar. **Leia antes de mexer em qualquer coisa de conexão,
> convite, indicação ou busca.**

---

## 1. O modelo de conexão (mútua, validada pelos dois)

Uma conexão entre duas pessoas (A convidou/indicou, B entrou) passa por estados:

1. **Convite pendente** — A convida B (por link com código, ou por número → `pending_invites`
   com o hash do telefone de B). Ainda não há conexão.
2. **Conexão pendente** (`conexoes.status = "pendente"`) — B abre o link/entra. O código cria
   a conexão e **pergunta aos DOIS** "vocês se conhecem?" (`a_confirmou` / `b_confirmou`).
3. **Validada** (`status = "validada"`) — quando **os dois confirmam**. Só então:
   - vira 🟢 na busca (conexão mútua com nome);
   - se for indicação de profissional, a **recomendação é criada** (`_efeitos_conexao_validada`)
     e o profissional passa a **ATIVO** (aparece na busca).
4. **Recusada** (`status = "recusada"`) — se alguém disser "não conheço", ou por bloqueio.

> Regra-mãe: **a conexão só vale quando os DOIS confirmam.** Um lado só não basta.

### Janela de 24h (Meta)
A pergunta "vocês se conhecem?" é enviada aos dois. Para quem está no chat, chega na hora.
Para o outro lado, é um envio **proativo** — que a Meta **bloqueia fora de 24h**. Por isso,
quando a pessoa **reabre o chat**, o código mostra a confirmação pendente ANTES do menu
(`conexoes_pendentes_de`, tratado em `MENU_TRIGGERS`). No piloto **não usamos Template**.

---

## 2. As duas portas + o dedupe

- **Porta A — Autocadastro:** a pessoa vira profissional sozinha. Fica invisível até a 1ª
  recomendação real.
- **Porta B — Indicação:** um cliente indica → cria profissional `convidado`
  (PENDENTE_ENTRADA) + `pending_invite`. Ele só aparece (como isca anônima) até entrar.
- **Dedupe pelo hash do telefone:** entrar pela Porta B depois da A (ou vice-versa) NÃO cria
  registro novo — reaproveita o mesmo.

---

## 3. Para um profissional aparecer na busca (o caso "William")

Um profissional indicado (ex.: Catharina indicou William como eletricista) só aparece na
busca de eletricista de quem procura quando **TUDO** isto acontece:

1. William **entra pelo link** e **aceita os termos** (`prest_aceito`).
2. A conexão Catharina↔William é criada e **os dois confirmam** "vocês se conhecem?".
   → aí a **recomendação Catharina→William** é criada e o provider vira **ATIVO**.
   *(Correção aplicada: antes o `ativo` só vinha quando William configurava o perfil todo;
   agora a recomendação real já o torna visível — §5.3.)*
3. Quem procura precisa ter **conexão validada com Catharina** para ver como 🟢 (com o nome
   dela). Sem isso, aparece como ⚪ rede geral (se k≥5) ou não aparece.

> Se a busca "não trouxe" o profissional, quase sempre falta o passo 2 (um dos dois lados
> não confirmou "vocês se conhecem?"), ou o profissional não entrou/aceitou.

---

## 4. BUGS corrigidos (2026-07-03)

### 4.1 🔴 Conexão nunca criada para quem JÁ era membro (o bug grave dos prints)
**Sintoma:** vocês mandaram os links um pro outro, ambos entraram, a Dorote.ia disse "você
já está aqui" — mas **não conectou**. O mesmo com a Agnes.
**Causa:** o código do convite só era processado para **membro novo** (`if membro is None`
em `_processar_mensagem`). Quem já era membro/consentido tinha o link **ignorado** → nenhum
vínculo.
**Correção:** novo `_conectar_por_link_cliente`, chamado em `_processar_mensagem` para quem
já é membro e já consentiu. Ao abrir um link de convite de cliente (código no texto OU
convite pendente pelo número), abre a conexão mútua na hora e pergunta aos dois. Idempotente
(não recria nem repergunta se já houver conexão).

### 4.2 🔴 Profissional com recomendação real não aparecia na busca
**Causa:** `status = "ativo"` só era gravado quando o profissional configurava o perfil
inteiro. Um profissional indicado, que entrou e teve a conexão validada (recomendação real
criada), continuava `aguardando_perfil` → invisível.
**Correção:** em `_efeitos_conexao_validada`, ao criar a recomendação, o provider passa a
`ativo` (salvo `removido`/`pausado`). Alinha com §5.3: "tem ao menos 1 recomendação → aparece".

---

## 5. Garantias de LGPD deste core (não quebrar)

- **Consentimento antes de expor:** só entra na busca quem entrou e aceitou os termos. O
  profissional indicado fica como **sinal anônimo** (sem nome, sem telefone) até entrar.
- **Telefone:** o número trafega só no código. Na rede/grafo é guardado como **hash HMAC com
  pepper** (`edges`, `pending_invites`). O único telefone compartilhado é o de quem presta
  serviço e **já aceitou** — e agora ele é enviado pelo **código** na busca (não passa pela IA).
- **k-anonimato (≥5):** 🟡 rede pendente e as iscas só aparecem com pelo menos 5 contatos na
  rede; abaixo disso viram ⚪ / somem.
- **Bloqueio:** quem bloqueou/foi bloqueado não conecta nem aparece nas buscas um do outro.
- **SAIR:** apaga cadastro + nome, **anonimiza** (não apaga) as indicações que a pessoa fez,
  e remove o rastro dela (hash + nome) nas redes de terceiros.

---

## 6. Pontos frágeis ainda em aberto (documentar / decidir)

- A validação depende de **os dois confirmarem** "vocês se conhecem?". Se um lado nunca
  reabre o chat / nunca confirma, a conexão fica pendente para sempre. Possível melhoria:
  lembrete de confirmação pendente, ou expiração.
- Convite **por número** (contato específico, sem código) para quem já é membro: hoje o
  `_conectar_por_link_cliente` cobre isso pelo `pending_invite`, mas só dispara quando a
  pessoa manda alguma mensagem. Não há push proativo (janela 24h).
- Teste sempre com **os dois lados confirmando**; senão o 🟢 e a recomendação não nascem.
