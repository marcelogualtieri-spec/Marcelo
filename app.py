# app.py
# ---------------------------------------------------------------------------
# DOROTEIA - Camada 4: receber contatos, virar HASH e montar o grafo (item 5)
#
# Fluxo de vida de uma pessoa nesta etapa:
#   1. Manda a 1a mensagem        -> e cadastrada + recebe as boas-vindas (7.1)
#   2. Responde SIM               -> consentimento gravado + pedido de contatos (7.2)
#   3. Manda numeros de contatos  -> viram HASH em "edges" e os crus sao descartados (7.3)
#
# A parte sensivel (normalizar + hashear) fica no arquivo privacidade.py.
# ---------------------------------------------------------------------------

import os
from datetime import datetime, timezone
from html import escape

from flask import Flask, request, Response
from supabase import create_client

# Funcoes do nucleo de privacidade (ver privacidade.py e docs/privacidade-hash.md)
from privacidade import calcular_contact_hash, extrair_numeros_de_texto


# ---------------------------------------------------------------------------
# CONEXAO COM O BANCO (Supabase) - credenciais vem das variaveis de ambiente.
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)


# ===========================================================================
# FUNCOES AUXILIARES DE BANCO
# ===========================================================================

def buscar_membro(wa_id):
    """Procura a pessoa com aquele numero de WhatsApp. Devolve os dados ou None."""
    resposta = supabase.table("members").select("*").eq("wa_id", wa_id).execute()
    if resposta.data:
        return resposta.data[0]
    return None


def criar_membro(wa_id, nome_perfil):
    """Cria um cadastro novo (ainda sem consentimento)."""
    supabase.table("members").insert({
        "wa_id": wa_id,
        "nome_perfil": nome_perfil,
        "consent": False,
    }).execute()


def registrar_consentimento(wa_id):
    """Marca que a pessoa deu o 'ok' de privacidade, com a data/hora de agora."""
    agora = datetime.now(timezone.utc).isoformat()
    supabase.table("members").update({
        "consent": True,
        "consent_at": agora,
    }).eq("wa_id", wa_id).execute()


def processar_contatos(membro, numeros_e164):
    """Coracao da Camada 4: recebe numeros JA em E.164, guarda os HASHES na
    tabela edges e DESCARTA os numeros crus (eles nunca vao para o banco).

    Devolve (total_recebido, quantos_ja_sao_membros) so para a mensagem de volta.
    """
    member_id = membro["id"]

    # Hashes que esse membro ja tem guardados, pra nao duplicar.
    existentes = supabase.table("edges").select("contact_hash").eq("member_id", member_id).execute()
    hashes_existentes = {linha["contact_hash"] for linha in existentes.data}

    registros_novos = []
    ja_membros = 0

    for numero in numeros_e164:
        # Esse contato ja e um membro? Consultamos pelo numero, que existe aqui
        # apenas de forma transitoria (na memoria) - nao guardamos numero de nao-membro.
        if buscar_membro(numero) is not None:
            ja_membros += 1

        # Transforma o numero no codigo irreversivel.
        codigo = calcular_contact_hash(numero)

        # So agenda pra gravar se ainda nao existir (a tabela tem UNIQUE de qualquer jeito).
        if codigo not in hashes_existentes:
            registros_novos.append({"member_id": member_id, "contact_hash": codigo})
            hashes_existentes.add(codigo)

    # Grava de uma vez so os hashes novos. Os numeros crus "somem" aqui:
    # nao escrevemos nenhum numero de nao-membro em lugar nenhum.
    if registros_novos:
        supabase.table("edges").insert(registros_novos).execute()

    return len(numeros_e164), ja_membros


# ===========================================================================
# MONTAGEM DAS RESPOSTAS
# ===========================================================================

def resposta_whatsapp(texto):
    """Embrulha um texto no formato (TwiML) que a Twilio entende e devolve."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escape(texto)}</Message>
</Response>"""
    return Response(twiml, mimetype="application/xml")


def texto_contatos_recebidos(total, ja_membros):
    """Monta a fala da tela 7.3 com base em quantos contatos chegaram."""
    restantes = total - ja_membros
    msg = f"Recebi {total} contato(s), valeu! 🙌\n\n"
    if ja_membros > 0:
        msg += (f"Desses, {ja_membros} ja usam a Doroteia - entao as indicacoes "
                "deles ja podem aparecer pra voce com nome.\n")
    else:
        msg += ("Nenhum deles entrou ainda - mas relaxa: assim que entrarem, "
                "as indicacoes aparecem sozinhas.\n")
    if restantes > 0:
        msg += f"\nOs outros {restantes} ainda nao entraram. Em breve vou te dar um link pra convidar. 😉"
    return msg


# ===========================================================================
# TEXTOS FIXOS DA DOROTEIA
# ===========================================================================

TEXTO_BOAS_VINDAS = (
    "Oi! Aqui e a Doroteia. Funciono como aquele amigo que sempre tem a "
    "indicacao certa - so que dentro do WhatsApp.\n\n"
    "Voce me pede um servico (tipo \"preciso de um encanador em Perdizes\") e "
    "eu te digo quem *gente que voce conhece* ja indicou.\n\n"
    "Pra comecar, preciso do seu ok:\n"
    "- Seu nome pode aparecer como quem indicou, so pros seus contatos que "
    "tambem usam a Doroteia.\n"
    "- Voce nunca recebe mensagem de quem voce nao chamou.\n"
    "- Seu telefone nunca e repassado a ninguem.\n\n"
    "Topa? Responda *SIM* pra comecar, ou *SABER MAIS* pra eu explicar melhor."
)

TEXTO_SABER_MAIS = (
    "Claro! Em resumo:\n"
    "- *Privacidade:* a ligacao entre voce e seus contatos e guardada de forma "
    "embaralhada (ninguem ve numeros de telefone).\n"
    "- *Seu telefone* nunca e passado pra ninguem.\n"
    "- Voce so recebe mensagem se chamar primeiro ou entrar por convite.\n"
    "- Quando quiser, pode pedir pra sair que eu apago tudo.\n\n"
    "Topa comecar? Responda *SIM*."
)

TEXTO_PRECISA_CONSENTIR = (
    "Pra gente comecar, eu preciso do seu ok 🙂\n"
    "Responda *SIM* pra topar, ou *SABER MAIS* pra eu explicar."
)

TEXTO_PEDIR_CONTATOS = (
    "Show! Agora vamos te deixar bem servido. 🙌\n\n"
    "Me manda os numeros das pessoas em quem voce confia. Por enquanto (fase "
    "de testes) mande em texto mesmo - um por linha ou separados por virgula.\n"
    "Ex: (11) 99999-8888, (11) 98888-7777\n\n"
    "Quanto mais voce adicionar, melhor: quando voce pedir um servico, eu "
    "consigo te dizer quais delas ja indicaram alguem bom."
)


# ===========================================================================
# A PORTA PRINCIPAL: onde a Twilio bate quando chega uma mensagem
# ===========================================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    texto_recebido = request.form.get("Body", "").strip()
    remetente = request.form.get("From", "")
    nome_perfil = request.form.get("ProfileName", "")
    wa_id = remetente.replace("whatsapp:", "")

    print(f"Mensagem de {wa_id} ({nome_perfil}): {texto_recebido}")

    membro = buscar_membro(wa_id)

    # CASO 1 - pessoa nova: cadastra e manda as boas-vindas.
    if membro is None:
        criar_membro(wa_id, nome_perfil)
        return resposta_whatsapp(TEXTO_BOAS_VINDAS)

    # CASO 2 - ja consentiu: o caminho agora e receber contatos.
    if membro["consent"]:
        numeros = extrair_numeros_de_texto(texto_recebido)
        if numeros:
            total, ja_membros = processar_contatos(membro, numeros)
            return resposta_whatsapp(texto_contatos_recebidos(total, ja_membros))
        # Consentiu mas nao mandou numeros: pede os contatos.
        return resposta_whatsapp(TEXTO_PEDIR_CONTATOS)

    # CASO 3 - ja cadastrada mas AINDA NAO consentiu: interpreta a resposta.
    texto = texto_recebido.lower()
    if texto in ("sim", "sim, bora", "bora", "s"):
        registrar_consentimento(wa_id)
        # Tela 7.1 -> segue direto para o pedido de contatos (7.2).
        return resposta_whatsapp("Perfeito, anotei seu ok! ✅\n\n" + TEXTO_PEDIR_CONTATOS)
    if "saber" in texto or "mais" in texto:
        return resposta_whatsapp(TEXTO_SABER_MAIS)
    return resposta_whatsapp(TEXTO_PRECISA_CONSENTIR)


@app.route("/", methods=["GET"])
def home():
    return "A Doroteia esta viva! 🎉"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
