# Checklist de Produção — Doroteia

> Onde estamos e o que falta pra soltar pros 40 usuários.
> Legenda: ✅ feito · ⏳ falta · 👤 tarefa sua · 🤖 eu te ajudo/codo

---

## ✅ Já pronto

**Produto (as 8 camadas do briefing)**
- ✅ Banco de dados (Supabase) com as tabelas
- ✅ Webhook + boas-vindas + consentimento
- ✅ Contatos → hash → grafo (privacidade por construção)
- ✅ Pedir serviço (entende a frase com a Claude) + regras 🟢🟡🔴
- ✅ Recomendar um prestador
- ✅ Convite por link (cria o vínculo)
- ✅ Menu + "meus dados" / exclusão total (LGPD)
- ✅ Métricas de demanda (tabela `searches`) + consultas de negócio

**Segurança / robustez (produção técnica)**
- ✅ RLS ligado no Supabase (banco trancado a acessos externos)
- ✅ Validação da assinatura da Twilio (só aceita mensagem real da Twilio)
- ✅ Rede de segurança no código (nunca deixa a conversa no silêncio)
- ✅ Segredos fora do código (variáveis de ambiente no Render)

---

## ⏳ Falta — tarefas suas (👤)

1. **👤 Número oficial do WhatsApp** (sair do sandbox). Precisa de:
   - Conta **Meta Business** (Gerenciador de Negócios do Facebook)
   - **Verificação da empresa** pela Meta
   - Um **número de telefone dedicado** (que NÃO esteja no app do WhatsApp)
   - Nome de exibição aprovado ("Doroteia")
   - *Leva alguns dias de aprovação.* 🤖 Eu te guio clique a clique quando quiser.

2. **👤 Revisão do DPO** (privacidade/LGPD). Entregar o `docs/privacidade-hash.md`
   e validar os pontos abertos (telefone do prestador = base legal; retenção; etc.).
   🤖 Eu posso montar um "resumo de entrega" pra facilitar.

3. **👤 Backup da chave do hash** (`CONTACT_HASH_KEY`). Guarde uma cópia segura
   dessa chave (gerenciador de senhas). Se ela se perder, o grafo de contatos
   "quebra" (os hashes deixam de casar). É a peça mais insubstituível.

4. **👤 Teste com 3–5 amigos reais** antes dos 40 — pra pegar surpresas de
   linguagem e de fluxo.

5. **👤 (Recomendado) Plano pago no Render.** O plano grátis "dorme" quando fica
   ocioso e demora ~50s pra acordar — a primeira mensagem pode falhar. Um plano
   básico mantém a Doroteia sempre acordada.

---

## ⏳ Falta — onde eu te ajudo/codo (🤖)

1. **🤖 Guiar o cadastro do número oficial** (passo a passo, quando você começar).
2. **🤖 Preparar a entrega pro DPO** (resumo + perguntas).
3. **🤖 Botões interativos de verdade.** Hoje usamos texto (SIM, recomendar...).
   Quando o número oficial sair, troco pelos botões clicáveis do WhatsApp.
4. **🤖 Processamento assíncrono (item 8 do briefing).** Hoje a Doroteia responde
   na hora (síncrono). Pros 40 está ótimo. Se escalar muito, a gente separa:
   responde "ok" na hora e processa o resto em segundo plano, pra nunca dar
   timeout. *Não é urgente.*
5. **🤖 Ajustes de copy** — qualquer fala, é só editar o `textos.py`.

---

## 💰 De olho nos custos (quando for ao ar de verdade)
- **WhatsApp/Twilio**: cobram por conversa/mensagem em produção.
- **Claude (Anthropic)**: cada frase interpretada custa frações de centavo.
- **Render**: grátis no teste; ~US$ 7/mês pra ficar sempre acordado.
- **Supabase**: grátis cobre bem o beta.

> Para 40 pessoas, tudo isso é baixo — mas vira conta importante quando escala.
> A tabela `searches` (consulta 3 em `docs/metricas.md`) ajuda a estimar volume.

---

## 🚦 Resumo: 3 coisas pra "ligar a chave" do beta real
1. Número oficial do WhatsApp aprovado (passo 4).
2. Backup da `CONTACT_HASH_KEY` guardado.
3. Render num plano que não "dorme".

O resto (DPO, botões, assíncrono) pode evoluir em paralelo. 💛
