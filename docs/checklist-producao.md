# Checklist de Produção — Doroteia

> Estado atual do produto e o que ainda falta.
> Legenda: ✅ feito · ⏳ falta · 👤 tarefa sua · 🤖 eu te ajudo/codo

---

## ✅ Produto — o que está funcionando

### Onboarding
- ✅ Pessoa nova entra: detecta convite (por código no texto ou por hash do telefone)
- ✅ Boas-vindas com IA: cita quem convidou, explica a Doroteia em 3–4 linhas, envia botões "Pode ser! 💛" / "Quero saber mais"
- ✅ Consentimento (LGPD): só após aceite explícito — botão ou texto afirmativo
- ✅ Pós-consent: boas-vindas calorosas (≤3 linhas), convida a compartilhar contatos, pergunta o que precisa

### Busca de indicações (verde / amarelo / vermelho)
- ✅ Busca por serviço + cidade (bairro opcional — se faltar, busca na cidade inteira)
- ✅ Vínculo de confiança: por convite (invited_by) OU por hash de contato (edges)
- ✅ Vários indicadores do mesmo prestador aparecem juntos com prova social ("Tanto João quanto Maria indicaram o mesmo!")
- ✅ Ordenação por nota média (mais bem avaliados primeiro)
- ✅ Escopo amplo: médico, escola, advogado, prestador, professor — qualquer indicação

### Rede de contatos
- ✅ Adicionar + convidar em passo único: compartilha card → IA detecta quem já é membro + gera convite individual por pessoa que ainda não usa
- ✅ Link curto `/c/<code>` por contato — número nunca vai pra IA
- ✅ Grafo de privacidade: contatos gravados só como HMAC-SHA256

### Recomendações
- ✅ Indicar via card de contato (ficha [CONTATO_n])
- ✅ Indicar digitando o telefone com DDD
- ✅ Bairro opcional na indicação — se faltar, considera que atende na cidade inteira

### Avaliação (qualifica a rede)
- ✅ Avaliação 1–5 estrelas após usar um indicado
- ✅ "Ainda não usei" — marca como dispensado, para de perguntar
- ✅ Nota média recalculada em providers (desnormalizada para ranquear rápido)

### Follow-up proativo
- ✅ GitHub Actions roda todo dia às 10h BRT → POST /cron/follow-up
- ✅ 7 dias após mostrar uma indicação, Doroteia pergunta "chegou a usar? como foi?"
- ✅ Máximo 50 mensagens por rodada, uma por membro
- ✅ follow_up_at evita duplicatas; status='avaliada' evita reperguntar

### Painel do usuário
- ✅ "O que já indiquei?" → `ver_minhas_indicacoes` (com notas)
- ✅ "Quem da minha rede está aqui?" → `ver_minha_rede`
- ✅ "O que busquei antes?" → `ver_minhas_buscas` (últimas 10, com 🟢🟡🔴)
- ✅ Dados gerais + opção de apagar tudo (LGPD)

### Segurança / infraestrutura
- ✅ Assinatura X-Hub-Signature-256 da Meta validada em todo POST
- ✅ Cron protegido por X-Cron-Secret
- ✅ RLS ligado no Supabase
- ✅ Segredos em variáveis de ambiente (nunca no código)
- ✅ WhatsApp Cloud API direta (sem intermediário/BSP pago)
- ✅ Encurtador interno de links (/c/<code>) — sem exposição de números nas URLs

---

## ⏳ Falta — tarefas suas (👤)

1. **👤 Número oficial do WhatsApp** — sair do sandbox da Meta. Precisa de:
   - Conta **Meta Business** (Gerenciador de Negócios)
   - **Verificação da empresa** pela Meta
   - Um **número dedicado** (que NÃO esteja no app do WhatsApp)
   - Nome de exibição aprovado ("Doroteia")
   - *Leva alguns dias. 🤖 Eu te guio clique a clique quando quiser começar.*

2. **👤 Configurar variáveis de ambiente no Render**
   Faltam as novas (as demais provavelmente já estão):
   - `WHATSAPP_PHONE_NUMBER_ID` — ID do número do bot (visível no painel Meta ou nos logs do webhook)
   - `CRON_SECRET` — string aleatória que você inventar (ex.: `openssl rand -hex 32`)
   - `PUBLIC_BASE_URL` — deve estar como `https://doroteia-ia.onrender.com`

3. **👤 Configurar CRON_SECRET no GitHub Secrets**
   Mesma string que colocou no Render → repositório → Settings → Secrets → Actions → `CRON_SECRET`

4. **👤 Rodar as migrações no Supabase** (se ainda não fez)
   Abra o SQL Editor do Supabase e cole o conteúdo de `db/migrations-todas.sql`.
   É seguro rodar mais de uma vez (tudo usa `IF NOT EXISTS`).

5. **👤 Backup da `CONTACT_HASH_KEY`**
   Guarde numa cópia segura (gerenciador de senhas). Se perder, o grafo de contatos quebra — os hashes deixam de casar e ninguém se "conhece" mais.

6. **👤 Plano pago no Render** (recomendado)
   O plano grátis "dorme" após inatividade e demora ~50s pra acordar — a primeira mensagem pode falhar ou dar timeout no webhook da Meta. Um plano básico (~US$ 7/mês) mantém o servidor sempre acordado.

7. **👤 Revisão do DPO** (LGPD)
   Entregar `docs/privacidade-hash.md` pra validação jurídica.
   Pontos abertos: base legal para o telefone do prestador, política de retenção, canal de exercício de direitos.

---

## ⏳ Falta — onde eu te ajudo (🤖)

1. **🤖 Guiar o cadastro do número oficial** passo a passo.
2. **🤖 Preparar entrega pro DPO** (resumo executivo + perguntas para o jurídico).
3. **🤖 Teste com 3–5 amigos reais** antes dos 40 — pra pegar surpresas de linguagem e de fluxo. Eu ajudo a interpretar os logs.
4. **🤖 Processamento assíncrono**: hoje a Doroteia responde de forma síncrona (dentro dos 20s do webhook da Meta). Pros 40 usuários está ótimo. Se escalar muito, separamos: responde "ok" na hora e processa em background. *Não é urgente.*

---

## 💰 Custos estimados (quando for ao ar)

| Serviço | Custo |
|---|---|
| WhatsApp Cloud API | Gratuito até 1.000 conversas/mês; depois por conversa (~US$ 0,01–0,05 BR) |
| Claude Haiku (Anthropic) | Frações de centavo por mensagem interpretada |
| Render | Grátis no sandbox; ~US$ 7/mês pro plano que não dorme |
| Supabase | Grátis cobre bem o beta (500 MB, 50k linhas) |
| GitHub Actions | Grátis para repositórios públicos / 2.000 min/mês nos privados |

> Para 40 pessoas, tudo isso é muito baixo. A tabela `searches` (ver `docs/metricas.md`) ajuda a estimar volume quando escalar.

---

## 🚦 Resumo: o que fazer agora pra ativar o follow-up

1. `WHATSAPP_PHONE_NUMBER_ID` no Render
2. `CRON_SECRET` no Render **e** no GitHub Secrets
3. Migração `db/migrations-todas.sql` rodada no Supabase
4. Deploy do código mais recente no Render (branch `claude/optimistic-shannon-6p9ig5` → main)

O número oficial e o DPO podem seguir em paralelo enquanto você testa. 💛
