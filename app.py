# app.py
# ---------------------------------------------------------------------------
# DOROTEIA - cerebro do bot. Recebe a mensagem do WhatsApp (via WhatsApp Cloud
# API da Meta) e delega a CONVERSA pra IA (cerebro.py), que responde em
# linguagem natural. As ACOES sensiveis (buscar, recomendar, contatos, convite,
# dados, exclusao, consentimento) sao executadas AQUI, de forma determinista,
# atraves das "ferramentas" que a IA pode chamar.
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

from privacidade import calcular_contact_hash, normalizar_e164
import cerebro
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


def enviar_mensagem_meta(to, texto, phone_number_id):
    """Envia uma mensagem de texto pela WhatsApp Cloud API."""
    if not (WHATSAPP_TOKEN and phone_number_id and to):
        print(f"[META] envio ignorado (token={'ok' if WHATSAPP_TOKEN else 'FALTA'}, "
              f"phone_id={'ok' if phone_number_id else 'FALTA'}, to={'ok' if to else 'FALTA'}).")
        return
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    corpo = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": texto, "preview_url": True},
    }).encode("utf-8")
    req = Request(url, data=corpo, method="POST")
    req.add_header("Authorization", f"Bearer {WHATSAPP_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=10) as resposta:
            resposta.read()
    except HTTPError as e:
        corpo_erro = ""
        try:
            corpo_erro = e.read().decode("utf-8", errors="ignore")[:300]
        except Exception:
            pass
        print(f"[META] HTTP {e.code} ao enviar: {corpo_erro}")
    except Exception as e:
        print(f"[META] falha ao enviar: {e!r}")


def resposta_whatsapp(texto):
    """Envia texto pela Cloud API usando o contexto da mensagem atual (g)."""
    print(f"[RESP] {texto[:80]!r}")
    enviar_mensagem_meta(g.get("to"), texto, g.get("phone_number_id"))


def _e164(bruto):
    """Normaliza um numero pro formato +55... (E.164)."""
    bruto = (bruto or "").strip()
    if not bruto.startswith("+"):
        bruto = "+" + re.sub(r"\D", "", bruto)
    return normalizar_e164(bruto) or bruto


def conteudo_da_mensagem(msg):
    """Extrai (texto, numeros_compartilhados) de uma mensagem da Cloud API."""
    tipo = msg.get("type")
    if tipo == "text":
        return (msg.get("text") or {}).get("body", "").strip(), []
    if tipo == "interactive":
        inter = msg.get("interactive") or {}
        sub = inter.get(inter.get("type", ""), {}) or {}
        return (sub.get("title") or "").strip(), []
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


def salvar_historico(wa_id, historico):
    try:
        supabase.table("members").update({"historico": historico}).eq("wa_id", wa_id).execute()
    except Exception:
        traceback.print_exc()


def contar(tabela, member_id):
    return len(supabase.table(tabela).select("id").eq("member_id", member_id).execute().data)


def registrar_busca(servico, bairro, cidade, resultado):
    try:
        row = {"servico": servico.lower(), "bairro": bairro, "resultado": resultado}
        if cidade:
            row["cidade"] = cidade
        supabase.table("searches").insert(row).execute()
    except Exception as erro:
        print(f"[METRICA] nao consegui registrar a busca: {erro}")


def excluir_membro(membro):
    supabase.table("members").delete().eq("id", membro["id"]).execute()


# ===========================================================================
# CONTATOS -> HASH -> GRAFO
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


# ===========================================================================
# CONVITE
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
# REGRAS DE VINCULO E BUSCA (verde / amarelo / vermelho)
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


def executar_busca(pedidor, servico, bairro, cidade):
    """Roda a busca real e devolve (com_nome, sem_nome).
    com_nome: [(prestador, nome_de_quem_indicou)]  -> rede direta (verde)
    sem_nome: [prestador]                          -> fora da rede (amarelo)"""
    query = (supabase.table("recommendations").select("*")
             .ilike("servico", servico).ilike("bairro", bairro))
    if cidade:
        query = query.ilike("cidade", cidade)
    recs = query.execute().data

    com_nome, sem_nome = [], []
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
    return com_nome, sem_nome


# ===========================================================================
# AS FERRAMENTAS (executadas quando a IA as chama). Devolvem TEXTO pra IA.
# ===========================================================================

def _resolver_ficha(valor, numeros):
    """Converte '[CONTATO_2]' no numero real (numeros[1]). Se vier um numero
    cru, normaliza. Devolve E.164 ou None."""
    m = re.search(r"CONTATO_(\d+)", valor or "")
    if m:
        i = int(m.group(1)) - 1
        if 0 <= i < len(numeros):
            return numeros[i]
        return None
    return normalizar_e164(valor or "") or None


def _ferr_buscar(membro, entrada):
    servico = (entrada.get("servico") or "").strip().lower()
    bairro  = (entrada.get("bairro")  or "").strip()
    cidade  = (entrada.get("cidade")  or "").strip()
    if not (servico and bairro and cidade):
        return "Faltou servico, bairro ou cidade. Pergunte o que faltar com naturalidade."

    com_nome, sem_nome = executar_busca(membro, servico, bairro, cidade)
    local = f"{bairro}, {cidade}"

    if com_nome:
        registrar_busca(servico, bairro, cidade, "verde")
        linhas = [f"- Nome: {p['nome']} | telefone (copie EXATO): {p['telefone']} | indicado por: {quem}"
                  for p, quem in com_nome]
        return ("RESULTADO=verde - indicacoes de pessoas da rede de confianca dela, em "
                f"{local}. Apresente com alegria, mantendo nome e telefone EXATOS e citando "
                "quem indicou:\n" + "\n".join(linhas))
    if sem_nome:
        registrar_busca(servico, bairro, cidade, "amarelo")
        linhas = [f"- Nome: {p['nome']} | telefone (copie EXATO): {p['telefone']}" for p in sem_nome]
        return ("RESULTADO=amarelo - ha indicacoes boas em "
                f"{local}, mas de FORA da rede dela (NAO revele quem indicou). Apresente "
                "mantendo o telefone EXATO e comente que, se ela trouxer mais gente de "
                "confianca, essas indicacoes passam a aparecer com nome:\n" + "\n".join(linhas))

    registrar_busca(servico, bairro, cidade, "vermelho")
    return (f"RESULTADO=vermelho - ninguem indicou {servico} em {local} ainda. Acolha a "
            "pessoa e incentive-a a recomendar alguem que conheca ou a convidar amigos pra "
            "fortalecer a rede.")


def _ferr_recomendar(membro, entrada, numeros):
    nome     = (entrada.get("nome")    or "").strip() or "Prestador"
    servico  = (entrada.get("servico") or "").strip().lower()
    bairro   = (entrada.get("bairro")  or "").strip()
    cidade   = (entrada.get("cidade")  or "").strip()
    estado   = (entrada.get("estado")  or "").strip()
    telefone = _resolver_ficha(entrada.get("telefone"), numeros)

    if not telefone:
        return "Nao recebi um telefone valido do prestador. Peca o numero (com DDD) ou o contato."
    if not (servico and bairro and cidade):
        return "Faltou servico, bairro ou cidade do prestador. Pergunte o que faltar."

    prestador = supabase.table("providers").insert({
        "nome": nome, "telefone": telefone, "servico": servico,
        "bairro": bairro, "cidade": cidade, "estado": estado,
    }).execute().data[0]
    supabase.table("recommendations").insert({
        "member_id": membro["id"], "provider_id": prestador["id"],
        "servico": servico, "bairro": bairro, "cidade": cidade,
    }).execute()

    return (f"Recomendacao de {nome} ({servico} em {bairro}, {cidade}) registrada com sucesso. "
            "Agradeca a pessoa com carinho e explique que a indicacao dela vai aparecer (com o "
            "nome dela) pra quem da rede dela precisar desse servico.")


def _ferr_adicionar_contatos(membro, numeros):
    if not numeros:
        return ("Nenhum contato veio nesta mensagem. Peca pra ela compartilhar pelo clipe 📎 "
                "do WhatsApp ou digitar os numeros com DDD.")
    total, ja_membros = processar_contatos(membro, numeros)
    restantes = total - ja_membros
    return (f"Adicionei {total} contato(s) a rede de confianca dela (guardados em codigo). "
            f"{ja_membros} ja usa(m) a Doroteia; {restantes} ainda nao. Agradeca e explique "
            "que, quando os outros entrarem, as indicacoes passam a aparecer entre eles.")


def _ferr_convidar(membro, numeros):
    if not numeros:
        return ("Nenhum contato veio nesta mensagem pra convidar. Peca pra compartilhar o "
                "contato pelo clipe 📎 ou digitar o numero com DDD.")
    numero_bot = g.get("display_phone_number") or ""
    for numero in numeros:
        registrar_convite_pendente(membro, numero)
    codigo = obter_ou_criar_codigo(membro)
    link_amigo = encurtar_link(montar_link_convite(numero_bot, codigo))
    mensagem = t.CONVITE_MENSAGEM_AMIGO.format(link=link_amigo)
    link_pronto = encurtar_link(montar_link_para_contato(numeros[0], mensagem))
    extra = ""
    if len(numeros) > 1:
        extra = (f" Tambem ja conectei a pessoa com os outros {len(numeros) - 1} contato(s); "
                 "quando entrarem, se reconhecem.")
    return (f"Convite pronto. Entregue este link EXATO pra ela abrir e enviar pro contato "
            f"(ja conectei os dois): {link_pronto}.{extra}")


def _ferr_link_generico(membro):
    numero_bot = g.get("display_phone_number") or ""
    codigo = obter_ou_criar_codigo(membro)
    link = encurtar_link(montar_link_convite(numero_bot, codigo))
    return (f"Link de convite generico (copie EXATO): {link}. Diga que ela pode mandar esse "
            "link pra quantas pessoas de confianca quiser; quem entrar por ele ja fica ligado a ela.")


def _ferr_ver_dados(membro):
    return (
        "Dados guardados sobre a pessoa (apresente de forma clara e tranquila):\n"
        f"- Nome: {membro.get('nome_perfil') or '(sem nome)'}\n"
        f"- Consentiu: {'sim' if membro.get('consent') else 'nao'}\n"
        f"- Contatos na rede dela (em codigo, nunca o numero): {contar('edges', membro['id'])}\n"
        f"- Indicacoes que ela fez: {contar('recommendations', membro['id'])}\n"
        "Reforce que os contatos ficam so em codigo embaralhado, e lembre que ela pode pedir "
        "pra apagar tudo quando quiser."
    )


def _ferr_excluir(membro, entrada):
    if entrada.get("confirmado") is True:
        excluir_membro(membro)
        return ("Todos os dados da pessoa foram apagados. Despeca-se com carinho e diga que, se "
                "um dia quiser voltar, e so mandar um oi.")
    return ("Ainda NAO foi confirmado. Pergunte com cuidado se ela tem certeza de que quer apagar "
            "TUDO (e irreversivel). So chame esta ferramenta de novo com confirmado=true depois do sim.")


def construir_executor(membro):
    """Devolve a funcao que a IA usa pra disparar acoes. Mantem o consentimento
    como porteiro: sem consent, so 'registrar_consentimento' funciona."""
    def executar(nome, entrada, numeros):
        if nome != "registrar_consentimento" and not membro.get("consent"):
            return ("A pessoa ainda nao consentiu. Nao execute acoes; peca o 'pode ser' dela primeiro.")
        if nome == "registrar_consentimento":
            registrar_consentimento(membro["wa_id"])
            membro["consent"] = True
            return ("Consentimento registrado. De as boas-vindas de verdade e convide a pessoa a "
                    "adicionar contatos de confianca (pelo clipe 📎 ou digitando), explicando que "
                    "isso faz as indicacoes aparecerem com nome.")
        if nome == "buscar_servico":
            return _ferr_buscar(membro, entrada)
        if nome == "salvar_recomendacao":
            return _ferr_recomendar(membro, entrada, numeros)
        if nome == "adicionar_contatos":
            return _ferr_adicionar_contatos(membro, numeros)
        if nome == "convidar_pessoa":
            return _ferr_convidar(membro, numeros)
        if nome == "gerar_link_convite":
            return _ferr_link_generico(membro)
        if nome == "ver_meus_dados":
            return _ferr_ver_dados(membro)
        if nome == "excluir_meus_dados":
            return _ferr_excluir(membro, entrada)
        return "Ferramenta desconhecida."
    return executar


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
    membro = buscar_membro(wa_id)

    # Pessoa nova: cria o cadastro (com vinculo de convite, se houver) e segue.
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
        membro = buscar_membro(wa_id)

    # A partir daqui, a IA conduz a conversa (e dispara as ferramentas acima).
    cerebro.conversar(
        membro,
        texto_recebido,
        numeros_compartilhados,
        executar_ferramenta=construir_executor(membro),
        enviar_texto=resposta_whatsapp,
        salvar_historico=lambda hist: salvar_historico(wa_id, hist),
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
