# Migração: para o WhatsApp oficial via API da Meta (sem Twilio)

> A Doroteia agora fala direto com a **WhatsApp Cloud API da Meta** — sem Twilio,
> sem taxa de intermediário, com cota grátis e número de teste na hora.
> Legenda: ✅ feito · ⏳ a fazer · 👤 você · 🤖 eu ajudo/configuro

## Onde você está
- ✅ Conta **Meta Business** — já tem.
- ✅ **Número dedicado** disponível (não usado no app do WhatsApp).
- ✅ Código já adaptado pra Cloud API (não usa mais Twilio).

---

## PARTE A — Testar de graça agora (número de teste da Meta)
Dá pra validar tudo **hoje**, sem custo e sem esperar verificação.

### A1 — 👤 Criar o App na Meta
1. Vá em **developers.facebook.com** → **My Apps** → **Create App**.
2. Tipo do app: **Business**. Ligue ao seu **Meta Business**.
3. No app, em **Add products**, adicione **WhatsApp** → **Set up**.

### A2 — 👤 Pegar o número de teste, o token e o phone number id
Na tela **WhatsApp → API Setup** aparecem:
- Um **número de teste** (From) já pronto — e um **Phone number ID**.
- Um **Temporary access token** (vale ~24h — serve pro teste).
- Um campo pra cadastrar **até 5 números** que podem receber (To). Adicione o seu.

### A3 — 🤖+👤 Configurar as variáveis no Render
No Render → serviço **doroteia-ia** → **Environment**, adicione:
| Variável | Valor |
|---|---|
| `WHATSAPP_TOKEN` | o **access token** da tela API Setup |
| `WHATSAPP_VERIFY_TOKEN` | uma palavra que **você** inventa (ex.: `doroteia-2026`) |
| `WHATSAPP_APP_SECRET` | *(opcional)* o **App Secret** (App → Settings → Basic) |

> Pode **apagar** as antigas `TWILIO_*` — não são mais usadas.
> Salve e espere o Render voltar a **Live** (o `VERIFY_TOKEN` precisa estar no ar
> antes do próximo passo).

### A4 — 👤 Ligar o webhook na Meta
Na tela **WhatsApp → Configuration → Webhook**:
1. **Callback URL:** `https://doroteia-ia.onrender.com/webhook`
2. **Verify token:** exatamente o mesmo que você pôs em `WHATSAPP_VERIFY_TOKEN`.
3. Clique **Verify and save** (a Meta vai bater no nosso servidor e confirmar). ✅
4. Em **Webhook fields**, clique **Manage** e **assine o campo `messages`**.

### A5 — 👤 Testar
1. Do seu WhatsApp, mande uma mensagem pro **número de teste**.
2. A Doroteia deve responder normal — sem "join", sem limite de sandbox. 🎉
3. Acompanhe nos **Logs do Render** (`Mensagem de...`, `[RESP]`).

---

## PARTE B — Número oficial de verdade (quando o teste estiver ok)
O número de teste só fala com 5 contatos. Pra abrir pros 40, registre o **número
dedicado**:

### B1 — 👤 Adicionar o número dedicado
Em **WhatsApp → API Setup → "Add phone number"** (ou no WhatsApp Manager):
1. Informe o **número dedicado** (não pode estar ativo no app do WhatsApp).
2. Confirme com o **código** que chega por SMS/ligação.
3. Defina o **nome de exibição** ("Doroteia") → a Meta **aprova** (minutos a dias).

### B2 — 👤 Verificação do negócio (pode levar dias)
A Meta pede **verificação da empresa** pra liberar volume.
Acompanhe em **Gerenciador de Negócios → Configurações → Central de Segurança**.
> ⏳ Essa é a parte que demora.

### B3 — 🤖+👤 Trocar pelo token PERMANENTE (importante!)
O token do teste expira em ~24h. Pro número oficial, gere um que **não expira**:
1. **Business Settings → Users → System Users** → crie um **System User** (Admin).
2. **Add Assets** → o seu **App do WhatsApp** (controle total).
3. **Generate new token** → escolha o app → permissões
   **`whatsapp_business_messaging`** e **`whatsapp_business_management`**.
4. Copie o token e atualize `WHATSAPP_TOKEN` no Render.
5. Pegue o **Phone number ID** do número oficial (o código já usa o que vem em
   cada mensagem, então não precisa configurar à mão).

### B4 — 👤 Apontar/confirmar o webhook
Mesmo webhook da Parte A (já configurado). Só confirme que o campo **`messages`**
continua assinado pro número oficial.

---

## O que muda no código?  → nada 🎉
- A Doroteia já descobre o **próprio número** (campo `metadata`), então os **links
  de convite** se ajustam sozinhos pro número oficial.
- Já está pronta pra **botões clicáveis** (a Cloud API suporta) — melhoria futura.

## Custos
- **Cloud API da Meta:** cota mensal grátis de conversas; depois, valor baixo por
  conversa. Pra 40 pessoas, tende a **R$ 0 / quase nada**.
- Sem Twilio, sem taxa de intermediário.

## Resumo dos bloqueios em ordem
1. ⏳ Parte A (criar app + token + webhook) — **dá pra fazer hoje, de graça**.
2. ⏳ Registrar número dedicado + nome (B1).
3. ⏳ Verificação do negócio na Meta (B2) — a parte que demora.
4. ⏳ Token permanente (B3).
