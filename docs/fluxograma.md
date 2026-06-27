# Fluxograma da Doroteia

> Diagramas em **Mermaid** — abra no GitHub ou num visualizador Markdown pra ver como desenho.

---

## 1. Arquitetura (as peças e como conversam)

```mermaid
flowchart LR
    U["📱 Usuário no WhatsApp"] <--> M["WhatsApp Cloud API\n(Meta/Graph v21)"]
    M <--> R["Render\napp.py — Flask"]
    R <--> S["Supabase\n(PostgreSQL)"]
    R <--> C["Anthropic\nClaude Haiku"]
    G["GitHub Actions\ncron diário 10h BRT"] --> R
```

**Em uma frase:** o usuário fala no WhatsApp → a Meta entrega pro servidor no Render → o servidor consulta o banco (Supabase) e, quando precisa entender uma frase, pergunta pro Claude Haiku → e responde de volta pela Cloud API. O cron do GitHub Actions dispara um endpoint diário de follow-up.

---

## 2. Fluxo principal — o que acontece a cada mensagem

```mermaid
flowchart TD
    A["Mensagem chega em /webhook\n(POST com assinatura Meta validada)"] --> B{"Membro existe\nno banco?"}

    %% ---------- Pessoa nova ----------
    B -- "Não" --> C{"Tem código de convite\nno texto?"}
    C -- "Sim" --> C1["Busca por invite_code\nno cadastro do convidante"]
    C -- "Não" --> C2{"Hash do telefone\ncasa em pending_invites?"}
    C2 -- "Sim" --> C3["Aplica convite pendente\n(deleta pending_invite)"]
    C2 -- "Não" --> C4["Sem convidante"]
    C1 --> D["Cria membro\n(consent=false, invited_by setado)"]
    C3 --> D
    C4 --> D

    %% ---------- Etiquetagem por comunidade (novo + retorno) ----------
    D --> CM{"Tem código de comunidade\nno texto? (comunidade: slug)"}
    B -- "Sim" --> CM
    CM -- "Sim" --> CM1["etiquetar_membro_comunidade\n(idempotente) + boas-vindas\ncitando o grupo"]
    CM -- "Não" --> CC["Enriquece contexto:\n- comunidades da pessoa\n- eh_admin?"]
    CM1 --> CC

    %% ---------- Sem consentimento ----------
    CC --> G0{"Já consentiu?"}
    G0 -- "Não, 1º contato\n(histórico vazio)" --> E0["SISTEMA_PRIMEIRO_CONTATO\nbotões: apresenta + explica o que faz\n+ POR QUE precisa do consent\n'Pode ser! 💛' / 'Quero saber mais'"]
    G0 -- "Não, já apresentada" --> E["SISTEMA_SEM_CONSENT\nsó tools: registrar_consentimento + enviar_botoes"]
    E --> E1{"Intenção?"}
    E1 -- "Quer saber mais / dúvida / tenta avançar" --> E1a["Explica TUDO que dá pra fazer\n+ privacidade + importância do consent\n(botões de novo)"]
    E1 -- "Aceitou" --> E3
    E0 --> E2{"Pessoa aceita?"}
    E2 -- "Sim (botão ou texto)" --> E3["IA chama registrar_consentimento\napp grava consent=true + consent_at\n(se invited_by: avisa o convidante)"]
    E3 --> E4["IA responde em ≤3 linhas:\nboas-vindas, convida a compartilhar contatos\ne pergunta o que ela precisa"]

    %% ---------- Já consentiu ----------
    G0 -- "Sim" --> F["Enriquece o membro:\n- convidado_por_nome (se aplicável)\n- avaliacao_pendente (indicação sem nota)"]
    E4 --> F
    F --> G2["cerebro.conversar()\nClaude Haiku com histórico (≤12 msgs)\n+ todas as tools"]
    G2 --> H{"IA decide qual\nferramenta usar"}
```

> **Fase de consentimento sem botão solto:** enquanto a pessoa não consente, o modelo só recebe as ferramentas `registrar_consentimento` e `enviar_botoes` — nenhuma ação real (buscar, indicar, contatos) vaza antes do "ok".

---

## 3. Fluxos por intenção

### 3.1 Buscar uma indicação

```mermaid
flowchart TD
    A["buscar_servico(servico, cidade, bairro?)"] --> B["executar_busca:\nbusca em recommendations\nfiltro: servico + cidade\nbairro apenas se informado"]
    B --> C["Para cada rec:\nverifica consent do recomendador\n+ existe_vinculo(pedidor, recomendador)"]
    C --> D{"Tem vínculo direto?"}
    D -- "Sim" --> F["🟢 VERDE (rede direta)\nnome(s) de quem indicou"]
    D -- "Não" --> D2{"Compartilha alguma\ncomunidade com o pedidor?"}
    D2 -- "Sim" --> CM["🤝 MESMA COMUNIDADE\nnome de quem indicou + nome do grupo\n'Na comunidade X, Fulano indicou'"]
    D2 -- "Não" --> G["🟡 AMARELO (fora da rede)\nsem dizer quem indicou"]
    F --> R["Agrupa por provider_id,\nordena por nota_media,\nregistra em indicacoes_recebidas"]
    CM --> R
    G --> R
    R --> E{"Algum resultado?"}
    E -- "Verde ou comunidade" --> I["registrar_busca\n(verde, ou 'comunidade' se só comunidade)"]
    E -- "Só amarelo" --> I2["registrar_busca(amarelo)"]
    E -- "Nenhum" --> H["🔴 VERMELHO\nconvida a recomendar alguém\nou trazer mais contatos\nregistrar_busca(vermelho)"]
```

Prioridade de apresentação: **🟢 rede direta → 🤝 mesma comunidade → 🟡 fora da rede → 🔴 nada**. Um prestador que apareça em mais de um nível só conta no mais forte.

**Vínculo direto** (`existe_vinculo`): pedidor convidou recomendador, OU recomendador convidou pedidor, OU o hash do telefone de um aparece na tabela `edges` do outro.

**Mesma comunidade:** `comunidades(pedidor) ∩ comunidades(recomendador) ≠ ∅` — derivado em tempo de busca a partir de `comunidade_membros`.

### 3.2 Adicionar contatos + gerar convites (passo único)

```mermaid
flowchart TD
    A["Usuária compartilha cards pelo clipe 📎"] --> B["conteudo_da_mensagem:\nextrai lista (e164, nome_card)"]
    B --> C["IA vê fichas [CONTATO_1], [CONTATO_2]...\ncom nomes — nunca os números reais"]
    C --> D["IA chama adicionar_contatos"]
    D --> E["processar_contatos:\n1) calcula HMAC-SHA256 de cada número\n2) insere em edges (hashes novos)\n3) classifica: membro / não-membro"]
    E --> F{"Para quem já é membro"}
    F --> F1["Anuncia com entusiasmo\n'Fulano já usa a Doroteia!'"]
    E --> G{"Para quem não é membro"}
    G --> G1["registrar_convite_pendente\n(hash no pending_invites)"]
    G1 --> G2["gera link individual curto\n/c/<code> → wa.me/<número>?text=..."]
    F1 --> H["IA entrega: quem já está na rede\n+ link por pessoa (troca [CONTATO_n] pelo nome)"]
    G2 --> H
```

### 3.3 Recomendar alguém

```mermaid
flowchart TD
    A["IA chama salvar_recomendacao\n(nome, telefone/ficha, servico, cidade, bairro?)"] --> B["_resolver_ficha:\nconverte [CONTATO_n] no número real"]
    B --> C{"Tem telefone e cidade?"}
    C -- "Não" --> D["Devolve erro pra IA\npedir o que falta"]
    C -- "Sim" --> E["INSERT em providers\n(nome, telefone, servico, bairro, cidade, estado)"]
    E --> F["INSERT em recommendations\n(member_id, provider_id, servico, bairro, cidade)"]
    F --> G["IA agradece e explica que\na indicação vai aparecer com o nome dela"]
```

### 3.4 Avaliar uma indicação

```mermaid
flowchart TD
    A["Usuária conta como foi o prestador\nou IA puxa o assunto (avaliacao_pendente)"] --> B["IA chama avaliar_indicacao\n(nome, usou, nota?, comentario?)"]
    B --> C{"usou?"}
    C -- "false" --> D["UPDATE indicacoes_recebidas\nstatus = 'dispensada'\nIA para de perguntar"]
    C -- "true" --> E{"nota de 1-5?"}
    E -- "Não" --> F["Devolve erro pra IA\npedir a nota"]
    E -- "Sim" --> G["UPSERT em avaliacoes\n(member_id, provider_id, nota, comentario)"]
    G --> H["UPDATE indicacoes_recebidas\nstatus = 'avaliada'"]
    H --> I["_recalcular_nota_provider:\nrecalcula nota_media e qtd_avaliacoes\nem providers"]
    I --> J["IA agradece e explica\nque a nota melhora a relevância"]
```

### 3.5 Follow-up proativo (cron diário)

```mermaid
flowchart TD
    A["GitHub Actions\n13:00 UTC = 10h BRT"] --> B["POST /cron/follow-up\nheader X-Cron-Secret"]
    B --> C["_enviar_follow_ups:\nbusca indicacoes_recebidas\nonde status='pendente'\nE follow_up_at IS NULL\nE created_at < agora - 7 dias"]
    C --> D["Seleciona 1 por membro\n(mais recente)\naté 50 por rodada"]
    D --> E["enviar_mensagem_meta\nvia WHATSAPP_PHONE_NUMBER_ID\n'Oi! Há 7 dias te indiquei X...'"]
    E --> F["UPDATE indicacoes_recebidas\nfollow_up_at = agora\n(evita duplicatas)"]
```

### 3.6 Painel pessoal

| Ferramenta | O que faz |
|---|---|
| `ver_meus_dados` | Nome, consent, contagens (edges, recommendations) |
| `ver_minhas_indicacoes` | Tudo que ela já indicou, com nota média quando houver |
| `ver_minha_rede` | Quais contatos do grafo dela já são membros com consent |
| `ver_minhas_buscas` | Últimas 10 buscas, com resultado 🟢🤝🟡🔴 |

### 3.7 Exclusão (LGPD)

```mermaid
flowchart TD
    A["Usuária pede pra sair / apagar tudo"] --> B["IA chama excluir_meus_dados\n(confirmado=false)"]
    B --> C["IA pede confirmação explícita\n(ação irreversível)"]
    C --> D{"Confirmou?"}
    D -- "Sim" --> E["IA chama excluir_meus_dados\n(confirmado=true)"]
    E --> F["DELETE em members\n(CASCADE apaga edges, recs, avaliacoes...)"]
    F --> G["IA se despede com carinho"]
    D -- "Não" --> H["IA cancela e volta ao normal"]
```

### 3.8 Comunidades (cada grupo vira um link de entrada)

```mermaid
flowchart TD
    subgraph CRIAR["Organizadora cria a comunidade (admin)"]
      A1["Organizadora (número em ADMIN_WA_IDS)\nmanda 'criar comunidade Plato Perdizes'"] --> A2["IA chama criar_comunidade\n(gated: só admin)"]
      A2 --> A3["slugify → 'plato-perdizes'\nINSERT em comunidades (slug único)"]
      A3 --> A4["Monta link curto:\nwa.me/&lt;bot&gt;?text=...(comunidade: plato-perdizes)"]
      A4 --> A5["IA entrega o link\npra colar no grupo do WhatsApp"]
    end

    subgraph ENTRAR["Pessoa entra pelo link"]
      B1["Clica no link (só circula dentro do grupo)"] --> B2["Mensagem chega com\n'(comunidade: plato-perdizes)'"]
      B2 --> B3["extrair_codigo_comunidade\n→ busca comunidade pelo slug"]
      B3 --> B4["etiquetar_membro_comunidade\n(idempotente, vale p/ novo e p/ quem já usa)"]
      B4 --> B5["Boas-vindas citando o grupo\n'Vi que você chegou pela comunidade X 🙌'"]
    end
```

> **Privacidade:** a Doroteia **nunca lê membros de grupo**. A barreira de entrada é o próprio link — só quem está no grupo o vê. A pessoa se "etiqueta" sozinha ao entrar (dado consentido). 100% legal/LGPD.

---

## 4. Regras de vínculo (como o verde acende)

```mermaid
flowchart LR
    P["Pedidor P\nbusca encanador em SP"] --> Q{"Recomendador R\ntem vínculo com P?"}
    Q -- "P convidou R (invited_by)" --> V["🟢 mostra nome de R"]
    Q -- "R convidou P (invited_by)" --> V
    Q -- "Hash de R está em edges de P" --> V
    Q -- "Hash de P está em edges de R" --> V
    Q -- "Sem vínculo" --> CQ{"P e R compartilham\nalguma comunidade?"}
    CQ -- "Sim" --> CV["🤝 mostra nome de R\n+ nome da comunidade"]
    CQ -- "Não" --> Y["🟡 sem nome"]
```

> O vínculo por contato é checado comparando **HMAC-SHA256** dos números (irreversíveis), nunca os números em si. Detalhes em `docs/privacidade-hash.md`.

---

## 5. Mapa: arquivo → função → tabela

| Função | Arquivo | Tabela(s) |
|---|---|---|
| Receber mensagem | `app.py / webhook()` | — |
| Criar membro | `app.py / criar_membro()` | `members` |
| Gravar consentimento | `app.py / registrar_consentimento()` | `members` |
| Hash + grafo de contatos | `app.py / processar_contatos()` | `edges` |
| Busca verde/comunidade/amarelo/vermelho | `app.py / executar_busca()` | `recommendations`, `members`, `edges`, `comunidade_membros` |
| Criar comunidade (admin) | `app.py / criar_comunidade()` + `_ferr_criar_comunidade()` | `comunidades` |
| Etiquetar membro na entrada | `app.py / etiquetar_membro_comunidade()` | `comunidade_membros` |
| Salvar recomendação | `app.py / _ferr_recomendar()` | `providers`, `recommendations` |
| Convite por telefone | `app.py / registrar_convite_pendente()` | `pending_invites` |
| Aplicar convite ao entrar | `app.py / aplicar_convite_pendente()` | `pending_invites`, `members` |
| Link curto `/c/<code>` | `app.py / encurtar_link()` + `redirecionar_link()` | `short_links` |
| Indicação recebida (follow-up) | `app.py / registrar_indicacao_recebida()` | `indicacoes_recebidas` |
| Avaliar indicação | `app.py / _ferr_avaliar()` | `avaliacoes`, `indicacoes_recebidas`, `providers` |
| Follow-up proativo | `app.py / _enviar_follow_ups()` | `indicacoes_recebidas` |
| Painel buscas | `app.py / _ferr_ver_buscas()` | `searches` |
| Painel rede | `app.py / _ferr_ver_rede()` | `edges`, `members` |
| Painel indicações | `app.py / _ferr_ver_indicacoes()` | `recommendations`, `providers` |
| IA conversacional | `cerebro.py / conversar()` | `members` (historico) |

---

## 6. Banco de dados (tabelas atuais)

| Tabela | Para que serve |
|---|---|
| `members` | Cadastro, consent, histórico de conversa (jsonb) |
| `edges` | Grafo de confiança — só hashes dos contatos |
| `providers` | Prestadores/médicos/escolas indicados |
| `recommendations` | Quem indicou qual provider |
| `searches` | Métricas de busca (servico, bairro, cidade, resultado, member_id) |
| `pending_invites` | Convites a quem ainda não entrou (hash do telefone) |
| `short_links` | Encurtador interno `/c/<code>` |
| `avaliacoes` | Notas 1–5 por membro por provider |
| `indicacoes_recebidas` | Providers mostrados a cada pessoa → base do follow-up |
| `comunidades` | Grupos reais (escola, prédio, bairro) com slug + nome |
| `comunidade_membros` | Quem pertence a qual comunidade (N-para-N) |

---

## 7. Variáveis de ambiente necessárias (Render)

| Variável | Para que serve |
|---|---|
| `SUPABASE_URL` | Conexão com o banco |
| `SUPABASE_KEY` | Chave de serviço do Supabase |
| `WHATSAPP_TOKEN` | Token da WhatsApp Cloud API (Meta) |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificação do webhook Meta |
| `WHATSAPP_APP_SECRET` | Valida assinatura das mensagens recebidas |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número do bot (usado no cron de follow-up) |
| `ANTHROPIC_API_KEY` | Chave da API do Claude Haiku |
| `CONTACT_HASH_KEY` | Chave secreta do HMAC-SHA256 dos contatos |
| `PUBLIC_BASE_URL` | Base para links curtos (ex: `https://doroteia-ia.onrender.com`) |
| `CRON_SECRET` | Protege o endpoint `/cron/follow-up` |
| `ADMIN_WA_IDS` | Números de organizadora (só dígitos, separados por vírgula) que podem criar comunidades |

| Variável | Onde também configurar |
|---|---|
| `CRON_SECRET` | GitHub Secrets (usado pelo workflow `follow-up.yml`) |
