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
    "Voce recebe uma mensagem de WhatsApp em portugues do Brasil e extrai duas "
    "informacoes: qual SERVICO a pessoa procura e em qual BAIRRO.\n"
    "- 'servico': no singular e em minusculas (ex: 'encanador', 'eletricista', "
    "'diarista'). Se a mensagem NAO for um pedido de servico, devolva string vazia.\n"
    "- 'bairro': com a inicial maiuscula (ex: 'Perdizes'). Se nenhum bairro for "
    "citado, devolva string vazia."
)

# O "molde" da resposta: obrigamos a Claude a responder neste formato exato (JSON).
_ESQUEMA = {
    "type": "object",
    "properties": {
        "servico": {"type": "string"},
        "bairro": {"type": "string"},
    },
    "required": ["servico", "bairro"],
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
        return {"servico": "", "bairro": ""}
