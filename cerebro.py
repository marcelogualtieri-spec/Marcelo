# cerebro.py
# ===========================================================================
# O CEREBRO CONVERSACIONAL DA DOROTEIA.
# ---------------------------------------------------------------------------
# Aqui a Dorote.ia deixa de usar "falas prontas" e passa a CONVERSAR de verdade,
# com um motor de IA (Claude Haiku). A IA entende qualquer jeito de escrever e
# responde em linguagem natural - mas TODA ACAO sensivel (buscar, recomendar,
# adicionar contatos, convidar, ver/apagar dados, consentir) passa por uma
# "ferramenta" que o NOSSO codigo executa de forma determinista (app.py).
#
# PRIVACIDADE: numeros de telefone de contatos/convidados NUNCA vao pra IA.
# Antes de mandar a mensagem pra Claude, trocamos cada numero por uma ficha
# ("[CONTATO_1]"). So o nosso codigo sabe o numero real por tras da ficha.
# ===========================================================================

import os
import re

from anthropic import Anthropic
from privacidade import extrair_numeros_de_texto, normalizar_e164
import textos

_cliente = Anthropic()

# Endereco dos Termos de Uso e Privacidade (pagina /termos do proprio servidor).
LINK_TERMOS = (os.environ.get("TERMOS_URL")
               or "https://doroteia-ia.onrender.com/termos")

# Mensagem fixa de boas-vindas/consentimento, ja com o link dos termos.
BOAS_VINDAS = textos.BOAS_VINDAS.format(link=LINK_TERMOS)

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
# PERSONALIDADE E REGRAS (a "alma" da Dorote.ia fica aqui, em vez de textos.py)
# ---------------------------------------------------------------------------
SISTEMA_BASE = """Voce e a Dorote.ia: uma assistente no WhatsApp que recomenda \
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
- ESCREVA SEMPRE PORTUGUES CORRETO: com acentuacao (voce, nao, indicacao, servico,
  confianca, voce ve, e so) e pontuacao adequada. Nunca escreva sem acentos. Revise
  mentalmente antes de responder — texto com erro passa imagem ruim.
- O nome da marca e SEMPRE *Dorote.ia* (com o ponto, exatamente assim). Nunca escreva
  "Doroteia" sem o ponto.
- LINGUAGEM NEUTRA DE GENERO (obrigatorio): evite "ele/ela", "o/a profissional".
  Use "a pessoa", "quem presta o servico", "o contato", "quem indicou", ou frases
  impessoais. Quando inevitavel, prefira reescrever a frase a marcar genero.
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
- A Dorote.ia atende o Brasil inteiro, nao so Sao Paulo. Sempre que for buscar ou
  registrar uma indicacao, garanta que tem a CIDADE. Se faltar, pergunte com naturalidade.
- BAIRRO e opcional: se a pessoa informar, use; se nao, busque ou registre na cidade inteira.
  O estado (UF) ajuda quando houver cidades de mesmo nome.

VOCABULARIO FIXO — use sempre igual, nunca misture os dois conceitos:
- *INDICACAO* / *INDICAR* = recomendar um prestador, medico, escola ou qualquer servico.
  Ex.: "voce quer *indicar* o Joao como encanador?", "que nota voce da pra essa *indicacao*?".
- *REDE DE CONFIANCA* / *TRAZER PRA REDE* = adicionar pessoas de confianca como contatos.
  Ex.: "quer *trazer a Maria pra sua rede*?", "voce tem 5 pessoas na sua *rede de confianca*".
  NUNCA use "indicar" ou "indicacao" para se referir a pessoas na rede — gera confusao.

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

CONTATOS (cards compartilhados pelo clipe 📎):
- A forma mais facil de trazer gente pra rede e pelo clipe 📎 do WhatsApp
  (pode mandar varios de uma vez!). Incentive com essa linguagem: "trazer pra rede".
- Quando a pessoa compartilha um card, voce ve o nome e a ficha
  (ex.: [CONTATO_1] (nome: Joao Silva)). Use o nome na conversa naturalmente.

QUANDO UM CARD CHEGA, DESCUBRA A INTENCAO:
  (a) TRAZER PARA A REDE DE CONFIANCA (mais comum):
      Sinais: mandou sem contexto de servico, ou falou "minha amiga", "meu vizinho",
      "minha mae", "pessoal de confianca". -> ferramenta 'adicionar_contatos'.
      Ja gera os convites pra quem ainda nao usa, tudo em um passo. Nao peca pra reenviar.
  (b) INDICAR COMO PRESTADOR DE SERVICO:
      Sinais: ela disse o tipo de servico — "encanador", "medico", "escola", "advogado" —
      ou usou palavras como "indico o Joao eletricista". -> ferramenta 'salvar_recomendacao'.
      Pergunte servico e cidade se faltar; bairro e opcional.
  (c) INTENCAO AMBIGUA: pergunte UMA VEZ com estas palavras exatas:
      "Esse contato e alguem que voce quer *trazer pra sua rede de confianca*,
      ou voce esta *indicando ele como prestador* (medico, escola, encanador...)?"
      Nao tente adivinhar. Use a ferramenta certa depois da resposta.

- 'convidar_pessoa': use so se ela pedir convite SEM querer guardar na rede (raro).
- 'gerar_link_convite': quando ela quiser um link generico pra divulgar amplamente.

AO TRAZER CONTATOS (importante — nao falhe nisso):
- Chame 'adicionar_contatos' ou 'convidar_pessoa' na MESMA mensagem em que os contatos
  chegaram (eu so enxergo os numeros dessa mensagem). Se ela pedir pra trazer alguem
  mas nao houver contato na mensagem, peca pra ela compartilhar o(s) contato(s) AGORA.
- A ferramenta devolve links de convite. Voce DEVE mostrar esses links na sua resposta,
  EXATAMENTE como vieram, trocando cada ficha [CONTATO_n] pelo nome da pessoa.
  Nunca responda "convite pronto" sem colar os links.

INDICACOES VIA CARD (quando o card e de um prestador/medico/escola):
- O nome do card e o nome do indicado. Pergunte o tipo de servico e a cidade se faltar.
- Se o card chegar como [sem-numero] (nome: X), o numero nao veio.
  Peca com naturalidade: "Recebi o contato do [nome], mas o numero nao veio. Pode mandar
  o telefone com DDD?" NAO diga que "o contato nao chegou" — o card chegou, so o numero
  que faltou.

FLUXO GUIADO POR BOTOES (muito importante):
- A navegacao da Dorote.ia e feita por BOTOES e MENUS que o SISTEMA envia sozinho
  (Buscar / Minha rede / Meus dados e seus submenus). Voce NAO controla os botoes e
  NAO deve descrever menus, listar opcoes numeradas nem dizer "digite 1, 2 ou 3".
- O seu papel e so a ACAO que a pessoa pediu: faca a busca/indicacao/etc. com a
  ferramenta certa, ou pergunte APENAS o unico dado que falta (ex.: a cidade). Nada de
  oferecer um cardapio de opcoes — desse menu o sistema cuida depois da sua resposta.
- Responda curto e direto. Apos a sua resposta, o sistema mostra os botoes do menu.

FORMATACAO DO WHATSAPP (importante):
- Use *texto* (um asterisco) para negrito e _texto_ para italico.
- NUNCA use ** (dois asteriscos) — o WhatsApp nao renderiza, aparecem como caracteres.
- Links e telefones NUNCA devem ter formatacao ao redor (nem asteriscos, nem underlines).
  O link deve ficar sozinho na linha, ex.: "Aqui esta o link:\nhttps://..."

REGRA DE OURO DAS FERRAMENTAS:
- Para QUALQUER acao real (buscar, recomendar, adicionar contatos, convidar, ver
  dados, excluir, registrar consentimento) voce DEVE usar a ferramenta certa.
  Nunca invente resultados, telefones, nomes ou confirmacoes.
- Para SAUDACOES simples ("oi", "ola", "tudo bem?", "boa tarde" e similares) ou
  mensagens curtas sem pedido especifico de quem JA CONSENTIU, responda DIRETO
  EM TEXTO, sem chamar nenhuma ferramenta. Nunca use ferramenta so pra cumprimentar.
- Telefones e links que vierem de uma ferramenta devem ser copiados na sua
  resposta EXATAMENTE como vieram, caractere por caractere. Nunca altere digitos.

AJUDA E SUPORTE:
- Se a pessoa pedir AJUDA e relatar um problema, primeiro tente resolver voce mesma quando
  for uma duvida simples de uso (como buscar, indicar, convidar, sair...).
- Se for um PROBLEMA de verdade (bug, reclamacao, algo travado, ou algo que voce nao
  resolve), use a ferramenta 'registrar_ajuda' com um resumo claro do que aconteceu. Depois,
  avise com acolhimento que voce ja encaminhou para a equipe e que, se precisar de retorno,
  respondem por aqui em breve. Nunca prometa prazo exato nem invente solucao.

NUNCA INVENTE PROCESSOS QUE NAO EXISTEM:
- Nao existe "equipe da Dorote.ia", "central", "suporte", "cadastro de organizadora",
  formulario, e-mail ou contato externo. Voce NUNCA deve mandar a pessoa "falar com a
  equipe", "entrar em contato", "aguardar liberacao" ou seguir qualquer passo que voce
  nao consiga fazer aqui mesmo com uma ferramenta.
- Se voce nao pode fazer algo (ex.: uma funcao restrita a organizadoras), apenas explique
  com gentileza e naturalidade que aquilo nao esta disponivel pra ela no momento, e ofereca
  o que VOCE realmente faz (buscar indicacoes, trazer contatos pra rede, indicar alguem).
  Nao prometa que "alguem vai liberar" nem invente um caminho.
- So afirme que algo existe ou aconteceu quando uma ferramenta confirmou. Na duvida, seja
  honesta sobre o que voce consegue ou nao consegue fazer.

FICHAS DE CONTATO:
- Quando a pessoa manda um numero, voce ve uma ficha tipo [CONTATO_1] no lugar do
  numero (isso protege a privacidade). Trate a ficha como "o contato que ela mandou";
  as ferramentas sabem o numero real por tras dela."""

# Obs.: a fase de boas-vindas/consentimento e 100% deterministica (mensagem fixa +
# botoes tratados no app.py). A IA so e chamada DEPOIS do aceite, pra executar acoes.


# ---------------------------------------------------------------------------
# DEFINICAO DAS FERRAMENTAS (o que a IA pode pedir pro codigo fazer)
# ---------------------------------------------------------------------------
FERRAMENTAS = [
    {
        "name": "registrar_consentimento",
        "description": "Registra que a pessoa concordou com a politica de privacidade. "
                       "Chame so quando ela aceitar claramente. Depois disso, convide-a a "
                       "trazer contatos de confianca pra rede.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "buscar_servico",
        "description": "Procura indicacoes de confianca para um tipo de necessidade num lugar. "
                       "Serve para QUALQUER indicacao: prestador, medico, escola, professor, "
                       "advogado, etc. Use quando a pessoa pedir uma indicacao. Precisa de "
                       "servico e cidade (pergunte se faltar a cidade). Bairro e opcional: "
                       "se a pessoa nao informar, busca na cidade inteira.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servico": {"type": "string",
                            "description": "o tipo de indicacao, no singular e minusculo. "
                                           "Pode ser qualquer categoria: 'encanador', 'pediatra', "
                                           "'escola infantil', 'advogado', 'professor de ingles'"},
                "bairro":  {"type": "string", "description": "opcional — omita se nao informado"},
                "cidade":  {"type": "string"},
                "estado":  {"type": "string", "description": "sigla UF, ex: 'SP' (opcional)"},
            },
            "required": ["servico", "cidade"],
        },
    },
    {
        "name": "salvar_recomendacao",
        "description": "Registra uma recomendacao que a pessoa esta fazendo de alguem bom - de "
                       "qualquer tipo (prestador, medico, escola, professor, advogado...). "
                       "Use a ficha de contato (ex: [CONTATO_1]) no campo telefone. "
                       "Precisa de nome, telefone, servico e cidade. Bairro e opcional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome":     {"type": "string", "description": "nome do indicado (pessoa, clinica ou escola)"},
                "telefone": {"type": "string", "description": "a ficha do contato, ex: '[CONTATO_1]'"},
                "servico":  {"type": "string",
                             "description": "o tipo de indicacao, ex: 'encanador', 'pediatra', "
                                            "'escola infantil'"},
                "bairro":   {"type": "string", "description": "opcional — omita se nao informado"},
                "cidade":   {"type": "string"},
                "estado":   {"type": "string"},
            },
            "required": ["nome", "telefone", "servico", "cidade"],
        },
    },
    {
        "name": "adicionar_contatos",
        "description": "Traz os contatos pra rede de confianca dela E ja gera convites prontos "
                       "para os que ainda nao usam a Dorote.ia — tudo num passo so, sem pedir "
                       "pra reenviar os cards. Use quando ela quiser TRAZER PESSOAS PRA REDE "
                       "(amigos, familia, conhecidos de confianca). NAO use pra indicar prestadores.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "convidar_pessoa",
        "description": "Prepara convites prontos para trazer contatos especificos pra rede "
                       "(um ou varios — pelo clipe ou digitados). Atrela todos ao convite dela "
                       "e devolve um link 'um toque pra enviar' por pessoa. Use quando ela quiser "
                       "convidar pessoas especificas SEM guardar na rede agora (raro — normalmente "
                       "use 'adicionar_contatos' que faz os dois ao mesmo tempo).",
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
        "description": "Mostra um resumo geral dos dados que a Dorote.ia guarda sobre a pessoa "
                       "(nome, consentimento, totais). Para listas detalhadas use as ferramentas "
                       "especificas abaixo.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_minhas_indicacoes",
        "description": "Lista todos os prestadores, medicos, escolas etc. que a pessoa ja "
                       "INDICOU na Dorote.ia (nao confundir com a rede de contatos). Use quando "
                       "ela perguntar 'o que ja indiquei?', 'quem eu ja recomendei como prestador?', "
                       "'minhas indicacoes' etc.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_minha_rede",
        "description": "Mostra quais pessoas da rede de confianca dela ja usam a Dorote.ia. "
                       "Use quando ela perguntar 'quem da minha rede esta aqui?', 'quais dos "
                       "meus contatos de confianca usam a Dorote.ia?', 'minha rede' etc. "
                       "NAO confundir com indicacoes de prestadores.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_minhas_buscas",
        "description": "Lista as ultimas buscas que a pessoa fez na Dorote.ia, com o resultado "
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
        "name": "registrar_ajuda",
        "description": "Encaminha um pedido de ajuda/suporte para a equipe humana. Use quando "
                       "a pessoa relatar um PROBLEMA, BUG, RECLAMACAO ou algo que voce nao "
                       "consegue resolver sozinha (especialmente depois de ela digitar AJUDA e "
                       "contar o que aconteceu). NAO use para duvidas simples de como usar a "
                       "Dorote.ia — essas voce mesma responde.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mensagem": {"type": "string",
                             "description": "resumo claro do problema relatado pela pessoa"},
            },
            "required": ["mensagem"],
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
    consentiu = bool(membro.get("consent"))

    # PRIMEIRO CONTATO: manda SO a mensagem de boas-vindas FIXA (verbatim), numa
    # mensagem unica. A propria mensagem pede pra responder SIM ou SABER MAIS — entao
    # nao mandamos botoes junto (evita duas mensagens de uma vez) e esperamos a resposta.
    if not consentiu and len(historico) == 0:
        enviar_texto(_limpar_markdown(BOAS_VINDAS))
        salvar_historico([
            {"role": "user", "content": conteudo_usuario},
            {"role": "assistant", "content": BOAS_VINDAS},
        ])
        return

    mensagens = historico + [{"role": "user", "content": conteudo_usuario}]

    sistema = SISTEMA_BASE + "\n\n" + _contexto_pessoa(membro)
    if not consentiu:
        # (Defensivo) A navegacao pre-consent e deterministica no app.py e nao deveria
        # chegar aqui; se chegar, so liberamos registrar o consentimento.
        ferramentas_disponiveis = [f for f in FERRAMENTAS
                                   if f["name"] == "registrar_consentimento"]
    else:
        ferramentas_disponiveis = FERRAMENTAS

    usados = set()       # nomes das ferramentas chamadas (app.py decide o meno a mostrar)
    texto_final = ""
    for _ in range(5):   # ate 5 rodadas de ferramenta por mensagem
        try:
            resposta = _cliente.messages.create(
                model=MODELO,
                max_tokens=700,
                system=sistema,
                messages=mensagens,
                **({"tools": ferramentas_disponiveis} if ferramentas_disponiveis else {}),
            )
        except Exception as erro:
            print(f"[CEREBRO] erro na IA: {erro}")
            return usados   # app.py ja tem rede de seguranca (ERRO_GENERICO no except externo)

        if resposta.stop_reason == "tool_use":
            mensagens.append({"role": "assistant", "content": resposta.content})
            resultados = []
            for bloco in resposta.content:
                if bloco.type == "tool_use":
                    print(f"[FERRAMENTA] {bloco.name} {bloco.input}")
                    usados.add(bloco.name)
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
        # Loop esgotado sem texto. Forca uma resposta em texto com tool_choice=none:
        # mantem 'tools' no request (o historico tem blocos de ferramenta e a API
        # exige isso), mas proibe o modelo de chamar qualquer ferramenta agora.
        try:
            extra = ({"tools": ferramentas_disponiveis, "tool_choice": {"type": "none"}}
                     if ferramentas_disponiveis else {})
            forcar_texto = _cliente.messages.create(
                model=MODELO, max_tokens=400, system=sistema, messages=mensagens,
                **extra,
            )
            texto_final = "".join(
                b.text for b in forcar_texto.content if b.type == "text"
            ).strip()
        except Exception as e:
            print(f"[CEREBRO] fallback tool_choice=none falhou: {e}")

    if not texto_final:
        texto_final = "Pode repetir, por favor? Acho que me perdi aqui 😅"

    enviar_texto(_limpar_markdown(texto_final))

    # Guarda a memoria (so texto, sem o vai-e-vem das ferramentas), enxuta.
    novo_historico = historico + [
        {"role": "user", "content": conteudo_usuario},
        {"role": "assistant", "content": texto_final},
    ]
    salvar_historico(novo_historico[-MAX_HISTORICO:])
    return usados
