# nlu.py
# ---------------------------------------------------------------------------
# ENTENDIMENTO DE LINGUAGEM (NLU) - usa a Claude (Anthropic) pra ler uma frase
# solta e extrair {servico, bairro}. Ex.: "preciso de um encanador em Perdizes"
# vira {"servico": "encanador", "bairro": "Perdizes"}.
# ---------------------------------------------------------------------------

import json
from anthropic import Anthropic

# Cria o "cliente" da Claude. Ele le a chave secreta da variavel de ambiente
# ANTHROPIC_API_KEY (que voce cadastrou no Render) - nada de chave no codigo.
_cliente = Anthropic()

# Instrucoes que dizem a Claude exatamente o que fazer.
_INSTRUCOES = (
    "Você recebe uma mensagem de WhatsApp em português do Brasil e extrai o pedido de "
    "serviço. IMPORTANTE: corrija a ortografia e os ACENTOS de tudo que devolver, "
    "escrevendo em português correto. Exemplos de correção: 'tecnico de fogao' → "
    "'técnico de fogão'; 'medico' → 'médico'; 'eletricista em perdizes' → serviço "
    "'eletricista', bairro 'Perdizes'.\n"
    "- 'servico': no singular e em minúsculas, com ortografia e acentos CORRETOS "
    "(ex.: 'encanador', 'diarista', 'técnico de fogão', 'médico'). Se a mensagem NÃO for "
    "um pedido de serviço, devolva string vazia.\n"
    "- 'bairro': inicial maiúscula e acentos corretos (ex.: 'Perdizes', 'Pinheiros'). "
    "Vazio se não for mencionado.\n"
    "- 'cidade': inicial maiúscula (ex.: 'São Paulo', 'Belo Horizonte'). Vazio se não for "
    "mencionada — não infira a partir do bairro.\n"
    "- 'estado': sigla maiúscula (ex.: 'SP', 'MG'). Vazio se não mencionado; pode inferir "
    "da cidade quando inequívoco.\n"
    "- 'detalhe': qualquer CARACTERÍSTICA específica pedida além do serviço e do bairro "
    "(ex.: 'que atenda fim de semana', 'especialista em geladeira', 'que aceite convênio', "
    "'para criança'). Curto e em português correto. Vazio se não houver."
)

_ESQUEMA = {
    "type": "object",
    "properties": {
        "servico": {"type": "string"},
        "bairro":  {"type": "string"},
        "cidade":  {"type": "string"},
        "estado":  {"type": "string"},
        "detalhe": {"type": "string"},
    },
    "required": ["servico", "bairro", "cidade", "estado", "detalhe"],
    "additionalProperties": False,
}


def extrair_servico_bairro(texto):
    """Pede pra Claude entender a frase e devolve {servico, bairro, cidade, estado,
    detalhe} — tudo com ortografia/acentos corrigidos. Se algo der errado, devolve os
    campos vazios; assim a Doroteia nao quebra, so deixa de entender aquele pedido."""
    try:
        resposta = _cliente.messages.create(
            model="claude-opus-4-8",          # o modelo da Claude que vamos usar
            max_tokens=250,                   # a resposta e curtinha (so o JSON)
            system=_INSTRUCOES,               # as instrucoes acima
            messages=[{"role": "user", "content": texto}],   # a frase da pessoa
            output_config={"format": {"type": "json_schema", "schema": _ESQUEMA}},
        )
        # A resposta vem como texto contendo o JSON; transformamos em dicionario.
        bloco_texto = next(b for b in resposta.content if b.type == "text")
        return json.loads(bloco_texto.text)
    except Exception as erro:
        print(f"[NLU] erro ao interpretar a mensagem: {erro}")
        return {"servico": "", "bairro": "", "cidade": "", "estado": "", "detalhe": ""}


# ---------------------------------------------------------------------------
# Extrair os dados de uma RECOMENDACAO (Camada 6): nome, telefone, servico, bairro.
# ---------------------------------------------------------------------------
_INSTRUCOES_REC = (
    "Voce recebe uma mensagem onde a pessoa esta RECOMENDANDO um prestador de "
    "servico. Extraia seis campos:\n"
    "- 'nome': nome do prestador (ex: 'Joao'). Vazio se nao houver.\n"
    "- 'telefone': o telefone como aparece, com DDD. Vazio se nao houver.\n"
    "- 'servico': singular e minusculo (ex: 'encanador'). Vazio se nao houver.\n"
    "- 'bairro': inicial maiuscula (ex: 'Perdizes'). Vazio se nao houver.\n"
    "- 'cidade': inicial maiuscula (ex: 'Sao Paulo'). Vazio se nao houver.\n"
    "- 'estado': sigla maiuscula (ex: 'SP'). Vazio se nao houver. Pode inferir "
    "a partir da cidade quando inequivoco."
)

_ESQUEMA_REC = {
    "type": "object",
    "properties": {
        "nome":     {"type": "string"},
        "telefone": {"type": "string"},
        "servico":  {"type": "string"},
        "bairro":   {"type": "string"},
        "cidade":   {"type": "string"},
        "estado":   {"type": "string"},
    },
    "required": ["nome", "telefone", "servico", "bairro", "cidade", "estado"],
    "additionalProperties": False,
}


def extrair_recomendacao(texto):
    """Le uma mensagem de recomendacao e devolve {nome, telefone, servico, bairro}.
    Em caso de erro, devolve tudo vazio (a Doroteia pede pra mandar de novo)."""
    try:
        resposta = _cliente.messages.create(
            model="claude-opus-4-8",
            max_tokens=300,
            system=_INSTRUCOES_REC,
            messages=[{"role": "user", "content": texto}],
            output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_REC}},
        )
        bloco_texto = next(b for b in resposta.content if b.type == "text")
        return json.loads(bloco_texto.text)
    except Exception as erro:
        print(f"[NLU] erro ao interpretar a recomendacao: {erro}")
        return {"nome": "", "telefone": "", "servico": "", "bairro": "", "cidade": "", "estado": ""}


# ---------------------------------------------------------------------------
# Fluxo deterministico de INDICACAO: separa, de um texto solto "como num grupo",
# o servico, o bairro/regiao e o motivo (detalhe) da indicacao. O nome quase
# sempre ja foi capturado antes, mas e lido se a pessoa o repetir (correcao).
# ---------------------------------------------------------------------------
_INSTRUCOES_IND = (
    "Voce recebe uma mensagem em portugues do Brasil onde alguem esta INDICANDO um "
    "profissional para uma rede de confianca. Extraia quatro campos (deixe vazio o que "
    "nao aparecer):\n"
    "- 'nome': nome do profissional. Normalmente NAO aparece nesta mensagem; so "
    "preencha se estiver claro.\n"
    "- 'servico': o que a pessoa faz, no singular e minusculo (ex: 'eletricista', "
    "'manicure', 'professor de ingles').\n"
    "- 'bairro': regiao de atendimento, como veio (ex: 'Pinheiros', 'cidade toda', "
    "'nao sei').\n"
    "- 'detalhe': o motivo/elogio da indicacao, resumido com as palavras da propria "
    "pessoa (ex: 'fez os doces do batizado, caprichou e foi pontual')."
)

_ESQUEMA_IND = {
    "type": "object",
    "properties": {
        "nome":    {"type": "string"},
        "servico": {"type": "string"},
        "bairro":  {"type": "string"},
        "detalhe": {"type": "string"},
    },
    "required": ["nome", "servico", "bairro", "detalhe"],
    "additionalProperties": False,
}


def extrair_indicacao(texto):
    """Le um texto de indicacao e devolve {nome, servico, bairro, detalhe}.
    Em caso de erro, devolve tudo vazio (o fluxo pede pra reenviar)."""
    try:
        resposta = _cliente.messages.create(
            model="claude-opus-4-8",
            max_tokens=400,
            system=_INSTRUCOES_IND,
            messages=[{"role": "user", "content": texto}],
            output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_IND}},
        )
        bloco_texto = next(b for b in resposta.content if b.type == "text")
        return json.loads(bloco_texto.text)
    except Exception as erro:
        print(f"[NLU] erro ao interpretar a indicacao: {erro}")
        return {"nome": "", "servico": "", "bairro": "", "detalhe": ""}


# ---------------------------------------------------------------------------
# Perfil PROFISSIONAL: a pessoa descreve o proprio trabalho num texto so e a
# Claude organiza em campos (categoria/subcategoria/regiao/diferenciais/contato),
# que o codigo valida com botoes antes de gravar.
# ---------------------------------------------------------------------------
_INSTRUCOES_PERFIL = (
    "Voce recebe a descricao que um PROFISSIONAL fez do proprio trabalho (PT-BR). "
    "Organize em campos, sem inventar nada que nao esteja no texto:\n"
    "- 'categoria': a categoria principal do servico, no singular e minuscula "
    "(ex.: 'eletricista', 'confeiteira', 'professor de ingles', 'tecnico de geladeira').\n"
    "- 'subcategoria': a especialidade/detalhe, se houver (ex.: 'bolos de casamento', "
    "'maquina de lavar', 'ingles para criancas'). Vazio se nao houver.\n"
    "- 'regiao': onde atende (ex.: 'zona leste de Sao Paulo', 'Pinheiros', 'cidade toda', "
    "'online'). Vazio se nao houver.\n"
    "- 'diferenciais': no que e forte — rapidez, garantia, especialidades, experiencia. "
    "Vazio se nao houver.\n"
    "- 'contato': formas de pagamento e de contato (Pix, cartao, dinheiro, Instagram, site, "
    "endereco). Vazio se nao houver."
)

_ESQUEMA_PERFIL = {
    "type": "object",
    "properties": {
        "categoria":    {"type": "string"},
        "subcategoria": {"type": "string"},
        "regiao":       {"type": "string"},
        "diferenciais": {"type": "string"},
        "contato":      {"type": "string"},
    },
    "required": ["categoria", "subcategoria", "regiao", "diferenciais", "contato"],
    "additionalProperties": False,
}


def extrair_perfil_profissional(texto):
    """Le a descricao do profissional e devolve os campos organizados.
    Em caso de erro, devolve tudo vazio (o fluxo pede pra reenviar)."""
    try:
        resposta = _cliente.messages.create(
            model="claude-opus-4-8",
            max_tokens=500,
            system=_INSTRUCOES_PERFIL,
            messages=[{"role": "user", "content": texto}],
            output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_PERFIL}},
        )
        bloco_texto = next(b for b in resposta.content if b.type == "text")
        return json.loads(bloco_texto.text)
    except Exception as erro:
        print(f"[NLU] erro ao interpretar o perfil: {erro}")
        return {"categoria": "", "subcategoria": "", "regiao": "", "diferenciais": "", "contato": ""}
