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
    "Voce recebe uma mensagem de WhatsApp em portugues do Brasil e extrai quatro "
    "informacoes: qual SERVICO a pessoa procura, em qual BAIRRO, em qual CIDADE e "
    "em qual ESTADO.\n"
    "- 'servico': no singular e em minusculas (ex: 'encanador', 'eletricista', "
    "'diarista'). Se a mensagem NAO for um pedido de servico, devolva string vazia.\n"
    "- 'bairro': com a inicial maiuscula (ex: 'Perdizes', 'Savassi'). Vazio se "
    "nao for mencionado.\n"
    "- 'cidade': com a inicial maiuscula (ex: 'Sao Paulo', 'Belo Horizonte', "
    "'Rio de Janeiro'). Vazio se nao for mencionada - nao infira a partir do bairro.\n"
    "- 'estado': sigla em maiusculas (ex: 'SP', 'MG', 'RJ'). Vazio se nao "
    "for mencionado. Pode inferir a partir da cidade quando inequivoco "
    "(ex: cidade='Sao Paulo' -> estado='SP', cidade='Salvador' -> estado='BA')."
)

_ESQUEMA = {
    "type": "object",
    "properties": {
        "servico": {"type": "string"},
        "bairro":  {"type": "string"},
        "cidade":  {"type": "string"},
        "estado":  {"type": "string"},
    },
    "required": ["servico", "bairro", "cidade", "estado"],
    "additionalProperties": False,
}


def extrair_servico_bairro(texto):
    """Pede pra Claude entender a frase e devolve {'servico': ..., 'bairro': ...}.
    Se algo der errado (ex: sem credito), devolve os dois campos vazios -
    assim a Doroteia nao quebra, so deixa de entender aquele pedido."""
    try:
        resposta = _cliente.messages.create(
            model="claude-opus-4-8",          # o modelo da Claude que vamos usar
            max_tokens=200,                   # a resposta e curtinha (so o JSON)
            system=_INSTRUCOES,               # as instrucoes acima
            messages=[{"role": "user", "content": texto}],   # a frase da pessoa
            output_config={"format": {"type": "json_schema", "schema": _ESQUEMA}},
        )
        # A resposta vem como texto contendo o JSON; transformamos em dicionario.
        bloco_texto = next(b for b in resposta.content if b.type == "text")
        return json.loads(bloco_texto.text)
    except Exception as erro:
        print(f"[NLU] erro ao interpretar a mensagem: {erro}")
        return {"servico": "", "bairro": "", "cidade": "", "estado": ""}


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
