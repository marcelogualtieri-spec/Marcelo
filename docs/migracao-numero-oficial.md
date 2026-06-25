# Migração: do Sandbox para o número oficial do WhatsApp

> Tira a Doroteia do "modo teste" e a coloca no ar de verdade, com número próprio.
> Via Twilio (onde a Doroteia já vive) + Meta Business.
> Legenda: ✅ feito · ⏳ a fazer · 👤 você · 🤖 eu ajudo/configuro

## Onde você está (checado em 25/06)
- ✅ Conta **Meta Business** — já tem.
- ✅ **Número dedicado** disponível (não usado no app do WhatsApp).
- ⏳ Conta **Twilio** ainda é **trial** → precisa virar paga (Passo 1).

> ⏳ Expectativa: a verificação da Meta costuma levar **alguns dias**. Não é "liga e
> usa na hora". O código quase não muda — o trabalho é de **configuração**.

---

## Passo 1 — 👤 Fazer upgrade da conta Twilio (trial → paga)  ← VOCÊ ESTÁ AQUI
Sem isso, o Twilio não deixa registrar um número oficial.
1. Entre no **Twilio Console** (console.twilio.com).
2. No topo/menu, procure **"Upgrade"** (ou Billing → Upgrade).
3. Adicione um **meio de pagamento** e confirme o upgrade.
4. Recomendado: adicione um crédito inicial pequeno (ex.: US$ 20) pra começar.
> Bônus: isso também **remove o limite diário de mensagens** (o erro 63038 que vimos).

## Passo 2 — 👤+🤖 Iniciar o cadastro do "WhatsApp Sender" no Twilio
1. No Console: **Messaging → Senders → WhatsApp senders** (ou "Try WhatsApp / Register a sender").
2. Clique em **Create new sender**.
3. Vai abrir o **cadastro guiado da Meta (Embedded Signup)** — faça login e
   **conecte a sua conta Meta Business** (a que você já tem).
4. Escolha/conecte a **conta do WhatsApp Business (WABA)**.

## Passo 3 — 👤 Verificação do negócio na Meta (pode levar dias)
- A Meta pode pedir **verificação da empresa** (documentos/dados do negócio).
- Acompanhe pelo **Gerenciador de Negócios → Configurações → Central de Segurança**.
- ⏳ Essa é a parte que **demora** — siga os próximos passos quando ela aprovar.

## Passo 4 — 👤 Registrar o número dedicado + nome de exibição
1. No cadastro, informe o **número dedicado** (o que você separou).
2. A Meta envia um **código** por SMS ou ligação → digite pra confirmar a posse.
   - ⚠️ O número **não pode** estar ativo no app do WhatsApp. Se estiver, apague a
     conta do WhatsApp daquele número antes.
3. Defina o **nome de exibição** (ex.: "Doroteia"). A Meta **aprova** esse nome
   (pode levar de minutos a algumas horas/dias).

## Passo 5 — 🤖 Apontar o webhook do número novo pro nosso servidor
Quando o número estiver ativo:
1. No Twilio, no **WhatsApp Sender** (ou no **Messaging Service** ligado a ele),
   ache **"Endpoint / Webhook" → "When a message comes in"**.
2. Cole a URL do nosso servidor no Render:  `https://SEU-APP.onrender.com/webhook`
   - Método: **HTTP POST**.
3. Salve. (É o mesmo endpoint que o sandbox usa hoje — só passa a valer pro número
   oficial.) 🤖 Eu te ajudo a confirmar a URL certa.

## Passo 6 — 👤+🤖 Testar de verdade
1. Mande uma mensagem pro **número oficial** (não mais o do sandbox).
2. A Doroteia deve responder normalmente — agora sem "join" e sem limite de teste.
3. Confira nos **Logs do Render** (`[ESTADO]`/`[RESP]`) se quiser acompanhar.

---

## O que muda no código?  → quase nada 🎉
- A Doroteia já descobre o **próprio número** pela mensagem (campo `To`), então os
  **links de convite se ajustam sozinhos** pro número oficial.
- Possível melhoria depois: trocar os comandos de texto por **botões clicáveis**
  (o WhatsApp oficial suporta) — fica pra uma próxima rodada.

## Custos a partir daqui (produção real)
- **Twilio + WhatsApp**: cobram por conversa/mensagem (some o limite do trial).
- Mantenha a tabela `searches` de olho no volume (ver `docs/metricas.md`).

## Resumo dos bloqueios em ordem
1. ⏳ Upgrade Twilio (Passo 1) — **agora**.
2. ⏳ Conectar Meta + verificação (Passos 2–3) — a parte que demora.
3. ⏳ Registrar número + nome (Passo 4).
4. ⏳ Webhook + teste (Passos 5–6).
