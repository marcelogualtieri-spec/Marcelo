# Briefing Dorote.ia — contexto para assistentes (marketing, growth, LGPD, copy)

> **Como usar:** cole este documento inteiro no início de uma conversa nova com o
> Claude (ou outro assistente) e diga o que precisa — "me ajude a escrever as mensagens
> de onboarding", "monte um plano de growth", "revise a privacidade sob a LGPD", "crie
> posts de lançamento", etc. Ele passa a conhecer o produto, as regras e o tom.
>
> **Regra de marca inegociável:** o nome é sempre **Dorote.ia** (com o ponto). Nunca
> "Doroteia".

---

## 1. O que é a Dorote.ia (pitch)

A **Dorote.ia** é uma assistente no **WhatsApp** que funciona como uma **central de
indicações de confiança**: você pede um profissional ou serviço (médico, encanador,
escola, advogado, diarista...) e ela busca recomendações feitas por **pessoas que você
conhece** — sua própria rede de confiança. É o "boca a boca" organizado, sem a bagunça
dos grupos de WhatsApp e sem a desconfiança dos sites de busca.

**Tagline de trabalho:** *"Encontre profissionais recomendados por quem você confia."*

## 2. O problema que resolve

- Pedir indicação em grupo de WhatsApp é caótico, some no fluxo e mistura todo mundo.
- Sites de busca e redes sociais têm avaliações duvidosas, pagas ou de estranhos.
- A melhor recomendação ainda é a de alguém de confiança — mas isso não está organizado
  em lugar nenhum.

A Dorote.ia transforma a confiança pessoal em uma rede consultável, preservando a
privacidade de todos.

## 3. Como funciona — a jornada

1. **Primeiro contato:** a pessoa manda um "oi". A Dorote.ia se apresenta numa única
   mensagem e pede o aceite dos Termos (responder **SIM** ou **SABER MAIS**).
2. **Consentimento (LGPD):** só depois do "SIM" o serviço começa. Tudo é guiado por
   **botões** para não ficar solto.
3. **Menu principal (perfil ativo):** Indicar profissional · Convidar quem confio · ☰ Outras
   opções. O sistema **lembra o perfil ativo** (Cliente ou Profissional); quem tem os dois
   alterna com o comando **TROCAR**. Comandos globais: **MENU · TROCAR · SAIR · AJUDA**.
4. **Buscar:** a pessoa diz o que precisa e em qual bairro/região de SP; a Dorote.ia cruza
   as indicações. **Sem resultado:** ela oferece opções (perguntar a amigos, convidar a
   rede) — **nunca** pede a quem procura que ela mesma indique alguém.
5. **Recomendar:** a pessoa indica um bom profissional (nome, telefone, serviço, cidade)
   — pelo clipe 📎 ou digitando.
6. **Convidar / montar a rede:** gera um link para trazer pessoas de confiança. Quanto
   maior a rede, melhores as indicações.
7. **Sair:** digitar **SAIR** a qualquer momento apaga o cadastro e o nome (com
   confirmação). As indicações já feitas **não são apagadas** — ficam anônimas
   (⚪ rede geral), para a rede não perder a recomendação.

## 4. O coração do produto — os 3 níveis de confiança da indicação

Quando alguém busca, o resultado tem um de três níveis (quanto mais alto, mais forte):

1. **🟢 Conexão mútua validada:** quem indicou tem conexão confirmada com você (os dois
   se aceitaram). Aparece **com o nome** de quem indicou — prova social máxima.
2. **🟡 Da sua agenda (pendente, anônimo):** alguém que **você** adicionou à sua agenda
   de confiança, mas que ainda não confirmou a conexão. Aparece **anônimo**, mas você
   sabe que é de alguém que você escolheu. *(Regra de privacidade — k-anonimato: esse
   rótulo só aparece se você tiver pelo menos ~5 contatos pendentes, para que não seja
   possível adivinhar quem foi.)*
3. **⚪ Rede geral Dorote.ia:** recomendação de alguém sem relação com você. Anônima.
   Acompanha o aviso de que foi "validada pela rede" e o convite para você registrar
   indicações de confiança e fortalecer a base.

> Esse mecanismo é o diferencial: a confiança vira níveis, e a pessoa tem motivo para
> crescer a própria rede (subir do anônimo para o "com nome").

## 5. Dois papéis: Cliente e Profissional (perfil dual)

- **Cliente:** busca, recomenda, convida, monta a rede.
- **Profissional:** quem presta um serviço e quer ser recomendado.
  - Pode entrar por **indicação** (um cliente recomenda → recebe um link → aceita os
    termos profissionais → configura região, diferenciais, descrição → fica ativo), ou
  - Por **autocadastro** ("💼 Quero ser profissional").
- **A mesma pessoa pode ser os dois** (uma conta, um chat). O sistema **lembra o perfil
  ativo** e ela alterna com o comando **TROCAR** (ou em Outras opções → Trocar de perfil).
  Cada perfil tem a sua própria "Minha conta": Cliente vê *Minha rede* e *Indicações que
  fiz*; Profissional vê *Meu perfil* e *Quem me recomendou*.
- **Premissa:** todo cadastro de profissional aceita os Termos. Profissionais de contato
  **público** (ex.: médico com telefone de consultório no Google) podem ser indicados
  como **"referência não verificada"** (base legal de interesse legítimo + dado público),
  sempre com **direito de remoção**.
- Um profissional só é encontrado quando há **recomendações reais de clientes** sobre ele.

## 6. Privacidade e LGPD (arquitetura real)

**Dados coletados:** nome de perfil e número do WhatsApp; conteúdo das mensagens (para a
IA entender e responder); contatos de confiança que a pessoa escolhe conectar; indicações
feitas; buscas; e, para profissionais, dados do perfil.

**Como protegemos (explicar SEM jargão para o público; com método na política):**
- Os **contatos de confiança** são guardados de forma **protegida** — o sistema **não
  guarda nem expõe os números** dos contatos (tecnicamente, um código irreversível
  HMAC-SHA256; mas isso só aparece na seção técnica da política, nunca nas mensagens).
- A **IA nunca recebe números de telefone** — eles são substituídos por fichas
  ([CONTATO_1]) antes de irem ao modelo.
- O telefone **pessoal** nunca é repassado. O único telefone compartilhado é o do
  **profissional indicado** (que é o propósito do serviço).

**Bases legais:** consentimento (aceite explícito no chat) para o uso geral; interesse
legítimo + dado tornado público para "referências públicas" de profissionais.

**Direitos do titular (LGPD art. 18):** acesso, correção, eliminação, portabilidade,
informação sobre compartilhamento e revogação do consentimento. Na prática: digitar
**SAIR** apaga o cadastro e o nome (com confirmação) e **anonimiza** as indicações já
feitas (elas continuam ajudando a rede, sem o nome de quem indicou); o resto é pedido
no chat ou ao Encarregado.

**Operadores / transferência internacional (art. 33):** Meta (WhatsApp Cloud API),
Anthropic (IA), Supabase (banco), Render (hospedagem) — podem processar dados fora do
Brasil, com salvaguardas.

**Pendência antes de divulgar publicamente:** preencher a identificação do **controlador**
(razão social/CNPJ, se houver) e o **e-mail do Encarregado (DPO)** na política de Termos.

## 7. Regras de negócio e guardrails

- **Rede sem conversa direta:** usuários **não trocam mensagens** entre si pela Dorote.ia.
  Ela só cruza indicações. (Reduz spam e risco.)
- **Descobribilidade:** quem tem o seu número e te adiciona pode saber que você usa a
  Dorote.ia e ver suas indicações (com nome se houver conexão mútua; anônimo se não).
  Isso está **explícito nos Termos**.
- **Bloqueio:** dá para bloquear qualquer pessoa a qualquer momento.
- **Reciprocidade ("dar para receber"):** **buscar é gratuito** na versão simples, mas a
  rede só funciona se for alimentada — pode haver **regras de contribuição** (adicionar
  contatos, registrar indicações) para liberar recursos.
- **Sem inventar processos:** a IA nunca promete "falar com a equipe", cadastro externo
  ou prazos — se não resolve, encaminha via canal de **AJUDA** e diz que retornam em breve.
- **Canal de AJUDA:** quem digita AJUDA e relata um problema tem o caso encaminhado para a
  equipe (e respondido com acolhimento).

## 8. Tom de voz e identidade

- **Nome:** sempre **Dorote.ia** (com o ponto).
- **Personalidade:** como aquela amiga que sempre tem a indicação certa — calorosa,
  acolhedora, direta, frases curtas.
- **Português correto e cuidadoso** (acentuação e pontuação sempre).
- **Linguagem neutra de gênero** (evitar "ele/ela", "o/a profissional"; usar "a pessoa",
  "quem presta o serviço", "o contato", construções impessoais).
- **Privacidade explicada de forma simples e um pouco mais formal**, sem jargão técnico.
- Emojis com moderação (💛 😊 🤝 🔒 🔍 💼).

## 9. Restrições do WhatsApp (importantes para growth e UX)

- **Botões:** no máximo **3 por mensagem** (por isso os menus são agrupados; rótulos
  curtos, até 20 caracteres).
- **Janela de 24 horas:** mensagens **proativas** (avisos, lembretes, convites a quem está
  inativo) só chegam livremente dentro de **24h** desde a última mensagem da pessoa. Fora
  disso, exigem **Templates de Mensagem pré-aprovados** pela Meta (e alguns têm custo).
  *No piloto atual não usamos templates — então notificações proativas só alcançam quem
  falou nas últimas 24h.*
- **Indicador de "digitando..."** e leitura são usados para o chat não parecer travado.
- Não há leitura de membros de grupos do WhatsApp (proibido); a rede cresce por convites
  e contatos voluntários.

## 10. Stack técnica (resumo)

- **Frente:** WhatsApp Cloud API (Meta).
- **Servidor:** Python/Flask no Render (no piloto, instância gratuita que "dorme" com
  inatividade — daí alguma lentidão no primeiro retorno).
- **Banco:** Supabase (PostgreSQL).
- **IA conversacional:** Claude Haiku (interpreta linguagem natural; as ações sensíveis
  são executadas de forma determinística pelo código, não pela IA).

## 11. Estado atual e roadmap

**Já funciona:** onboarding + consentimento; **busca nos 3 níveis** (🟢 conexão mútua
validada / 🟡 da rede pendente, anônimo / ⚪ rede geral) com **k-anonimato (≥5)** e
**sinais anônimos** de indicação pendente; **conexão mútua** (os dois confirmam "vocês se
conhecem?"); indicar profissional (com a regra de ouro do consentimento) e convidar/montar
rede por link (links distintos para cliente e para profissional); **avaliação por botões**
(1–5; a IA nunca dá nota); fluxo de prestador (onboarding, perfil, pausar/remover, perfil
dual; invisível na busca até a 1ª recomendação); **SAIR que anonimiza** as indicações;
confirmação pendente mostrada **ao reabrir o chat**; **anti-spam** (20/dia); canal de AJUDA;
robustez do chat (sem duplicatas, "digitando..."). Migrações: v11, v12, v13.

**Próximas fases:**
- **Bloqueio** de pessoas e **recusar conexão** com gestão na "Minha conta".
- **Notificações e resumo diário** (dependem de resolver os Templates de 24h da Meta).
- **Painel "Minha conta"** com histórico por categoria (conexões ativas/pendentes,
  profissionais indicados por mim, indicações que recebi).
- Antes de divulgar: preencher **controlador** (razão social/CNPJ) e **Encarregado (DPO)**
  nos Termos.

## 12. Pedidos comuns que este briefing habilita

- Escrever/revisar **mensagens** do bot (onboarding, menus, erros, prestador) no tom certo.
- Montar **plano de growth** (cold-start da rede, gatilhos de convite, reciprocidade).
- Criar **marketing/copy** de lançamento (posts, descrição, página).
- **Auxílio LGPD** (revisar política, bases legais, fluxos de consentimento e exclusão).
- **Guardrails de negócio** (regras de contribuição, anti-spam, limites).
- Adaptar fluxos às **regras do WhatsApp** (botões, janela de 24h, templates).

> Ao pedir ajuda, diga o público (ex.: mães de uma escola, condomínio, bairro), a cidade
> do piloto e o objetivo. A Dorote.ia nasce em São Paulo/SP como piloto.
