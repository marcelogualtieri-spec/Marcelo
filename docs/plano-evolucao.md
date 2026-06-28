# Plano de Evolução — Doroteia (conexões + prestadores)

> Status: **desenho aprovado para aplicar; revisão posterior.** Consolida as decisões
> de produto que tomamos sobre o novo modelo de vínculo (conexões mútuas), os 3 níveis
> de indicação e a participação dos prestadores de serviço.

---

## 1. Visão

Rede de **indicações de confiança**, **sem conversa direta** entre usuários. A Doroteia
cruza indicações; o nome de quem indicou só aparece entre **conexões mútuas**. O
prestador de serviço é parte central — passa de "registro passivo" a "participante" com
controle do próprio perfil.

---

## 2. Os 3 níveis de indicação

| Nível | Quem indicou | Como aparece |
|---|---|---|
| 🟢 **1. Mútuo validado** | conexão mútua (os dois aceitaram) | **com o nome** |
| 🟡 **3. Pendente / da sua agenda** | alguém que **você adicionou**, mas que não te conectou | **anônimo**, "de alguém que você adicionou" |
| ⚪ **2. Rede Doroteia** | sem relação com você | **anônimo**, "da rede" |

**Regra de privacidade do nível 3 (k-anonimato, k = 5):**
- A indicação "da sua agenda" só é exibida **com esse rótulo** se você tiver
  **≥ 5 contatos pendentes** (o grupo onde o anônimo se esconde).
- Com **< 5 contatos pendentes**, a mesma indicação aparece como **nível 2 puro**
  ("da rede"), sem nenhuma pista de que é seu contato — zero vazamento. O empurrão para
  crescer a rede aparece de forma **genérica** (não colado a um resultado).
- Implementação: simples contagem `contatos_pendentes >= 5`.
- Bônus: essa regra **é** uma "regra de contribuição" (dar para receber).

---

## 3. Conexões (modelo "match")

- Conexão é **mútua e explícita**: link → clica → aceita → os dois ficam conectados.
  Sem aceite, não há nome (fica no nível 3).
- Estados: **pendente / aceita / recusada / bloqueada**.
- **Sem DM**: conectar habilita só o cruzamento de indicações, nunca troca de mensagens.
- **Bloqueio** disponível a qualquer momento.
- **Descobribilidade** (no Termo): quem tem seu número e te adiciona sabe que você usa a
  Doroteia e vê suas indicações (com nome se mútuo; anônimo se não).
- A tabela `edges` (hashes) **continua** sendo a base para detectar vínculos latentes que
  alimentam o nível 3 e as sugestões de conexão.

---

## 4. Prestadores de serviço

**Premissa:** todo *cadastro de prestador* aceita os Termos. O caso do profissional
público que não pode aceitar é tratado como classe separada (referência).

### Classe A — Prestador Verificado ✔️
Alcançável, clicou no link, **aceitou os Termos**, confirmou o perfil (serviço, região,
diferenciais). Recebe selo de verificado, avisos, e controla/pausa/remove o cadastro.

### Classe B — Referência pública (não verificada)
Profissional de **contato profissional público** (ex.: médico com telefone de consultório
no Google) **ou** que ainda não aderiu. Base legal: **interesse legítimo + dado tornado
público** (LGPD art. 7º, §3º) + recomendação de um usuário — **não** consentimento dele.
Condições:
- exibido como **"não verificado"**;
- **só contato profissional público**, nada privado;
- **opt-out sempre disponível** (pode pedir remoção mesmo sem ter aderido);
- se aderir e aceitar os Termos, **vira Classe A**.

### Dual-role (prestador que também é usuário) — resolução
- **Uma conta por número; papéis que se somam, no mesmo chat.**
- Todo número é usuário por padrão; "prestador" é um **perfil opcional** na mesma conta.
- A **porta de entrada** decide o onboarding (link de prestador → onboarding de prestador).
- O **menu é adaptativo**: "Meu perfil profissional" só aparece para quem tem perfil ativo,
  dentro de **"Minha conta"** (renomeia o atual "Meus dados").

### Fluxos e mensagens (linguagem neutra de gênero)

**P1 — Prestador novo (convidado por indicação).** Mensagem única + botões; o serviço vem
codificado no link:
> Olá! 💛 Você chegou à Doroteia porque *[quem indicou]* confia no seu trabalho e quer te
> indicar como profissional de *[serviço]*. A Doroteia conecta quem precisa de um serviço a
> profissionais recomendados por pessoas de confiança — sem a bagunça dos grupos. Quando
> alguém da rede precisar de *[serviço]* e receber sua indicação, seu contato vai só para
> essa pessoa. **Ninguém te manda mensagem por aqui.** Para ativar, precisamos da sua
> autorização para usar seu contato e a categoria do serviço, conforme os Termos de Uso.
> _Digite MENU a qualquer momento para mais informações._
> **[ ✅ Aceito e confirmo ]  [ ✏️ Ajustar serviço ]  [ ⛔ Não desejo ]**

- **[✅ Aceito]** →
> Cadastro ativo! 🚀 Agora você faz parte da rede de confiança. Para que os pedidos certos
> cheguem até você, me conte rapidinho (pode mandar tudo num texto só):
> 1️⃣ *Região de atendimento* — toda São Paulo ou bairros específicos?
> 2️⃣ *Diferenciais* — o que destaca seu trabalho? Formas de pagamento, redes sociais...
> 3️⃣ *Sobre o seu trabalho* — conte um pouco de como você atende.
> Depois, é só digitar *MENU* para ajustar qualquer coisa.

- **[✏️ Ajustar serviço]** → "Qual é a categoria certa do seu serviço? Ex.: encanador,
  eletricista, pediatra…" → segue para o refinamento.
- **[⛔ Não desejo]** →
> Tudo bem, sem problema! 💛 Não vou ativar seu cadastro e seu contato não será repassado a
> ninguém pela rede. Se mudar de ideia, é só voltar por aqui.

**P2 — Convidado que já é usuário (dual-role):**
> Oi de novo! 💛 *[quem indicou]* te indicou como profissional de *[serviço]*. Você já usa a
> Doroteia para buscar — quer também **ativar seu perfil profissional** e receber clientes
> quando for recomendado?
> **[ ✅ Ativar meu perfil ]  [ ✏️ Ajustar serviço ]  [ Agora não ]**

**P3 — Gerenciar perfil** (Minha conta → Meu perfil profissional):
> Seu perfil profissional 🧰 — Serviço: *[x]* · Região: *[y]* · Status: *[ativo/pausado]*
> **[ ✏️ Editar ]  [ ⏸️ Pausar indicações ]  [ ⬅️ Voltar ]**

**P4 — Aviso ao ser recomendado** (só dentro da janela de 24h no piloto):
> 🎉 Boa notícia! Você acabou de ser recomendado para *[serviço]* na região de *[bairro]*.
> Podem te chamar direto. _(Não compartilhamos os dados de quem buscou.)_

**P5 — Sair / remover (LGPD), sempre disponível:**
> Quer sair como profissional da rede? Posso **pausar** (volta quando quiser) ou **remover**
> seu cadastro de vez.
> **[ ⏸️ Pausar ]  [ 🗑️ Remover cadastro ]  [ ⬅️ Voltar ]**

---

## 5. Onboarding do usuário

- **Buscar primeiro** — não travar o início em "5 contatos".
- Deixar claro o "dar para receber": **busca gratuita**, mas certos recursos pedem
  contribuição (contatos/indicações) — ver Termo, seção de contribuição.

---

## 6. Notificações (piloto)

- Por enquanto, **só dentro da janela de 24h** do WhatsApp; **sem templates** pagos.
- Consequência consciente: avisos a quem está inativo não saem. Suficiente para o piloto.
- Revisitar templates quando escalar.

---

## 7. Cláusulas adicionadas ao Termo de Uso (`termos.py`)

- Rede **sem mensagens diretas** entre usuários.
- **Descobribilidade** + visibilidade de indicações.
- **Bloqueio**.
- **Profissionais**: Verificado (aceita Termos) × Referência pública (interesse legítimo /
  dado público) + **direito de pausa/remoção**.
- **Contribuição e gratuidade** (busca grátis; regras de contribuição).

> Pendente de preenchimento antes de divulgar: identificação do controlador e e-mail do
> Encarregado (DPO) em `termos.py`.

---

## 8. Implementação em fases (proposta)

1. **Fase 1 — Conexões + 3 níveis na busca.** Tabela `connections` (estado), reescrita de
   `existe_vinculo`/busca para os 3 níveis com o gate k=5, e **bloqueio**.
2. **Fase 2 — Convite-conexão por link.** Aceitar / recusar / bloquear; menu de "Convites
   pendentes".
3. **Fase 3 — Prestadores.** Onboarding Classe A (link → aceite → perfil), Referência
   pública Classe B, dual-role, "Meu perfil profissional".
4. **Fase 4 — Notificações/resumo diário.** Só quando resolver os templates de 24h.
- **Transversal:** linguagem neutra de gênero; Termos sempre atualizados.

### Mudanças de dados previstas (a detalhar por fase)
- `connections` (a, b, status, quem_iniciou, datas).
- `providers`: `member_id`, `status` (pendente/ativo/pausado/removido), `verificado`,
  `regiao`, `diferenciais`, `descricao`.
- `members`: flags conforme necessário.
- Reaproveita `edges`, `short_links`, códigos de convite e o cron já existentes.
