# app.py
# ---------------------------------------------------------------------------
# DOROTEIA - cerebro do bot. Recebe a mensagem do WhatsApp (via WhatsApp Cloud
# API da Meta), decide o que fazer e responde. As FALAS ficam todas em textos.py.
# ---------------------------------------------------------------------------

import hashlib
import hmac
import json
import os
import re
import secrets
import string
import traceback
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from flask import Flask, request, Response, g
from supabase import create_client
from werkzeug.middleware.proxy_fix import ProxyFix

from privacidade import calcular_contact_hash, extrair_numeros_de_texto, normalizar_e164
from nlu import extrair_servico_bairro, extrair_recomendacao

import textos as t


# ---------------------------------------------------------------------------
# CONEXAO COM O BANCO (Supabase)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# ---------------------------------------------------------------------------
# CONFIG DA WHATSAPP CLOUD API (Meta)
# ---------------------------------------------------------------------------
GRAPH_API = "https://graph.facebook.com/v21.0"
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "doroteia")
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET")


def assinatura_meta_valida():
    """Confere a assinatura (X-Hub-Signature-256) que a Meta poe em cada mensagem."""
    if not WHATSAPP_APP_SECRET:
        print("[SEGURANCA] WHATSAPP_APP_SECRET nao configurado - checagem desligada.")
        return True
    assinatura = request.headers.get("X-Hub-Signature-256", "")
    if not assinatura.startswith("sha256="):
        return False
    esperado = "sha256=" + hmac.new(
        WHATSAPP_APP_SECRET.encode(), request.get_data(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, assinatura)


def _post_meta(phone_number_id, corpo_json):
    """Faz o POST para a Graph API (texto ou interativo). Interno."""
    if not (WHATSAPP_TOKEN and phone_number_id):
        print("[META] envio ignorado: token ou phone_id ausente.")
        return
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    req = Request(url, data=json.dumps(corpo_json).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {WHATSAPP_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=10) as r:
            r.read()
    except HTTPError as e:
        corpo_erro = ""
        try:
            corpo_erro = e.read().decode("utf-8", errors="ignore")[:300]
        except Exception:
            pass
        print(f"[META] HTTP {e.code}: {corpo_erro}")
    except Exception as e:
        print(f"[META] falha ao enviar: {e!r}")


def enviar_mensagem_meta(to, texto, phone_number_id):
    """Envia mensagem de texto simples."""
    if not to:
        return
    _post_meta(phone_number_id, {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": texto, "preview_url": True},
    })


def _enviar_interativa(corpo_interativo):
    """Envia mensagem interativa (botoes ou lista) usando o contexto g."""
    to = g.get("to")
    phone_number_id = g.get("phone_number_id")
    if not to:
        return
    print(f"[RESP-BTN] {str(corpo_interativo)[:80]!r}")
    _post_meta(phone_number_id, {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": corpo_interativo,
    })


def resposta_whatsapp(texto):
    """Envia texto simples usando o contexto da mensagem atual (g)."""
    print(f"[RESP] {texto[:80]!r}")
    enviar_mensagem_meta(g.get("to"), texto, g.get("phone_number_id"))


def resposta_botoes(texto, botoes):
    """Envia mensagem com até 3 botões de resposta rápida.
    botoes: lista de (id, label) — id vira o 'texto' retornado quando clicado."""
    _enviar_interativa({
        "type": "button",
        "body": {"text": texto},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": bid, "title": label}}
                for bid, label in botoes[:3]
            ]
        },
    })


def resposta_lista(texto_corpo, texto_botao, secoes):
    """Envia mensagem com lista de opções (até 10 itens no total).
    secoes: [{"title": str, "rows": [{"id": str, "title": str, "description": str}]}]"""
    _enviar_interativa({
        "type": "list",
        "body": {"text": texto_corpo},
        "action": {
            "button": texto_botao,
            "sections": secoes,
        },
    })


def enviar_menu(voc):
    """Envia o menu principal como lista interativa."""
    resposta_lista(
        t.MENU.format(voc=voc),
        "Ver opcoes",
        [{
            "title": "O que voce precisa?",
            "rows": [
                {"id": "1", "title": "Pedir um servico",
                 "description": "ex.: encanador em Perdizes, SP"},
                {"id": "2", "title": "Recomendar alguem",
                 "description": "indicar um bom prestador"},
                {"id": "3", "title": "Convidar alguem",
                 "description": "trazer um amigo para a Doroteia"},
                {"id": "4", "title": "Meus dados / sair",
                 "description": "ver ou apagar seus dados"},
            ]
        }]
    )


def _e164(bruto):
    """Normaliza um numero pro formato +55... (E.164)."""
    bruto = (bruto or "").strip()
    if not bruto.startswith("+"):
        bruto = "+" + re.sub(r"\D", "", bruto)
    return normalizar_e164(bruto) or bruto


def conteudo_da_mensagem(msg):
    """Extrai (texto, numeros_compartilhados) de uma mensagem da Cloud API.
    Para botoes/lista clicados, retorna o ID do botao (que mapeamos a comandos internos)."""
    tipo = msg.get("type")
    if tipo == "text":
        return (msg.get("text") or {}).get("body", "").strip(), []
    if tipo == "interactive":
        inter = msg.get("interactive") or {}
        sub_tipo = inter.get("type", "")
        sub = inter.get(sub_tipo) or {}
        # Retorna o id (nome interno do botao), com title como fallback
        return (sub.get("id") or sub.get("title") or "").strip(), []
    if tipo == "button":
        return ((msg.get("button") or {}).get("text") or "").strip(), []
    if tipo == "contacts":
        numeros = []
        for c in msg.get("contacts", []):
            for tel in c.get("phones", []):
                numero = _e164(tel.get("wa_id") or tel.get("phone") or "")
                if numero and numero not in numeros:
                    numeros.append(numero)
        return "", numeros
    return "", []


# ===========================================================================
# AJUDINHAS DE PERSONALIZACAO
# ===========================================================================

def primeiro_nome(nome_perfil):
    if nome_perfil and nome_perfil.strip():
        return nome_perfil.strip().split()[0]
    return ""


def vocativo(nome):
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
        "invited_by": invited_by,
    }).execute()


def registrar_consentimento(wa_id):
    agora = datetime.now(timezone.utc).isoformat()
    supabase.table("members").update({
        "consent": True,
        "consent_at": agora,
    }).eq("wa_id", wa_id).execute()


def definir_estado(wa_id, estado):
    supabase.table("members").update({"estado": estado}).eq("wa_id", wa_id).execute()


def contar(tabela, member_id):
    return len(supabase.table(tabela).select("id").eq("member_id", member_id).execute().data)


def registrar_busca(servico, bairro, cidade, resultado):
    """Metrica (sem dado pessoal): anota o que foi procurado e a cor da resposta."""
    try:
        row = {
            "servico": servico.lower(),
            "bairro": bairro,
            "resultado": resultado,
        }
        if cidade:
            row["cidade"] = cidade
        supabase.table("searches").insert(row).execute()
    except Exception as erro:
        print(f"[METRICA] nao consegui registrar a busca: {erro}")


def excluir_membro(membro):
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
    nome     = (dados.get("nome")     or "").strip() or "Prestador"
    servico  = (dados.get("servico")  or "").strip()
    bairro   = (dados.get("bairro")   or "").strip()
    cidade   = (dados.get("cidade")   or "").strip()
    estado   = (dados.get("estado")   or "").strip()
    telefone = normalizar_e164((dados.get("telefone") or "").strip())

    if not telefone or not servico or not bairro:
        return t.REC_INCOMPLETA

    prestador = supabase.table("providers").insert({
        "nome":     nome,
        "telefone": telefone,
        "servico":  servico.lower(),
        "bairro":   bairro,
        "cidade":   cidade,
        "estado":   estado,
    }).execute().data[0]

    supabase.table("recommendations").insert({
        "member_id":   membro["id"],
        "provider_id": prestador["id"],
        "servico":     servico.lower(),
        "bairro":      bairro,
        "cidade":      cidade,
    }).execute()

    definir_estado(membro["wa_id"], "normal")
    bairro_display = f"{bairro}, {cidade}" if (bairro and cidade) else bairro
    return t.REC_OK.format(nome=nome, servico=servico, bairro=bairro_display, voc=voc) + t.RODAPE


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


def registrar_convite_pendente(membro, numero_e164):
    """Guarda (em HASH) que este membro convidou aquele numero."""
    codigo = calcular_contact_hash(numero_e164)
    existe = (supabase.table("pending_invites").select("id")
              .eq("inviter_id", membro["id"]).eq("contact_hash", codigo).limit(1).execute().data)
    if not existe:
        supabase.table("pending_invites").insert({
            "inviter_id": membro["id"],
            "contact_hash": codigo,
        }).execute()


def montar_link_para_contato(numero_e164, mensagem):
    numero = numero_e164.replace("+", "")
    return f"https://wa.me/{numero}?text={quote(mensagem)}"


def gerar_codigo_curto(tamanho=6):
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def encurtar_link(url):
    """Encurtador proprio: /c/<codigo> redireciona pro link longo."""
    try:
        codigo = gerar_codigo_curto()
        supabase.table("short_links").insert({"code": codigo, "url": url}).execute()
        base = request.url_root.rstrip("/")
        return f"{base}/c/{codigo}"
    except Exception:
        traceback.print_exc()
        return url


def aplicar_convite_pendente(wa_id):
    numero = normalizar_e164(wa_id)
    if not numero:
        return None
    codigo = calcular_contact_hash(numero)
    achado = (supabase.table("pending_invites").select("id, inviter_id")
              .eq("contact_hash", codigo).limit(1).execute().data)
    if not achado:
        return None
    supabase.table("pending_invites").delete().eq("id", achado[0]["id"]).execute()
    return achado[0]["inviter_id"]


# ===========================================================================
# CAMADA 5/6 - REGRAS VERDE / AMARELO / VERMELHO
# ===========================================================================

def hash_de_membro(membro):
    numero = normalizar_e164(membro["wa_id"])
    return calcular_contact_hash(numero) if numero else None


def existe_vinculo(pedidor, recomendador):
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


def tratar_pedido_servico(pedidor, servico, bairro, cidade, voc):
    bairro_display = f"{bairro}, {cidade}" if (bairro and cidade) else bairro

    query = (supabase.table("recommendations").select("*")
             .ilike("servico", servico)
             .ilike("bairro", bairro))
    if cidade:
        query = query.ilike("cidade", cidade)
    recs = query.execute().data

    com_nome = []
    sem_nome = []

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
        registrar_busca(servico, bairro, cidade, "verde")
        return texto_verde(servico, bairro_display, com_nome, voc)
    if sem_nome:
        registrar_busca(servico, bairro, cidade, "amarelo")
        return texto_amarelo(servico, bairro_display, sem_nome)
    registrar_busca(servico, bairro, cidade, "vermelho")
    return t.VERMELHO.format(servico=servico, bairro=bairro_display) + t.RODAPE


def texto_verde(servico, bairro_display, lista, voc):
    partes = [t.VERDE_CABECALHO.format(voc=voc, servico=servico.capitalize(), bairro=bairro_display)]
    for prestador, quem in lista:
        partes.append(t.VERDE_LINHA.format(nome=prestador["nome"], quem=quem, telefone=prestador["telefone"]))
    return "\n".join(partes) + t.VERDE_RODAPE + t.RODAPE


def texto_amarelo(servico, bairro_display, prestadores):
    partes = [t.AMARELO_CABECALHO.format(servico=servico, bairro=bairro_display, n=len(prestadores))]
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


SAUDACOES = {"oi", "ola", "olá", "oi!", "ola!", "opa", "oie", "eai", "e ai",
             "eaí", "hey", "bom dia", "boa tarde", "boa noite"}
AGRADECIMENTOS = {"obrigado", "obrigada", "obg", "obgd", "vlw", "valeu",
                  "valeu!", "brigado", "brigada", "muito obrigado",
                  "muito obrigada", "obrigado!", "obrigada!"}


# ===========================================================================
# A PORTA PRINCIPAL (WhatsApp Cloud API)
# ===========================================================================

@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    if (request.args.get("hub.mode") == "subscribe"
            and request.args.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN):
        return Response(request.args.get("hub.challenge", ""), mimetype="text/plain")
    return Response("Token de verificacao invalido", status=403)


@app.route("/webhook", methods=["POST"])
def webhook():
    if not assinatura_meta_valida():
        print("[SEGURANCA] mensagem rejeitada: assinatura invalida.")
        return Response("Assinatura invalida", status=403)
    dados = request.get_json(silent=True) or {}
    processar_eventos(dados)
    return Response("OK", status=200)


def processar_eventos(dados):
    for entry in dados.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            display = re.sub(r"\D", "", metadata.get("display_phone_number", ""))

            nomes = {}
            for c in value.get("contacts", []):
                nomes[c.get("wa_id")] = (c.get("profile") or {}).get("name", "")

            for msg in value.get("messages", []):
                origem = msg.get("from", "")
                nome_perfil = nomes.get(origem, "")
                texto, numeros = conteudo_da_mensagem(msg)

                g.to = origem
                g.phone_number_id = phone_number_id
                g.display_phone_number = display

                wa_id = _e164(origem)
                print(f"Mensagem de {wa_id} ({nome_perfil}): {texto!r}")
                try:
                    _processar_mensagem(wa_id, texto, nome_perfil, numeros)
                except Exception:
                    traceback.print_exc()
                    resposta_whatsapp(t.ERRO_GENERICO)


def _processar_mensagem(wa_id, texto_recebido, nome_perfil, numeros_compartilhados):
    nome = primeiro_nome(nome_perfil)
    voc = vocativo(nome)

    membro = buscar_membro(wa_id)

    # CASO 1 - pessoa nova
    if membro is None:
        invited_by = None
        codigo = extrair_codigo_convite(texto_recebido)
        if codigo:
            convidante = membro_por_codigo(codigo)
            if convidante:
                invited_by = convidante["id"]
        if invited_by is None:
            invited_by = aplicar_convite_pendente(wa_id)
        criar_membro(wa_id, nome_perfil, invited_by)
        return resposta_botoes(
            t.BOAS_VINDAS.format(voc=voc),
            [("sim", "Pode ser! ✅"), ("saber_mais", "Saber mais")]
        )

    # CASO 2 - ja consentiu
    if membro["consent"]:
        texto_minusculo = texto_recebido.lower()
        estado = membro.get("estado") or "normal"
        print(f"[ESTADO] {wa_id} estado={estado} texto={texto_recebido!r}")

        # 2a) No meio de uma recomendacao?
        if estado == "recomendando":
            if texto_minusculo in ("cancelar", "sair", "parar"):
                definir_estado(wa_id, "normal")
                resposta_whatsapp(t.REC_CANCELADA)
                return enviar_menu(voc)
            return resposta_whatsapp(tratar_recomendacao(membro, texto_recebido, voc))

        # 2a2) Confirmando exclusao dos dados?
        if estado == "confirmando_exclusao":
            if texto_minusculo in ("excluir", "apagar", "apagar tudo", "confirmar"):
                excluir_membro(membro)
                return resposta_whatsapp(t.ADEUS)
            if texto_minusculo in ("cancelar", "nao", "não", "voltar"):
                definir_estado(wa_id, "normal")
                resposta_whatsapp(t.EXCLUSAO_CANCELADA)
                return enviar_menu(voc)
            return resposta_botoes(
                t.EXCLUSAO_CONFIRMAR,
                [("excluir", "Apagar tudo ❌"), ("cancelar", "Cancelar")]
            )

        # 2a3) Convidando pelo numero?
        if estado == "convidando":
            if texto_minusculo in ("cancelar", "sair", "parar"):
                definir_estado(wa_id, "normal")
                return enviar_menu(voc)
            numero_bot = g.get("display_phone_number") or ""
            if texto_minusculo in ("link", "meu link", "linque"):
                definir_estado(wa_id, "normal")
                codigo = obter_ou_criar_codigo(membro)
                link = encurtar_link(montar_link_convite(numero_bot, codigo))
                return resposta_whatsapp(t.CONVITE.format(link=link) + t.RODAPE)
            numeros = numeros_compartilhados or extrair_numeros_de_texto(texto_recebido)
            if not numeros:
                return resposta_botoes(
                    t.CONVIDAR_NUMERO_INVALIDO,
                    [("link", "Meu link geral"), ("cancelar", "Cancelar")]
                )
            for numero in numeros:
                registrar_convite_pendente(membro, numero)
            numero_amigo = numeros[0]
            codigo = obter_ou_criar_codigo(membro)
            link_amigo = encurtar_link(montar_link_convite(numero_bot, codigo))
            mensagem = t.CONVITE_MENSAGEM_AMIGO.format(link=link_amigo)
            link_curto = encurtar_link(montar_link_para_contato(numero_amigo, mensagem))
            definir_estado(wa_id, "normal")
            resposta = t.CONVITE_PRONTO.format(link=link_curto)
            if len(numeros) > 1:
                resposta += t.CONVITE_EXTRAS.format(qtd=len(numeros) - 1)
            return resposta_whatsapp(resposta)

        # 2b) Saudacao ou agradecimento?
        if texto_minusculo in SAUDACOES:
            return resposta_whatsapp(t.SAUDACAO.format(voc=voc))
        if texto_minusculo in AGRADECIMENTOS:
            return resposta_whatsapp(t.AGRADECIMENTO.format(voc=voc))

        # 2b2) Atalhos do menu: numeros 1-4 (texto digitado) ou IDs de botao da lista
        atalhos_menu = {"1": "servico", "2": "recomendar", "3": "convidar", "4": "meus dados"}
        if texto_minusculo in atalhos_menu:
            escolha = atalhos_menu[texto_minusculo]
            if escolha == "servico":
                return resposta_whatsapp(t.PEDIR_SERVICO.format(voc=voc))
            texto_minusculo = escolha

        # 2c) Recomendar
        if texto_minusculo in ("recomendar", "indicar", "recomendar alguem",
                               "recomendar um", "quero recomendar"):
            definir_estado(wa_id, "recomendando")
            return resposta_whatsapp(t.PEDIR_RECOMENDACAO)

        # 2d) Convidar
        if texto_minusculo in ("convidar", "convite", "convidar alguem", "quero convidar"):
            definir_estado(wa_id, "convidando")
            return resposta_botoes(
                t.CONVIDAR_PEDIR_NUMERO,
                [("link", "Meu link geral"), ("cancelar", "Cancelar")]
            )

        # 2e) Menu
        if texto_minusculo in ("menu", "ajuda", "opcoes", "opções"):
            return enviar_menu(voc)

        # 2f) Meus dados / sair
        if texto_minusculo in ("meus dados", "meus dados / sair", "sair", "dados",
                               "excluir", "apagar", "lgpd", "privacidade"):
            definir_estado(wa_id, "confirmando_exclusao")
            return resposta_botoes(
                texto_meus_dados(membro, voc),
                [("excluir", "Apagar tudo ❌"), ("cancelar", "Voltar")]
            )

        # 2g) Contatos compartilhados ou digitados
        numeros = extrair_numeros_de_texto(texto_recebido)
        for numero in numeros_compartilhados:
            if numero not in numeros:
                numeros.append(numero)
        if numeros:
            total, ja_membros = processar_contatos(membro, numeros)
            return resposta_whatsapp(texto_contatos_recebidos(total, ja_membros))

        # 2h) Pedido de servico (NLU)
        dados = extrair_servico_bairro(texto_recebido)
        servico = dados.get("servico", "").strip()
        bairro  = dados.get("bairro",  "").strip()
        cidade  = dados.get("cidade",  "").strip()

        if servico and bairro:
            return resposta_whatsapp(tratar_pedido_servico(membro, servico, bairro, cidade, voc))
        if servico and not bairro:
            return resposta_whatsapp(t.PEDIR_BAIRRO.format(servico=servico))
        return enviar_menu(voc)

    # CASO 3 - ainda nao consentiu
    texto = texto_recebido.lower()
    if texto in ("sim", "sim, bora", "bora", "s"):
        registrar_consentimento(wa_id)
        return resposta_whatsapp(t.CONSENTIMENTO_OK.format(voc=voc) + t.PEDIR_CONTATOS)
    if "saber" in texto or "mais" in texto:
        return resposta_botoes(t.SABER_MAIS, [("sim", "Pode ser! ✅")])
    return resposta_botoes(
        t.PRECISA_CONSENTIR,
        [("sim", "Pode ser! ✅"), ("saber_mais", "Saber mais")]
    )


@app.route("/c/<codigo>", methods=["GET"])
def redirecionar_link(codigo):
    try:
        achado = (supabase.table("short_links").select("url")
                  .eq("code", codigo).limit(1).execute().data)
        if achado:
            return Response(status=302, headers={"Location": achado[0]["url"]})
    except Exception:
        traceback.print_exc()
    return Response("Link nao encontrado.", status=404)


@app.route("/", methods=["GET"])
def home():
    return "A Doroteia esta viva! 🎉"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
