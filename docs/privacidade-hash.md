# Privacidade e hash dos contatos (Doroteia) — item 5 do briefing

> Documento para revisão por especialista de segurança / DPO.
> Descreve **o que foi implementado**, **por que é seguro** e **quais pontos
> ainda precisam de validação formal**. Código correspondente:
> `privacidade.py` (núcleo) e `app.py` (função `processar_contatos`).

---

## 1. Objetivo

Montar um grafo social de "quem conhece quem" para priorizar indicações de
pessoas do círculo de confiança do usuário — **sem armazenar números de
telefone de quem não é membro**. A ligação entre pessoas é guardada de forma
**irreversível**, não como número discável.

## 2. O que NÃO é armazenado

- ❌ Número de telefone de um contato compartilhado que **não** é membro.
- ❌ Nome do contato compartilhado (o vCard/nome cru é descartado).
- ❌ A chave secreta (pepper) **não** vive no banco de dados.

## 3. O que É armazenado (tabela `edges`)

| Coluna | Conteúdo |
|---|---|
| `member_id` | quem compartilhou o contato (é membro consentido) |
| `contact_hash` | **HMAC-SHA256** do número do contato (irreversível) |
| `created_at` | data/hora |

Restrição `UNIQUE(member_id, contact_hash)`: evita duplicatas.

> Observação: o número do **próprio membro** é guardado em claro em
> `members.wa_id`. Isso é intencional e está discutido na seção 8.

## 4. A receita (pipeline)

```
número bruto
   │  (1) normalização
   ▼
E.164  (ex.: +5511999998888)         ← phonenumbers (Google libphonenumber)
   │  (2) HMAC-SHA256 com chave secreta
   ▼
contact_hash  (texto hexadecimal de 64 caracteres)
   │  (3) grava em edges; número cru é descartado na mesma operação
   ▼
banco
```

1. **Normalização (E.164):** garante que o mesmo telefone gere sempre a mesma
   entrada. Sem isso, `(11) 99999-8888` e `+55 11 99999 8888` produziriam
   hashes diferentes e o grafo não casaria. Implementado em
   `privacidade.normalizar_e164` (números inválidos são descartados).
2. **HMAC-SHA256 com chave secreta:** `privacidade.calcular_contact_hash`.
3. **Descarte do cru:** em `app.processar_contatos`, apenas os hashes são
   acumulados e inseridos; o número nunca é escrito no banco.

## 5. Por que HMAC com chave secreta (e não um hash "puro")?

O espaço de números de telefone é pequeno (ordem de bilhões). Um hash simples
(`sha256(numero)`) seria vulnerável a **ataque de dicionário / força bruta**:
um atacante geraria o hash de todos os números possíveis e montaria uma tabela
reversa, revelando os números a partir dos hashes.

O **HMAC** mistura uma **chave secreta** (pepper) no cálculo. Sem conhecer a
chave, o atacante **não consegue** pré-computar essa tabela: ele teria que
adivinhar a chave (256 bits de entropia, inviável). É a defesa central do
modelo.

## 6. Onde vive a chave secreta (pepper)

- Variável de ambiente `CONTACT_HASH_KEY`, configurada no provedor de
  hospedagem (Render), gerada aleatoriamente.
- **Fora do banco de dados** e **fora do código-fonte** (não vai para o Git;
  `.env` está no `.gitignore`).
- Lida uma única vez na inicialização (`privacidade._CHAVE_SECRETA`).

## 7. Modelo de ameaça — "o que acontece se vazar?"

| Cenário | Consequência | Por quê |
|---|---|---|
| **Vaza só o banco** (dump do Postgres) | Números de não-membros **permanecem protegidos** | O atacante tem os `contact_hash`, mas **não tem a chave** para revertê-los por força bruta |
| **Vaza só o código** (repositório Git) | Nenhum dado e nenhuma chave expostos | Código não contém segredos nem dados |
| **Comprometimento total do servidor** (banco **+** variáveis de ambiente) | Risco real: com a chave, força bruta volta a ser possível | Mitigações na seção 8 |

O design eleva a barra de "um único vazamento revela tudo" para "é preciso
comprometer **dois** locais distintos (banco e segredos do servidor) ao mesmo
tempo".

## 8. Pontos que precisam de validação formal (DPO / especialista)

1. **`members.wa_id` em claro.** O número do próprio membro é guardado sem
   hash, pois é necessário para (a) identificar quem está falando no webhook e
   (b) descobrir se um contato compartilhado já é membro. Base legal: execução
   do serviço solicitado pelo titular (o membro consentiu). Avaliar se deve
   também ser protegido em repouso.
2. **`providers.telefone` em claro.** É dado pessoal de um terceiro (o
   prestador) e é justamente o que se entrega a quem pede. Precisa de base
   legal própria; o briefing sugere restringir a profissionais que oferecem o
   serviço publicamente e documentar.
3. **Matching feito na consulta (lazy).** Em vez de pré-calcular o "casamento"
   no momento em que alguém vira membro, ele é avaliado quando há uma busca
   (Camada 5), comparando hashes. O resultado é equivalente e evita estado
   extra; confirmar se atende aos requisitos.
4. **Rotação da chave.** Trocar `CONTACT_HASH_KEY` invalida todos os hashes
   existentes (o grafo "quebra"). Não há, hoje, procedimento de rotação. Tratar
   como chave de longa duração e definir processo de custódia/backup seguro.
5. **Normalização brasileira (9º dígito).** Casos de números móveis antigos sem
   o 9º dígito podem normalizar de forma inconsistente. `phonenumbers` cobre a
   maioria, mas vale teste dedicado para o público-alvo.
6. **Ainda ausentes nesta fase:** Row Level Security no Supabase, rate
   limiting, e tratamento de contato sem WhatsApp. Itens previstos para antes
   de produção.

## 9. Exclusão (LGPD)

As tabelas `recommendations` e `edges` referenciam `members` com
`ON DELETE CASCADE`. Apagar um membro remove automaticamente seus edges e
recomendações — atendendo ao "caminho fácil de exclusão" do briefing. A tela de
exclusão para o usuário final entra na Camada 8.
