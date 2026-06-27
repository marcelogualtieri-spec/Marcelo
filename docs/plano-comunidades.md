# Plano — Comunidades na Doroteia

> Transformar cada grupo real de WhatsApp (escola, prédio, bairro) num **link de
> entrada exclusivo**. Quem entra pelo link é *etiquetado* como pertencente àquela
> comunidade. As indicações passam a carregar esse contexto — sem nunca ler membros
> de grupo (100% legal/LGPD, como descrito no PDF da Manus AI).

## 1. O que muda na experiência

Hoje a busca tem 3 níveis de confiança:

- 🟢 **verde** — indicação de alguém com vínculo direto (convite ou contato em comum); mostra o nome.
- 🟡 **amarelo** — indicação boa, mas de fora da rede; esconde o nome.
- 🔴 **vermelho** — ninguém indicou ainda.

Comunidades adicionam um **nível intermediário entre verde e amarelo**:

- 🟢🤝 **mesma comunidade** — quem indicou está na MESMA comunidade que você (ex.: ambos
  entraram pelo link do "Plato Perdizes"). Mostra o nome **com o contexto da comunidade**:
  *"Na comunidade Plato Perdizes, o Seu Francisco foi indicado pela Júlia."*

Ordem de apresentação na busca: **verde → mesma comunidade → amarelo → vermelho**.

## 2. Banco de dados (migration v9)

### Tabela nova: `comunidades`
| coluna | tipo | descrição |
|---|---|---|
| id | uuid PK | |
| slug | text unique | usado no link, ex.: `plato-perdizes` |
| nome | text | nome de exibição, ex.: `Plato Perdizes` |
| criada_por | uuid (members) nullable | quem (organizadora) criou |
| created_at | timestamptz | |

### Tabela nova: `comunidade_membros` (N-para-N)
| coluna | tipo | descrição |
|---|---|---|
| id | uuid PK | |
| comunidade_id | uuid FK → comunidades | |
| member_id | uuid FK → members | |
| created_at | timestamptz | |
| | unique(comunidade_id, member_id) | uma linha por pessoa por comunidade |

> Uma pessoa pode pertencer a **várias** comunidades (ex.: escola + prédio). Por isso
> N-para-N, e não uma coluna em `members`.

**Não precisa mexer em `recommendations`.** A relação "mesma comunidade" é **derivada na
busca**: `comunidades(pedidor) ∩ comunidades(recomendador)`. Isso lida naturalmente com
quem está em várias comunidades e evita denormalização frágil.

## 3. Como os códigos são criados (comando admin no WhatsApp)

- Nova env `ADMIN_WA_IDS` (lista de números de organizadora, separados por vírgula).
- Só para esses números, a Doroteia ganha a ferramenta `criar_comunidade`.
- Você manda: *"criar comunidade Plato Perdizes"* → a Doroteia:
  1. gera o `slug` (`plato-perdizes`), garante que é único;
  2. insere em `comunidades`;
  3. devolve o **link pronto** pra colar no grupo:
     `https://wa.me/<bot>?text=Oi! Quero entrar na Doroteia (comunidade: plato-perdizes)`
- Para todo mundo que não é admin, a ferramenta nem é oferecida e o executor recusa.

## 4. Entrada e etiquetagem (o "pulo do gato")

- Quem clica no link cai no chat já com o texto `(comunidade: plato-perdizes)`.
- Novo parser `extrair_codigo_comunidade(texto)` lê o slug.
- Em `_processar_mensagem`, ao detectar o slug:
  - busca a comunidade pelo slug;
  - cria a linha em `comunidade_membros` (idempotente — entrar de novo não duplica);
  - funciona para **membro novo** (etiqueta no cadastro) e para **membro que já usa**
    a Doroteia e entrou num grupo novo (etiqueta na hora).
- `limpar_texto_convite` passa a remover também `(comunidade: ...)` antes de mandar pra IA.
- A Doroteia dá as boas-vindas citando a comunidade: *"Vi que você chegou pela comunidade
  *Plato Perdizes* 🙌"* — igual já faz com quem chega por convite de pessoa.

> O link só circula dentro do grupo do WhatsApp. Quem não está no grupo não vê o link —
> o **próprio WhatsApp faz a filtragem**. A Doroteia não lê nada do grupo.

## 5. Mudança na busca (`executar_busca` / `_ferr_buscar`)

- Pré-carrega o conjunto de comunidades do `pedidor`.
- Para cada indicação:
  - `existe_vinculo` → 🟢 verde (como hoje);
  - senão, se `comunidades(recomendador) ∩ comunidades(pedidor)` ≠ ∅ → 🟢🤝 **comunidade**
    (mostra nome + nome da comunidade compartilhada);
  - senão → 🟡 amarelo.
- Retorna 3 grupos: `com_nome` (verde), `por_comunidade` (novo), `sem_nome` (amarelo).
- `registrar_busca` ganha o resultado `"comunidade"` (separado de verde/amarelo/vermelho)
  pras métricas e pro alerta de busca vermelha continuar correto (busca com hit de
  comunidade **não** é vermelha).

## 6. Arquivos tocados

- `db/migration-v9.sql` (novo) + `db/migrations-todas.sql` (acrescenta v9).
- `app.py`:
  - env `ADMIN_WA_IDS` + helper `eh_admin(wa_id)`;
  - helpers: `slugify`, `criar_comunidade`, `buscar_comunidade_por_slug`,
    `etiquetar_membro_comunidade`, `comunidades_do_membro`, `extrair_codigo_comunidade`;
  - `limpar_texto_convite` estendido;
  - `_processar_mensagem`: parse + etiquetagem + contexto de boas-vindas;
  - `executar_busca` + `_ferr_buscar`: nível "comunidade";
  - `registrar_busca`: aceitar `"comunidade"`;
  - `construir_executor`: ferramenta `criar_comunidade` (gated por admin).
- `cerebro.py`:
  - nova ferramenta `criar_comunidade` (definição);
  - nota no system prompt p/ admin (pode criar comunidades) e p/ boas-vindas de comunidade;
  - `_contexto_pessoa`: lista as comunidades da pessoa + boas-vindas de entrada.

## 7. Decisão de privacidade a confirmar

Mostrar o **primeiro nome** de quem indicou para um co-membro da comunidade (que não é
contato direto) — é exatamente o efeito que o PDF pede (*"indicado pela Júlia"*). É
coerente com o comportamento 🟢 verde atual (indicar é um ato voluntário e "público"
dentro de círculos de confiança). 

- **Recomendado:** mostrar só o primeiro nome (como no verde).
- Alternativa mais conservadora: mostrar a comunidade mas anonimizar o nome
  (*"alguém da comunidade Plato Perdizes indicou"*). Menos poderoso socialmente.

## 8. Rollout

1. Rodar `db/migration-v9.sql` no Supabase.
2. Setar `ADMIN_WA_IDS` no Render (seu número).
3. Deploy do branch.
4. Criar as comunidades pelo chat e colar os links nos grupos.

## 9. Fora do escopo desta primeira versão (sugestões futuras)

- Painel pra listar comunidades e quantos membros cada uma tem.
- Expirar/desativar um código de comunidade.
- Permitir a uma pessoa "sair" de uma comunidade.
- Métrica de quantas indicações vieram por comunidade.
