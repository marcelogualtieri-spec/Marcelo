# app.py
# ---------------------------------------------------------------------------
# DOROTEIA - cerebro do bot. Recebe a mensagem do WhatsApp (via Twilio),
# decide o que fazer e responde. As FALAS ficam todas em textos.py.
# ---------------------------------------------------------------------------

import os
import re
import secrets
import string
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from flask import Flask, request, Response
from supabase import create_client

# Nucleo de privacidade (Camada 4) e entendimento de linguagem (Camada 5).
from privacidade import calcular_contact_hash, extrair_numeros_de_texto, normalizar_e164
from nlu import extrair_servico_bairro, extrair_recomendacao

# Todas as falas da Doroteia (voce pode editar em textos.py).
import textos as t


# ---------------------------------------------------------------------------
# CONEXAO COM O BANCO (Supabase)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)


# ===========================================================================
# AJUDINHAS DE PERSONALIZACAO (chamar a pessoa pelo nome)
# ===========================================================================

def primeiro_nome(nome_perfil):
    """Pega so o primeiro nome do perfil do WhatsApp (ou vazio se nao tiver)."""
    if nome_perfil and nome_perfil.strip():
        return nome_perfil.strip().split()[0]
    return ""


def vocativo(nome):
    """Vira ', Marcelo' quando sabemos o nome, ou '' quando nao sabemos.
    E o encaixe {voc} usado nos textos."""
    return f", {nome}" if nome else ""


# ===========================================================================
# FUNCOES DE BANCO
# ===========================================================================

def buscar_membro(wa_id):
    resposta = supabase.table("members").select("*").eq("wa_id", wa_id).execute()
    return resposta.data[0] if resposta.data else None


def buscar_membro_por_id(member_id):
    resposta = supabase.table("members").select("*").eq("id", member_id).execute()
    return resposta.data[0] if resposta.data else None


def buscar_provider(provider_id):
    resposta = supabase.table("providers").select("*").eq("id", provider_id).execute()
    return resposta.data[0] if resposta.data else None


def criar_membro(wa_id, nome_perfil, invited_by=None):
    supabase.table("members").insert({
        "wa_id": wa_id,
        "nome_perfil": nome_perfil,
        "consent": False,
        "invited_by": invited_by,   # quem convidou (None se chegou sozinho)
    }).execute()


def registrar_consentimento(wa_id):
    agora = datetime.now(timezone.utc).isoformat()
    supabase.table("members").update({
        "consent": True,
        "consent_at": agora,
    }).eq("wa_id", wa_id).execute()


def definir_estado(wa_id, estado):
    """Guarda em que ponto da conversa a pessoa esta (ex: 'recomendando')."""
    supabase.table("members").update({"estado": estado}).eq("wa_id", wa_id).execute()


def contar(tabela, member_id):
    return len(supabase.table(tabela).select("id").eq("member_id", member_id).execute().data)


def excluir_membro(membro):
    """Apaga o membro. edges e recommendations somem junto (ON DELETE CASCADE)."""
    supabase.table("members").delete().eq("id", membro["id"]).execute()


# ===========================================================================
# CAMADA 4 - CONTATOS -> HASH -> GRAFO
# ===========================================================================

def processar_contatos(membro, numeros_e164):
    member_id = membro["id"]
    existentes = supabase.table("edges").select("contact_hash").eq("member_id", member_id).execute()
    hashes_existentes = {linha["contact_hash"] for linha in existentes.data}

    registros_novos = []
    ja_membros = 0
    for numero in numeros_e164:
        if buscar_membro(numero) is not None:
            ja_membros += 1
        codigo = calcular_contact_hash(numero)
        if codigo not in hashes_existentes:
            registros_novos.append({"member_id": member_id, "contact_hash": codigo})
            hashes_existentes.add(codigo)

    if registros_novos:
        supabase.table("edges").insert(registros_novos).execute()

    return len(numeros_e164), ja_membros


def texto_contatos_recebidos(total, ja_membros):
    restantes = total - ja_membros
    msg = t.CONTATOS_CABECALHO.format(total=total)
    msg += t.CONTATOS_TEM_MEMBROS.format(ja=ja_membros) if ja_membros > 0 else t.CONTATOS_SEM_MEMBROS
    if restantes > 0:
        msg += t.CONTATOS_RESTANTES.format(rest=restantes)
    return msg + t.RODAPE


# ===========================================================================
# CAMADA 6 - RECOMENDAR
# ===========================================================================

def tratar_recomendacao(membro, texto, voc):
    dados = extrair_recomendacao(texto)
    nome = (dados.get("nome") or "").strip() or "Prestador"
    servico = (dados.get("servico") or "").strip()
    bairro = (dados.get("bairro") or "").strip()
    telefone = normalizar_e164((dados.get("telefone") or "").strip())

    if not telefone or not servico or not bairro:
        return t.REC_INCOMPLETA

    prestador = supabase.table("providers").insert({
        "nome": nome,
        "telefone": telefone,           # telefone do prestador (E.164) - e o dado que se entrega
        "servico": servico.lower(),
        "bairro": bairro,
    }).execute().data[0]

    supabase.table("recommendations").insert({
        "member_id": membro["id"],
        "provider_id": prestador["id"],
        "servico": servico.lower(),
        "bairro": bairro,
    }).execute()

    definir_estado(membro["wa_id"], "normal")
    return t.REC_OK.format(nome=nome, servico=servico, bairro=bairro, voc=voc) + t.RODAPE


# ===========================================================================
# CAMADA 7 - CONVITE
# ===========================================================================

def gerar_codigo_convite():
    alfabeto = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(6))


def obter_ou_criar_codigo(membro):
    if membro.get("invite_code"):
        return membro["invite_code"]
    codigo = gerar_codigo_convite()
    supabase.table("members").update({"invite_code": codigo}).eq("id", membro["id"]).execute()
    return codigo


def montar_link_convite(numero_bot, codigo):
    mensagem = f"Oi! Quero entrar na Doroteia 🙂 (convite: {codigo})"
    return f"https://wa.me/{numero_bot}?text={quote(mensagem)}"


def extrair_codigo_convite(texto):
    achado = re.search(r"convite:\s*([A-Za-z0-9]{6})", texto)
    return achado.group(1).upper() if achado else None


def membro_por_codigo(codigo):
    resposta = supabase.table("members").select("id").eq("invite_code", codigo).execute()
    return resposta.data[0] if resposta.data else None


# ===========================================================================
# CAMADA 5/6 - REGRAS VERDE / AMARELO / VERMELHO (item 6)
# ===========================================================================

def hash_de_membro(membro):
    numero = normalizar_e164(membro["wa_id"])
    return calcular_contact_hash(numero) if numero else None


def existe_vinculo(pedidor, recomendador):
    """Ha vinculo conhecido entre quem pede (P) e quem indicou (R)?
    Por convite (qualquer direcao) ou por contato compartilhado (edge por HASH)."""
    if pedidor.get("invited_by") and pedidor["invited_by"] == recomendador["id"]:
        return True
    if recomendador.get("invited_by") and recomendador["invited_by"] == pedidor["id"]:
        return True

    hash_p = hash_de_membro(pedidor)
    hash_r = hash_de_membro(recomendador)
    if hash_p is None or hash_r is None:
        return False

    if supabase.table("edges").select("id").eq("member_id", pedidor["id"]).eq("contact_hash", hash_r).limit(1).execute().data:
        return True
    if supabase.table("edges").select("id").eq("member_id", recomendador["id"]).eq("contact_hash", hash_p).limit(1).execute().data:
        return True
    return False


def tratar_pedido_servico(pedidor, servico, bairro, voc):
    recs = (supabase.table("recommendations").select("*")
            .ilike("servico", servico).ilike("bairro", bairro).execute().data)

    com_nome = []   # VERDE: (prestador, nome de quem indicou)
    sem_nome = []   # AMARELO: prestador, sem revelar quem indicou

    for rec in recs:
        recomendador = buscar_membro_por_id(rec["member_id"])
        if recomendador is None or not recomendador.get("consent"):
            continue
        prestador = buscar_provider(rec["provider_id"])
        if prestador is None:
            continue
        if existe_vinculo(pedidor, recomendador):
            com_nome.append((prestador, recomendador.get("nome_perfil") or "alguem que voce conhece"))
        else:
            sem_nome.append(prestador)

    if com_nome:
        return texto_verde(servico, bairro, com_nome, voc)
    if sem_nome:
        return texto_amarelo(servico, bairro, sem_nome)
    return t.VERMELHO.format(servico=servico, bairro=bairro) + t.RODAPE


def texto_verde(servico, bairro, lista, voc):
    partes = [t.VERDE_CABECALHO.format(voc=voc, servico=servico.capitalize(), bairro=bairro)]
    for prestador, quem in lista:
        partes.append(t.VERDE_LINHA.format(nome=prestador["nome"], quem=quem, telefone=prestador["telefone"]))
    return "\n".join(partes) + t.VERDE_RODAPE + t.RODAPE


def texto_amarelo(servico, bairro, prestadores):
    partes = [t.AMARELO_CABECALHO.format(servico=servico, bairro=bairro, n=len(prestadores))]
    for prestador in prestadores:
        partes.append(t.AMARELO_LINHA.format(nome=prestador["nome"], telefone=prestador["telefone"]))
    return "\n".join(partes) + t.AMARELO_RODAPE + t.RODAPE


def texto_meus_dados(membro, voc):
    return t.MEUS_DADOS.format(
        voc=voc,
        nome=membro.get("nome_perfil") or "(sem nome)",
        consent="sim" if membro.get("consent") else "nao",
        n_contatos=contar("edges", membro["id"]),
        n_indicacoes=contar("recommendations", membro["id"]),
    )


# ===========================================================================
# RESPOSTA NO FORMATO DA TWILIO
# ===========================================================================

def resposta_whatsapp(texto):
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escape(texto)}</Message>
</Response>"""
    return Response(twiml, mimetype="application/xml")


# Conjuntos de palavras que reconhecemos como saudacao ou agradecimento.
SAUDACOES = {"oi", "ola", "olá", "oi!", "ola!", "opa", "oie", "eai", "e ai",
             "eaí", "hey", "bom dia", "boa tarde", "boa noite"}
AGRADECIMENTOS = {"obrigado", "obrigada", "obg", "obgd", "vlw", "valeu",
                  "valeu!", "brigado", "brigada", "muito obrigado",
                  "muito obrigada", "obrigado!", "obrigada!"}


# ===========================================================================
# A PORTA PRINCIPAL
# ===========================================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    texto_recebido = request.form.get("Body", "").strip()
    remetente = request.form.get("From", "")
    nome_perfil = request.form.get("ProfileName", "")
    wa_id = remetente.replace("whatsapp:", "")

    nome = primeiro_nome(nome_perfil)
    voc = vocativo(nome)

    print(f"Mensagem de {wa_id} ({nome_perfil}): {texto_recebido}")

    membro = buscar_membro(wa_id)

    # CASO 1 - pessoa nova
    if membro is None:
        invited_by = None
        codigo = extrair_codigo_convite(texto_recebido)
        if codigo:
            convidante = membro_por_codigo(codigo)
            if convidante:
                invited_by = convidante["id"]
        criar_membro(wa_id, nome_perfil, invited_by)
        return resposta_whatsapp(t.BOAS_VINDAS.format(voc=voc))

    # CASO 2 - ja consentiu
    if membro["consent"]:
        texto_minusculo = texto_recebido.lower()
        estado = membro.get("estado") or "normal"

        # 2a) No meio de uma recomendacao (Camada 6)?
        if estado == "recomendando":
            if texto_minusculo in ("cancelar", "sair", "parar"):
                definir_estado(wa_id, "normal")
                return resposta_whatsapp(t.REC_CANCELADA + "\n\n" + t.MENU.format(voc=voc))
            return resposta_whatsapp(tratar_recomendacao(membro, texto_recebido, voc))

        # 2a2) Confirmando a exclusao dos dados (Camada 8 / LGPD)?
        if estado == "confirmando_exclusao":
            if texto_minusculo in ("excluir", "apagar", "apagar tudo", "confirmar"):
                excluir_membro(membro)
                return resposta_whatsapp(t.ADEUS)
            if texto_minusculo in ("cancelar", "nao", "não", "voltar"):
                definir_estado(wa_id, "normal")
                return resposta_whatsapp(t.EXCLUSAO_CANCELADA + "\n\n" + t.MENU.format(voc=voc))
            return resposta_whatsapp(t.EXCLUSAO_CONFIRMAR)

        # 2b) Saudacao ou agradecimento? Respondemos de forma natural.
        if texto_minusculo in SAUDACOES:
            return resposta_whatsapp(t.SAUDACAO.format(voc=voc))
        if texto_minusculo in AGRADECIMENTOS:
            return resposta_whatsapp(t.AGRADECIMENTO.format(voc=voc))

        # 2c) Comando: recomendar.
        if texto_minusculo in ("recomendar", "indicar", "recomendar alguem",
                               "recomendar um", "quero recomendar"):
            definir_estado(wa_id, "recomendando")
            return resposta_whatsapp(t.PEDIR_RECOMENDACAO)

        # 2d) Comando: convidar.
        if texto_minusculo in ("convidar", "convite", "convidar alguem", "quero convidar"):
            codigo = obter_ou_criar_codigo(membro)
            numero_bot = request.form.get("To", "").replace("whatsapp:", "").replace("+", "")
            return resposta_whatsapp(t.CONVITE.format(link=montar_link_convite(numero_bot, codigo)) + t.RODAPE)

        # 2e) Comando: menu.
        if texto_minusculo in ("menu", "ajuda", "opcoes", "opções"):
            return resposta_whatsapp(t.MENU.format(voc=voc))

        # 2f) Comando: meus dados / sair (oferece exclusao - LGPD).
        if texto_minusculo in ("meus dados", "meus dados / sair", "sair", "dados",
                               "excluir", "apagar", "lgpd", "privacidade"):
            definir_estado(wa_id, "confirmando_exclusao")
            return resposta_whatsapp(texto_meus_dados(membro, voc))

        # 2g) Mandou numeros? Tratamos como contatos (Camada 4).
        numeros = extrair_numeros_de_texto(texto_recebido)
        if numeros:
            total, ja_membros = processar_contatos(membro, numeros)
            return resposta_whatsapp(texto_contatos_recebidos(total, ja_membros))

        # 2h) Uma frase? Tentamos entender como pedido de servico (Camada 5).
        dados = extrair_servico_bairro(texto_recebido)
        servico = dados.get("servico", "").strip()
        bairro = dados.get("bairro", "").strip()

        if servico and bairro:
            return resposta_whatsapp(tratar_pedido_servico(membro, servico, bairro, voc))
        if servico and not bairro:
            return resposta_whatsapp(t.PEDIR_BAIRRO.format(servico=servico))
        return resposta_whatsapp(t.AJUDA)

    # CASO 3 - ainda nao consentiu
    texto = texto_recebido.lower()
    if texto in ("sim", "sim, bora", "bora", "s"):
        registrar_consentimento(wa_id)
        return resposta_whatsapp(t.CONSENTIMENTO_OK.format(voc=voc) + t.PEDIR_CONTATOS)
    if "saber" in texto or "mais" in texto:
        return resposta_whatsapp(t.SABER_MAIS)
    return resposta_whatsapp(t.PRECISA_CONSENTIR)


@app.route("/", methods=["GET"])
def home():
    return "A Doroteia esta viva! 🎉"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
