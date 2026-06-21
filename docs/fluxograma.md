# Fluxograma da Doroteia

> Documento de revisão. Os diagramas abaixo estão em **Mermaid** — abra este
> arquivo no GitHub (ou em um visualizador Markdown) para vê-los como desenho.

---

## 1. Arquitetura (as peças e como conversam)

```mermaid
flowchart LR
    U["📱 Usuario no WhatsApp"] <--> T["Twilio (BSP)\nentrega/recebe mensagens"]
    T <--> R["Render\napp.py (servidor Flask)"]
    R <--> S["Supabase\n(banco de dados)"]
    R --> C["Claude / Anthropic\nentende as frases"]
```

**Em uma frase:** o usuário fala no WhatsApp → a Twilio entrega pro nosso
servidor no Render → o servidor consulta o banco (Supabase) e, quando precisa
entender uma frase, pergunta pra Claude → e responde de volta pela Twilio.

---

## 2. Fluxo de decisão (o que acontece a cada mensagem)

```mermaid
flowchart TD
    A["Mensagem chega em /webhook"] --> B{"Ja e membro?"}

    %% ---------- Pessoa nova ----------
    B -- "Nao (pessoa nova)" --> C{"Tem codigo de convite\nno texto?"}
    C -- "Sim" --> C1["Guarda invited_by\n(vinculo do convite)"]
    C -- "Nao" --> C2["Sem convidante"]
    C1 --> D["Cria cadastro + envia BOAS-VINDAS\n(pede consentimento) - tela 7.1"]
    C2 --> D

    %% ---------- Sem consentimento ----------
    B -- "Sim, mas SEM consentimento" --> E{"O que respondeu?"}
    E -- "SIM" --> E1["Grava consentimento\n+ pede contatos (7.2)"]
    E -- "SABER MAIS" --> E2["Envia FAQ + repete"]
    E -- "outro" --> E3["Pede o consentimento de novo"]

    %% ---------- Ja consentiu ----------
    B -- "Sim, JA consentiu" --> F{"Estado da conversa?"}

    F -- "recomendando" --> G["Claude le os dados do prestador\ne grava a indicacao - Camada 6"]
    F -- "confirmando exclusao" --> H{"Digitou EXCLUIR?"}
    H -- "Sim" --> H1["Apaga TUDO - LGPD\n(Camada 8)"]
    H -- "cancelar" --> H2["Volta ao normal"]

    F -- "normal" --> I{"E um comando?"}
    I -- "recomendar" --> I1["Entra no modo recomendacao (6)"]
    I -- "convidar" --> I2["Gera link de convite (7)"]
    I -- "menu / oi" --> I3["Mostra o menu (7.7)"]
    I -- "meus dados / sair" --> I4["Mostra dados + oferece exclusao (8)"]
    I -- "tem numeros" --> J["HASH dos contatos -> grafo (edges)\nCamada 4 🔒"]
    I -- "e uma frase" --> K["Claude extrai\nservico + bairro - Camada 5"]

    K --> L{"Achou os dois?"}
    L -- "so o servico" --> L1["Pede o bairro"]
    L -- "nada" --> L2["Mostra a ajuda"]
    L -- "servico + bairro" --> M["Consulta o grafo\ne aplica as regras (item 6)"]

    M --> N{"Existe indicacao?"}
    N -- "da sua rede (tem vinculo)" --> N1["🟢 VERDE: mostra nome\nde quem indicou + telefone"]
    N -- "fora da sua rede" --> N2["🟡 AMARELO: mostra\nsem dizer quem indicou"]
    N -- "nenhuma" --> N3["🔴 VERMELHO: oferece\nque voce mesmo recomende"]
```

---

## 3. Mapa: cada etapa ↔ camada do briefing ↔ onde está no código

| Etapa no fluxo | Camada | Arquivo / função |
|---|---|---|
| Recebe a mensagem | 2 | `app.py` → `webhook()` |
| Boas-vindas + consentimento | 3 | `webhook()` (caso novo / sem consent) |
| Contatos → hash → grafo | 4 | `privacidade.py` + `processar_contatos()` |
| Pedir serviço (entender + regras) | 5 | `nlu.py` + `tratar_pedido_servico()` |
| Regras 🟢🟡🔴 (vínculo) | 5/6 | `existe_vinculo()` |
| Recomendar | 6 | `tratar_recomendacao()` |
| Convite (link + vínculo) | 7 | `montar_link_convite()` / `extrair_codigo_convite()` |
| Menu + exclusão (LGPD) | 8 | `texto_meus_dados()` / `excluir_membro()` |

---

## 4. Como o grafo "acende o verde" (resumo da privacidade)

```mermaid
flowchart LR
    P["Pedidor P\nbusca servico+bairro"] --> Q{"Quem indicou (R)\ntem vinculo com P?"}
    Q -- "convite: P convidou R\nou R convidou P" --> V["🟢 mostra o nome de R"]
    Q -- "contato: o HASH de P ou R\nbate em edges" --> V
    Q -- "sem vinculo" --> Y["🟡 mostra sem nome"]
```

> O vínculo por contato é checado comparando **hashes** (códigos irreversíveis),
> nunca números de telefone. Detalhes em `docs/privacidade-hash.md`.
