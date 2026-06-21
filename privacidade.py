# privacidade.py
# ===========================================================================
# NUCLEO DE PRIVACIDADE DA DOROTEIA  (item 5 do briefing)
# ---------------------------------------------------------------------------
# Este arquivo concentra a parte mais sensivel do produto: transformar um
# numero de telefone num CODIGO IRREVERSIVEL (hash), para guardarmos o grafo
# de "quem conhece quem" SEM nunca guardar numeros de telefone de nao-membros.
#
# Foi deixado isolado de proposito, pra facilitar a revisao por um
# especialista de seguranca / DPO. Toda a explicacao detalhada esta em
# docs/privacidade-hash.md.
# ===========================================================================

import os
import hmac
import hashlib

import phonenumbers   # biblioteca do Google pra entender/validar numeros de telefone


# ---------------------------------------------------------------------------
# A CHAVE SECRETA (o "pepper").
# Lemos da variavel de ambiente CONTACT_HASH_KEY (que vive so no Render).
# Ela NUNCA aparece escrita aqui e NUNCA e guardada no banco. Sem ela, e
# inviavel reverter os hashes de volta para os numeros originais.
# ---------------------------------------------------------------------------
_CHAVE_SECRETA = os.environ["CONTACT_HASH_KEY"].encode("utf-8")


def normalizar_e164(numero_bruto, regiao_padrao="BR"):
    """Padroniza um numero para o formato internacional E.164 (ex.: +5511999998888).

    Por que padronizar ANTES de tudo? Para que o MESMO telefone gere SEMPRE o
    mesmo codigo. "(11) 99999-8888", "11999998888" e "+55 11 99999 8888"
    precisam virar exatamente a mesma string, senao o grafo nao casaria.

    Devolve a string em E.164, ou None se o numero for invalido.
    """
    try:
        numero = phonenumbers.parse(numero_bruto, regiao_padrao)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(numero):
        return None
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


def calcular_contact_hash(numero_e164):
    """Transforma um numero E.164 no codigo irreversivel (contact_hash).

    Usa HMAC-SHA256 com a CHAVE SECRETA. Propriedades importantes:
      - Deterministico: mesmo numero + mesma chave  =>  sempre o mesmo codigo
        (por isso da pra comparar dois codigos e descobrir quem se conhece).
      - Irreversivel na pratica: do codigo NAO se volta para o numero.
      - Resistente a forca-bruta: sem a CHAVE SECRETA, um atacante nao consegue
        testar todos os numeros possiveis ate achar o que gera aquele codigo.
    """
    return hmac.new(
        _CHAVE_SECRETA,                 # a chave secreta (pepper)
        numero_e164.encode("utf-8"),    # o numero ja padronizado
        hashlib.sha256,                 # o algoritmo de embaralhamento
    ).hexdigest()                       # devolve o codigo como texto


def extrair_numeros_de_texto(texto, regiao_padrao="BR"):
    """Acha numeros de telefone VALIDOS dentro de um texto livre.

    Serve para a fase de testes, em que os contatos chegam digitados como
    texto. Devolve uma lista de numeros em E.164, ja sem repetidos.
    """
    encontrados = []
    for ocorrencia in phonenumbers.PhoneNumberMatcher(texto, regiao_padrao):
        e164 = phonenumbers.format_number(ocorrencia.number, phonenumbers.PhoneNumberFormat.E164)
        if e164 not in encontrados:
            encontrados.append(e164)
    return encontrados
