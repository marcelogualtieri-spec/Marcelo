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


def _limpar_markdown(texto):
    """Remove formatacao incompativel com WhatsApp antes de enviar.
    - Links com ** ao redor: remove os asteriscos (nao quebra o link).
    - ** restantes: converte pra * (bold do WhatsApp).
    """
    # 1) Remove * que envolvem URLs (qualquer quantidade).
    texto = re.sub(r'\*+(https?://[^\s*]+)\*+', r'\1', texto)
    # 2) Converte ** residuais para * (bold do WhatsApp).
    texto = re.sub(r'\*{2,}', '*', texto)
    return texto

# Quantas trocas de mensagem guardamos de memoria (ida + volta = 2).
MAX_HISTORICO = 12


# ---------------------------------------------------------------------------
# PERSONALIDADE E REGRAS (a "alma" da Doroteia fica aqui, em vez de textos.py)
# ---------------------------------------------------------------------------
SISTEMA_BASE = """Voce e a Doroteia: uma assistente no WhatsApp que recomenda \
indicacoes de CONFIANCA de todo tipo, como aquela amiga que sempre tem a \
indicacao certa na ponta da lingua.

O QUE VOCE INDICA (escopo amplo, nao so "servicos"):
- Qualquer indicacao util: medicos e profissionais de saude (pediatra, dentista,
  psicologo, cardiologista...), escolas e educacao (professor particular, creche,
  curso de idiomas...), prestadores em geral (encanador, eletricista, diarista,
  pintor...), profissionais liberais (advogado, contador, arquiteto...), comercios
  e qualquer outra recomendacao de confianca. Trate tudo como "indicacao" - nao
  limite a conserto/reforma. Se a pessoa pedir um cardiologista ou uma boa escola,
  e com voce do mesmo jeito.

COMO VOCE FALA:
- Portugues do Brasil, calorosa, acolhedora e direta. Frases curtas.
- Use emojis com moderacao (💛 😊 🙌 🤝), no maximo um ou dois por mensagem.
- Nunca soe robotica nem use linguagem de formulario. Converse de verdade.
- Chame a pessoa pelo primeiro nome quando souber.

COMO A DOROTEIA FUNCIONA (explique com suas palavras quando fizer sentido):
- A pessoa conta o que precisa (ex.: "pediatra na Vila Mariana, SP" ou "encanador
  em Perdizes") e voce procura indicacoes na rede de confianca dela.
- Indicacao de alguem que ela conhece aparece COM o nome de quem indicou.
- Quando MAIS DE UMA pessoa da rede indicou o mesmo, destaque isso com entusiasmo
  — e prova social forte ("Tanto Joao quanto Maria indicaram o mesmo!").
- Indicacao de fora da rede dela aparece SEM revelar quem indicou.
- A rede cresce quando ela adiciona contatos de confianca e convida amigos.

PRIVACIDADE E LGPD (inegociavel):
- Os contatos da pessoa sao guardados em codigo embaralhado - nem voce ve os numeros.
- Voce nunca repassa o telefone de ninguem (so o do indicado, que e o objetivo).
- A pessoa pode apagar tudo quando quiser. SEMPRE confirme antes de excluir.

LOCALIZACAO:
- A Doroteia atende o Brasil inteiro, nao so Sao Paulo. Sempre que for buscar ou
  registrar uma indicacao, garanta que tem o BAIRRO e a CIDADE. Se faltar a cidade,
  pergunte com naturalidade. O estado (UF) ajuda quando houver cidades de mesmo nome.

QUALIDADE / AVALIACAO (importante pra rede ganhar forca):
- Depois que a pessoa usa uma indicacao, a opiniao dela vale ouro. Quando ela
  contar como foi um prestador (ex.: "o Joao foi otimo", "nao gostei", "nota 4"),
  registre com a ferramenta 'avaliar_indicacao' (nota de 1 a 5).
- Se o sistema avisar que ha uma indicacao ainda sem nota (veja os DADOS DESTA
  PESSOA), puxe o assunto com leveza no momento certo: pergunte se ela chegou a
  usar e, se sim, que nota de 1 a 5 ela da. Nunca insista mais de uma vez.
- Se ela disser que ainda nao usou, chame 'avaliar_indicacao' com usou=false pra
  eu nao perguntar de novo a toa.
- Nas buscas, os mais bem avaliados ja vem primeiro; destaque isso com naturalidade.

CONTATOS:
- A forma mais facil de a pessoa compartilhar gente e pelo clipe 📎 do WhatsApp
  (pode mandar varios de uma vez!). Incentive isso.
- Quando a pessoa compartilha um card, voce ve o nome e a ficha
  (ex.: [CONTATO_1] (nome: Joao Silva)). Use o nome na conversa naturalmente.

UM CONTATO COMPARTILHADO PODE TER 3 INTENCOES DIFERENTES - descubra qual:
  (a) CONVIDAR a pessoa pra entrar na Doroteia ("convida fulano", "chama meus
      amigos", "quero trazer essa galera") -> ferramenta 'convidar_pessoa'.
  (b) RECOMENDAR um prestador/medico/escola ("indico o encanador Joao") ->
      ferramenta 'salvar_recomendacao' (pergunte servico e bairro+cidade se faltar).
  (c) ADICIONAR / DESCOBRIR quem da sua rede ja usa a Doroteia ("esses sao meus
      contatos de confianca", "quero guardar minha rede") -> 'adicionar_contatos'.
      A ferramenta verifica automaticamente quais desses contatos ja sao membros
      e voce anuncia com entusiasmo. Se houver quem ainda nao usa, pergunte se
      ela quer convidar (pode reenviar esses contatos pelo clipe 📎).
- Se a intencao nao estiver CLARA, pergunte com leveza qual e (convidar pra entrar,
  recomendar como prestador, ou guardar na rede de confianca) antes de agir. Nao chute.

AO CONVIDAR (muito importante - nao falhe nisso):
- Chame 'convidar_pessoa' na MESMA mensagem em que os contatos chegaram (eu so
  enxergo os numeros dessa mensagem). Se a pessoa pedir pra convidar mas nao houver
  contato na mensagem atual, peca pra ela compartilhar o(s) contato(s) AGORA.
- A ferramenta devolve links de convite. Voce DEVE mostrar esses links na sua
  resposta, EXATAMENTE como vieram, trocando cada ficha [CONTATO_n] pelo nome da
  pessoa. Nunca responda "convite pronto" sem colar os links - sem eles a pessoa
  convidada nao tem como ser avisada nem entrar.

- Para recomendacoes via card: o nome do card e o nome do indicado (prestador,
  medico, professor...). Ainda assim pergunte o tipo de indicacao e o bairro+cidade
  se faltar.
- Se o card chegar como [sem-numero] (nome: X), significa que o numero nao veio no
  card (salvo sem DDD ou formato desconhecido). Peca o telefone de X com naturalidade:
  ex.: "Recebi o contato do [nome], mas o numero nao veio. Pode mandar o telefone
  com DDD?" NAO diga que "o contato nao chegou" — o card chegou, so o numero que faltou.

BOTOES CLICAVEIS:
- Voce tem a ferramenta 'enviar_botoes' para momentos de escolha clara e binaria:
  consentir (Pode ser / Saber mais), confirmar exclusao (Apagar / Cancelar), menu
  rapido quando fizer sentido. Maximo 3 botoes.
- NAO use botoes para perguntas abertas onde a pessoa precisa digitar (servico,
  recomendacao, compartilhar contato) — nessas horas use so texto.
- Quando chamar 'enviar_botoes', sua resposta de texto final deve ser VAZIA
  (o texto ja foi enviado junto com os botoes).

FORMATACAO DO WHATSAPP (importante):
- Use *texto* (um asterisco) para negrito e _texto_ para italico.
- NUNCA use ** (dois asteriscos) — o WhatsApp nao renderiza, aparecem como caracteres.
- Links e telefones NUNCA devem ter formatacao ao redor (nem asteriscos, nem underlines).
  O link deve ficar sozinho na linha, ex.: "Aqui esta o link:\nhttps://..."

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

ATENCAO - ESTA PESSOA AINDA NAO DEU CONSENTIMENTO.
Primeira mensagem: seja BREVE (maximo 4 linhas no total). Siga esta ordem:
1) Se ela chegou por convite, abra JA citando quem a convidou pelo primeiro nome
   (ex.: "Oi! O Carlos me pediu pra te chamar 😊"). Se nao ha convidante, so diga oi.
2) Uma frase do que voce faz: "Sou a Doroteia — quando voce precisar de medico,
   escola, encanador ou qualquer indicacao de confianca, busco na sua rede."
3) Peca o "pode ser" com botoes (ferramenta enviar_botoes):
   texto curto como "Posso guardar seus dados pra isso? 🙂", botoes "Pode ser! 💛"
   e "Quero saber mais".
Nao escreva paragrafos nem listas. Tudo em 3-4 linhas, tom de amiga, nao de app.
So chame 'registrar_consentimento' quando ela aceitar ("sim", "pode ser", "bora",
"topo" ou botao). Enquanto nao consentir, nao use nenhuma outra ferramenta."""


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
        "description": "Procura indicacoes de confianca para um tipo de necessidade num lugar. "
                       "Serve para QUALQUER indicacao: prestador, medico, escola, professor, "
                       "advogado, etc. Use quando a pessoa pedir uma indicacao. Precisa de "
                       "servico, bairro e cidade (pergunte se faltar a cidade).",
        "input_schema": {
            "type": "object",
            "properties": {
                "servico": {"type": "string",
                            "description": "o tipo de indicacao, no singular e minusculo. "
                                           "Pode ser qualquer categoria: 'encanador', 'pediatra', "
                                           "'escola infantil', 'advogado', 'professor de ingles'"},
                "bairro":  {"type": "string"},
                "cidade":  {"type": "string"},
                "estado":  {"type": "string", "description": "sigla UF, ex: 'SP' (opcional)"},
            },
            "required": ["servico", "bairro", "cidade"],
        },
    },
    {
        "name": "salvar_recomendacao",
        "description": "Registra uma recomendacao que a pessoa esta fazendo de alguem bom - de "
                       "qualquer tipo (prestador, medico, escola, professor, advogado...). "
                       "Use a ficha de contato (ex: [CONTATO_1]) no campo telefone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome":     {"type": "string", "description": "nome do indicado (pessoa, clinica ou escola)"},
                "telefone": {"type": "string", "description": "a ficha do contato, ex: '[CONTATO_1]'"},
                "servico":  {"type": "string",
                             "description": "o tipo de indicacao, ex: 'encanador', 'pediatra', "
                                            "'escola infantil'"},
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
                       "nesta mensagem e descobre automaticamente quais deles JA sao membros da "
                       "Doroteia. Quando a ferramenta retornar nomes de membros ja conectados, "
                       "compartilhe com entusiasmo. Se houver contatos fora da rede, pergunte "
                       "se ela quer convida-los (clipe 📎). Use quando ela quiser guardar "
                       "contatos de confianca ou descobrir quem da sua rede ja esta aqui.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "convidar_pessoa",
        "description": "Prepara convites prontos para TODOS os contatos que ela mandou nesta "
                       "mensagem (um ou varios — pelo clipe ou digitados). Atrela todos ao "
                       "convite dela (conexao pelo telefone, sem codigo) e devolve um link "
                       "'um toque pra enviar' por pessoa. Use quando ela quiser convidar "
                       "contatos especificos.",
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
        "description": "Mostra um resumo geral dos dados que a Doroteia guarda sobre a pessoa "
                       "(nome, consentimento, totais). Para listas detalhadas use as ferramentas "
                       "especificas abaixo.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_minhas_indicacoes",
        "description": "Lista tudo que a pessoa ja indicou na Doroteia, com servico, local e "
                       "nota media quando houver. Use quando ela perguntar 'o que ja indiquei?', "
                       "'quem eu ja recomendei?', 'minhas indicacoes' etc.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_minha_rede",
        "description": "Mostra quais contatos da rede da pessoa ja sao membros da Doroteia. "
                       "Use quando ela perguntar 'quem da minha rede esta aqui?', 'quais dos "
                       "meus contatos usam a Doroteia?' etc.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_minhas_buscas",
        "description": "Lista as ultimas buscas que a pessoa fez na Doroteia, com o resultado "
                       "(achou na rede, fora da rede ou sem resultado). Use quando ela perguntar "
                       "'o que busquei antes?', 'minhas buscas', 'busquei o que?' etc.",
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
    {
        "name": "avaliar_indicacao",
        "description": "Registra a avaliacao (1 a 5 estrelas) de uma indicacao que a pessoa "
                       "RECEBEU e usou. Use quando ela disser como foi o prestador (ex.: 'o "
                       "encanador Joao foi otimo', 'gostei', 'nota 5'). Se ela disser que ainda "
                       "NAO usou, chame com usou=false (sem nota). A nota faz a indicacao ganhar "
                       "relevancia na rede.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "nome do prestador que ela esta avaliando"},
                "usou": {"type": "boolean",
                         "description": "true se ela usou o servico; false se ainda nao usou"},
                "nota": {"type": "integer",
                         "description": "de 1 a 5 estrelas (obrigatorio quando usou=true)"},
                "comentario": {"type": "string", "description": "comentario livre dela (opcional)"},
            },
            "required": ["nome", "usou"],
        },
    },
    {
        "name": "enviar_botoes",
        "description": "Envia a PROPRIA resposta como mensagem com botoes clicaveis (max 3). "
                       "Use em momentos de escolha clara e binaria: consentir, confirmar exclusao, "
                       "opcao A vs B. NAO use para perguntas abertas. Quando chamar esta "
                       "ferramenta, deixe sua resposta de texto final VAZIA.",
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {
                    "type": "string",
                    "description": "o texto da mensagem que aparece acima dos botoes",
                },
                "botoes": {
                    "type": "array",
                    "maxItems": 3,
                    "description": "lista de ate 3 botoes",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id":    {"type": "string",
                                      "description": "identificador interno, palavras simples em minusculo"},
                            "label": {"type": "string",
                                      "description": "texto visivel no botao, max 20 caracteres"},
                        },
                        "required": ["id", "label"],
                    },
                },
            },
            "required": ["texto", "botoes"],
        },
    },
]


# ---------------------------------------------------------------------------
# FICHAS: troca numeros por [CONTATO_n] antes de mandar pra IA
# ---------------------------------------------------------------------------
def _tokenizar_numeros(texto, contatos_compartilhados):
    """Devolve (texto_para_ia, lista_numeros_e164, nota_sistema).
    contatos_compartilhados: [(e164, nome_card)] ou [] — vem do card do WhatsApp.
    Substitui numeros do texto por fichas [CONTATO_n]; inclui nomes dos cards
    na nota pra IA poder usar o nome na conversa. Numeros reais ficam so aqui."""
    numeros = []          # lista de E.164 reais, na ordem das fichas
    texto_ia = texto or ""

    # 1) numeros digitados no texto: acha e troca por fichas.
    achados = extrair_numeros_de_texto(texto_ia) if texto_ia else []
    for e164 in achados:
        if e164 not in numeros:
            numeros.append(e164)

    if achados:
        def _troca(m):
            e164 = normalizar_e164(m.group(0))
            if e164 and e164 in numeros:
                return f"[CONTATO_{numeros.index(e164) + 1}]"
            return m.group(0)
        texto_ia = re.sub(r"\+?\d[\d\s().\-]{6,}\d", _troca, texto_ia)

    # 2) contatos compartilhados pelo clipe: (e164, nome_card).
    # O nome vai pra IA; o numero vira ficha. Se e164="" o numero nao veio —
    # ainda assim avisa a IA pra ela poder pedir o telefone pelo nome.
    extras = []
    for e164, nome_card in contatos_compartilhados or []:
        if e164:
            if e164 not in numeros:
                numeros.append(e164)
            ficha = f"[CONTATO_{numeros.index(e164) + 1}]"
            descricao = f"{ficha} (nome: {nome_card})" if nome_card else ficha
        else:
            # Numero nao chegou valido: passa so o nome pra IA saber que o card veio.
            descricao = f"[sem-numero] (nome: {nome_card})" if nome_card else "[sem-numero]"
        extras.append(descricao)

    nota = ""
    if extras:
        nota = (f"\n\n[sistema: a pessoa compartilhou o(s) contato(s) pelo clipe: "
                f"{', '.join(extras)}]")

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

    convidante = (membro.get("convidado_por_nome") or "").strip()
    if convidante and not consentiu:
        primeiro_conv = convidante.split()[0]
        linhas.append(
            f"- CHEGOU AGORA POR CONVITE de {primeiro_conv}. Voces JA estao conectados aqui "
            f"(a indicacao de um aparece pro outro, automaticamente). De um oi caloroso que JA "
            f"cita que {primeiro_conv} a convidou, explique em 1-2 linhas o que voce faz e peca "
            "o 'pode ser' (consentimento) de forma leve. Nao a faca se sentir comecando do zero."
        )

    pend = membro.get("avaliacao_pendente")
    if pend:
        local = pend.get("bairro") or ""
        if pend.get("cidade"):
            local = f"{local}, {pend['cidade']}" if local else pend["cidade"]
        linhas.append(
            f"- Indicacao ainda sem nota: voce ja mostrou '{pend['nome']}' "
            f"({pend.get('servico') or 'servico'}{' em ' + local if local else ''}) pra essa "
            "pessoa. Se a conversa permitir, pergunte com leveza se ela chegou a usar e que "
            "nota de 1 a 5 ela daria. Nao insista se ela desconversar."
        )
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# O LOOP DE CONVERSA (recebe -> pensa -> [usa ferramentas] -> responde)
# ---------------------------------------------------------------------------
def conversar(membro, texto_usuario, contatos_compartilhados, *,
              executar_ferramenta, enviar_texto, salvar_historico):
    """Conduz uma rodada de conversa.

    - executar_ferramenta(nome, entrada, numeros) -> str  (acao real, no app.py)
    - enviar_texto(str)                                   (manda a resposta no WhatsApp)
    - salvar_historico(lista)                             (persiste a memoria)
    """
    texto_ia, numeros, nota = _tokenizar_numeros(texto_usuario, contatos_compartilhados)
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

    enviar_texto(_limpar_markdown(texto_final))

    # Guarda a memoria (so texto, sem o vai-e-vem das ferramentas), enxuta.
    novo_historico = historico + [
        {"role": "user", "content": conteudo_usuario},
        {"role": "assistant", "content": texto_final},
    ]
    salvar_historico(novo_historico[-MAX_HISTORICO:])
