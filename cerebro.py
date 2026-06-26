# cerebro.py
# ===========================================================================
# O CEREBRO CONVERSACIONAL DA DOROTEIA.
# ---------------------------------------------------------------------------
# Aqui a Doroteia deixa de usar "falas prontas" e passa a CONVERSAR de verdade,
# com um motor de IA (Claude Haiku). A IA entende qualquer jeito de escrever e
# responde em linguagem natural - mas TODA ACAO sensivel (buscar, recomendar,
# adicionar contatos, convidar, ver/apagar dados, consentir) passa por uma
# "ferramenta" que o NOSSO codigo executa de forma determinista (app.py).
#
# PRIVACIDADE: numeros de telefone de contatos/convidados NUNCA vao pra IA.
# Antes de mandar a mensagem pra Claude, trocamos cada numero por uma ficha
# ("[CONTATO_1]"). So o nosso codigo sabe o numero real por tras da ficha.
# ===========================================================================

import re

from anthropic import Anthropic
from privacidade import extrair_numeros_de_texto, normalizar_e164

_cliente = Anthropic()

# Motor leve e rapido pra conversa do dia a dia.
MODELO = "claude-haiku-4-5"

# Quantas trocas de mensagem guardamos de memoria (ida + volta = 2).
MAX_HISTORICO = 12


# ---------------------------------------------------------------------------
# PERSONALIDADE E REGRAS (a "alma" da Doroteia fica aqui, em vez de textos.py)
# ---------------------------------------------------------------------------
SISTEMA_BASE = """Voce e a Doroteia: uma assistente no WhatsApp que recomenda \
prestadores de servico de CONFIANCA, como aquela amiga que sempre tem a \
indicacao certa na ponta da lingua.

COMO VOCE FALA:
- Portugues do Brasil, calorosa, acolhedora e direta. Frases curtas.
- Use emojis com moderacao (💛 😊 🙌 🤝), no maximo um ou dois por mensagem.
- Nunca soe robotica nem use linguagem de formulario. Converse de verdade.
- Chame a pessoa pelo primeiro nome quando souber.

COMO A DOROTEIA FUNCIONA (explique com suas palavras quando fizer sentido):
- A pessoa conta o que precisa (ex.: "encanador em Perdizes, SP") e voce procura
  indicacoes na rede de confianca dela.
- Indicacao de alguem que ela conhece aparece COM o nome de quem indicou.
- Indicacao de fora da rede dela aparece SEM revelar quem indicou.
- A rede cresce quando ela adiciona contatos de confianca e convida amigos.

PRIVACIDADE E LGPD (inegociavel):
- Os contatos da pessoa sao guardados em codigo embaralhado - nem voce ve os numeros.
- Voce nunca repassa o telefone de ninguem (so o do prestador, que e o objetivo).
- A pessoa pode apagar tudo quando quiser. SEMPRE confirme antes de excluir.

LOCALIZACAO:
- A Doroteia atende o Brasil inteiro, nao so Sao Paulo. Sempre que for buscar ou
  registrar um servico, garanta que tem o BAIRRO e a CIDADE. Se faltar a cidade,
  pergunte com naturalidade. O estado (UF) ajuda quando houver cidades de mesmo nome.

CONTATOS:
- A forma mais facil de a pessoa adicionar contatos ou convidar alguem e
  compartilhar o contato pelo clipe 📎 do WhatsApp. Incentive isso.

REGRA DE OURO DAS FERRAMENTAS:
- Para QUALQUER acao real (buscar, recomendar, adicionar contatos, convidar, ver
  dados, excluir, registrar consentimento) voce DEVE usar a ferramenta certa.
  Nunca invente resultados, telefones, nomes ou confirmacoes.
- Telefones e links que vierem de uma ferramenta devem ser copiados na sua
  resposta EXATAMENTE como vieram, caractere por caractere. Nunca altere digitos.

FICHAS DE CONTATO:
- Quando a pessoa manda um numero, voce ve uma ficha tipo [CONTATO_1] no lugar do
  numero (isso protege a privacidade). Trate a ficha como "o contato que ela mandou";
  as ferramentas sabem o numero real por tras dela."""

SISTEMA_SEM_CONSENT = """

ATENCAO - ESTA PESSOA AINDA NAO DEU CONSENTIMENTO:
- Antes de qualquer coisa, de as boas-vindas, explique em poucas linhas o que voce
  faz e peca o "pode ser" dela (consentimento de privacidade).
- So chame 'registrar_consentimento' quando ela concordar claramente (ex.: "sim",
  "pode ser", "bora", "topo").
- Enquanto ela nao consentir, NAO use nenhuma outra ferramenta (nao busque, nao
  salve nada). So converse e explique."""


# ---------------------------------------------------------------------------
# DEFINICAO DAS FERRAMENTAS (o que a IA pode pedir pro codigo fazer)
# ---------------------------------------------------------------------------
FERRAMENTAS = [
    {
        "name": "registrar_consentimento",
        "description": "Registra que a pessoa concordou com a politica de privacidade. "
                       "Chame so quando ela aceitar claramente. Depois disso, convide-a a "
                       "adicionar contatos de confianca.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "buscar_servico",
        "description": "Procura prestadores indicados para um servico em um lugar. "
                       "Use quando a pessoa pedir uma indicacao. Precisa de servico, bairro e "
                       "cidade (pergunte se faltar a cidade).",
        "input_schema": {
            "type": "object",
            "properties": {
                "servico": {"type": "string", "description": "no singular e minusculo, ex: 'encanador'"},
                "bairro":  {"type": "string"},
                "cidade":  {"type": "string"},
                "estado":  {"type": "string", "description": "sigla UF, ex: 'SP' (opcional)"},
            },
            "required": ["servico", "bairro", "cidade"],
        },
    },
    {
        "name": "salvar_recomendacao",
        "description": "Registra uma recomendacao que a pessoa esta fazendo de um prestador bom. "
                       "Use a ficha de contato (ex: [CONTATO_1]) no campo telefone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome":     {"type": "string", "description": "nome do prestador"},
                "telefone": {"type": "string", "description": "a ficha do contato, ex: '[CONTATO_1]'"},
                "servico":  {"type": "string"},
                "bairro":   {"type": "string"},
                "cidade":   {"type": "string"},
                "estado":   {"type": "string"},
            },
            "required": ["nome", "telefone", "servico", "bairro", "cidade"],
        },
    },
    {
        "name": "adicionar_contatos",
        "description": "Adiciona a rede de confianca da pessoa TODOS os contatos que ela mandou "
                       "nesta mensagem (compartilhados pelo clipe ou digitados). Use quando ela "
                       "quiser cadastrar pessoas de confianca dela.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "convidar_pessoa",
        "description": "Prepara um convite pronto para a pessoa que ela mandou nesta mensagem "
                       "(ficha de contato). Conecta os dois e devolve um link pronto pra ela "
                       "encaminhar. Use quando ela quiser convidar alguem especifico.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gerar_link_convite",
        "description": "Gera um link de convite generico que a pessoa pode divulgar pra varias "
                       "pessoas. Use quando ela quiser um link pra compartilhar amplamente.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_meus_dados",
        "description": "Mostra um resumo dos dados que a Doroteia guarda sobre a pessoa.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "excluir_meus_dados",
        "description": "Apaga TODOS os dados da pessoa. So passe confirmado=true depois que ela "
                       "confirmar explicitamente que quer apagar tudo. Se ainda nao confirmou, "
                       "chame com confirmado=false para registrar a intencao e peca a confirmacao.",
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmado": {"type": "boolean", "description": "true so apos confirmacao explicita"},
            },
            "required": ["confirmado"],
        },
    },
]


# ---------------------------------------------------------------------------
# FICHAS: troca numeros por [CONTATO_n] antes de mandar pra IA
# ---------------------------------------------------------------------------
def _tokenizar_numeros(texto, numeros_compartilhados):
    """Devolve (texto_para_ia, lista_numeros_e164, nota_sistema).
    Substitui numeros do texto por fichas [CONTATO_n] e adiciona os contatos
    compartilhados (clipe) como fichas tambem. Os numeros reais ficam so aqui."""
    numeros = []          # lista de E.164 reais, na ordem das fichas
    texto_ia = texto or ""

    # 1) numeros digitados no texto: acha e troca por fichas.
    achados = extrair_numeros_de_texto(texto_ia) if texto_ia else []
    for e164 in achados:
        if e164 not in numeros:
            numeros.append(e164)

    # Substitui qualquer sequencia "telefonica" do texto pela ficha correspondente.
    # (a ordem das fichas segue a ordem em que os numeros validos apareceram)
    if achados:
        def _troca(m):
            e164 = normalizar_e164(m.group(0))
            if e164 and e164 in numeros:
                return f"[CONTATO_{numeros.index(e164) + 1}]"
            return m.group(0)
        texto_ia = re.sub(r"\+?\d[\d\s().\-]{6,}\d", _troca, texto_ia)

    # 2) contatos compartilhados pelo clipe (vem so como numeros, sem texto).
    extras = []
    for e164 in numeros_compartilhados or []:
        if e164 not in numeros:
            numeros.append(e164)
        extras.append(f"[CONTATO_{numeros.index(e164) + 1}]")

    nota = ""
    if extras:
        nota = (f"\n\n[sistema: a pessoa compartilhou o(s) contato(s) "
                f"{', '.join(extras)} pelo clipe do WhatsApp.]")

    return texto_ia, numeros, nota


# ---------------------------------------------------------------------------
# CONTEXTO POR-PESSOA pro topo do prompt (nome, consentimento, totais)
# ---------------------------------------------------------------------------
def _contexto_pessoa(membro):
    nome = (membro.get("nome_perfil") or "").strip()
    primeiro = nome.split()[0] if nome else ""
    consentiu = bool(membro.get("consent"))
    linhas = [
        "DADOS DESTA PESSOA (para voce se situar):",
        f"- Primeiro nome: {primeiro or '(desconhecido)'}",
        f"- Ja consentiu: {'sim' if consentiu else 'nao'}",
    ]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# O LOOP DE CONVERSA (recebe -> pensa -> [usa ferramentas] -> responde)
# ---------------------------------------------------------------------------
def conversar(membro, texto_usuario, numeros_compartilhados, *,
              executar_ferramenta, enviar_texto, salvar_historico):
    """Conduz uma rodada de conversa.

    - executar_ferramenta(nome, entrada, numeros) -> str  (acao real, no app.py)
    - enviar_texto(str)                                   (manda a resposta no WhatsApp)
    - salvar_historico(lista)                             (persiste a memoria)
    """
    texto_ia, numeros, nota = _tokenizar_numeros(texto_usuario, numeros_compartilhados)
    conteudo_usuario = (texto_ia + nota).strip() or "(a pessoa mandou uma mensagem sem texto)"

    historico = list(membro.get("historico") or [])
    mensagens = historico + [{"role": "user", "content": conteudo_usuario}]

    sistema = SISTEMA_BASE + "\n\n" + _contexto_pessoa(membro)
    if not membro.get("consent"):
        sistema += SISTEMA_SEM_CONSENT

    texto_final = ""
    for _ in range(5):   # ate 5 rodadas de ferramenta por mensagem
        try:
            resposta = _cliente.messages.create(
                model=MODELO,
                max_tokens=700,
                system=sistema,
                tools=FERRAMENTAS,
                messages=mensagens,
            )
        except Exception as erro:
            print(f"[CEREBRO] erro na IA: {erro}")
            return   # app.py ja tem rede de seguranca (ERRO_GENERICO no except externo)

        if resposta.stop_reason == "tool_use":
            mensagens.append({"role": "assistant", "content": resposta.content})
            resultados = []
            for bloco in resposta.content:
                if bloco.type == "tool_use":
                    print(f"[FERRAMENTA] {bloco.name} {bloco.input}")
                    saida = executar_ferramenta(bloco.name, bloco.input, numeros)
                    resultados.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": saida,
                    })
            mensagens.append({"role": "user", "content": resultados})
            continue

        # Sem mais ferramentas: junta o texto final.
        texto_final = "".join(b.text for b in resposta.content if b.type == "text").strip()
        break

    if not texto_final:
        texto_final = "Pode repetir, por favor? Acho que me perdi aqui 😅"

    enviar_texto(texto_final)

    # Guarda a memoria (so texto, sem o vai-e-vem das ferramentas), enxuta.
    novo_historico = historico + [
        {"role": "user", "content": conteudo_usuario},
        {"role": "assistant", "content": texto_final},
    ]
    salvar_historico(novo_historico[-MAX_HISTORICO:])
