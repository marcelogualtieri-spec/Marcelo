# Checklist de Produção — Doroteia

> Estado atual do produto e o que ainda falta.
> Legenda: ✅ feito · ⏳ falta · 👤 tarefa sua · 🤖 eu te ajudo/codo

---

## ✅ Produto — o que está funcionando

### Onboarding
- ✅ Pessoa nova entra: detecta convite (por código no texto ou por hash do telefone)
- ✅ 1º contato: a IA se apresenta, explica o que faz **e por que precisa do consentimento**, com botões "Pode ser! 💛" / "Quero saber mais"
- ✅ "Quero saber mais" / dúvida / tentar avançar: explica **tudo** que dá pra fazer + privacidade + importância do consent (não repete a perguntinha seca)
- ✅ Trava de segurança: sem consentimento, o modelo só tem as ferramentas `registrar_consentimento` e `enviar_botoes` — nenhuma ação real vaza antes do "ok"
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

### Mensagens proativas
- ✅ Follow-up: 7 dias após mostrar uma indicação, Doroteia pergunta "chegou a usar? como foi?" (cron diário 10h BRT → POST /cron/follow-up)
- ✅ Loop de convite: quando um contato convidado entra, o convidante é avisado ("Fulano entrou pelo seu convite!")
- ✅ Alerta de busca vermelha: quem buscou e não achou nada é avisado quando aparece uma indicação nova daquele serviço na cidade
- ✅ Nudge pós-onboarding: lembra quem consentiu há 2+ dias mas não trouxe nenhum contato
- ✅ Máximo 50 mensagens por rodada, uma por membro; flags (`follow_up_at`, `alerta_enviado`, `nudge_contatos_at`) evitam duplicatas

### Painel do usuário
- ✅ "O que já indiquei?" → `ver_minhas_indicacoes` (com notas)
- ✅ "Quem da minha rede está aqui?" → `ver_minha_rede`
- ✅ "O que busquei antes?" → `ver_minhas_buscas` (últimas 10, com 🟢🤝🟡🔴)
- ✅ Dados gerais + opção de apagar tudo (LGPD)

### Segurança / infraestrutura
- ✅ Assinatura X-Hub-Signature-256 da Meta validada em todo POST
- ✅ Cron protegido por X-Cron-Secret
- ✅ RLS ligado no Supabase
- ✅ Segredos em variáveis de ambiente (nunca no código)
- ✅ WhatsApp Cloud API direta (sem intermediário/BSP pago)
- ✅ Encurtador interno de links (/c/<code>) — sem exposição de números nas URLs

### Deploy / configuração
- ✅ Número oficial do WhatsApp aprovado e ativo
- ✅ Variáveis de ambiente configuradas no Render (`WHATSAPP_PHONE_NUMBER_ID`, `CRON_SECRET`, etc.)
- ✅ `CRON_SECRET` configurado no GitHub Secrets
- ✅ Migrações v2–v9 rodadas no Supabase
- ✅ Revisão do DPO (LGPD) concluída

---

## ⏳ Falta — onde eu te ajudo (🤖)

1. **🤖 Backup da `CONTACT_HASH_KEY`** — se ainda não fez, guarde uma cópia em gerenciador de senhas. Se perder, o grafo de contatos quebra (os hashes deixam de casar).
2. **🤖 Teste com 3–5 amigos reais** antes de abrir pros 40 — pra pegar surpresas de linguagem e de fluxo. Eu ajudo a interpretar os logs.
3. **🤖 Processamento assíncrono** — hoje a Doroteia responde de forma síncrona (dentro dos 20s do webhook da Meta). Pros 40 usuários está ótimo. Se escalar muito, separamos: responde "ok" na hora e processa em background. *Não é urgente.*

---

## 💰 Custos (em produção)

| Serviço | Custo |
|---|---|
| WhatsApp Cloud API | Gratuito até 1.000 conversas/mês; depois por conversa (~US$ 0,01–0,05) |
| Claude Haiku (Anthropic) | Frações de centavo por mensagem interpretada |
| Render | ~US$ 7/mês (plano que não dorme) |
| Supabase | Grátis cobre bem o beta (500 MB, 50k linhas) |
| GitHub Actions | Grátis para repositórios públicos / 2.000 min/mês nos privados |

> Para 40 pessoas, tudo isso é muito baixo. A tabela `searches` (ver `docs/metricas.md`) ajuda a estimar volume quando escalar.
