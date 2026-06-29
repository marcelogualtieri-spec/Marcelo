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
import time
import threading
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from flask import Flask, request, Response, g
from supabase import create_client
from werkzeug.middleware.proxy_fix import ProxyFix

from privacidade import calcular_contact_hash, normalizar_e164
import cerebro
import nlu
import textos as t
import termos


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

# URL publica do servico, usada pra montar os links curtos /c/<code>. Vem de env
# (configuravel se um dia mudar o dominio); cai num padrao conhecido; e so em
# ultimo caso usa a URL da requisicao (que pode vir errada atras de proxy).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://doroteia-ia.onrender.com").rstrip("/")

# Links dos Termos de Uso (cliente e profissional).
LINK_TERMOS = os.environ.get("TERMOS_URL") or (PUBLIC_BASE_URL + "/termos")
LINK_TERMOS_PROF = os.environ.get("TERMOS_PROF_URL") or (PUBLIC_BASE_URL + "/termos/profissional")

# Cron de follow-up: chave de protecao do endpoint e id do numero do bot.
# CRON_SECRET: string aleatoria configurada no Render + GitHub Secrets.
# WHATSAPP_PHONE_NUMBER_ID: visivel nos eventos do webhook (metadata.phone_number_id).
CRON_SECRET            = os.environ.get("CRON_SECRET", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")

# Numero (so digitos, com DDI) que recebe os pedidos de ajuda/suporte. Opcional:
# sem ele, os pedidos so ficam registrados na tabela 'suporte' para a equipe ver.
SUPORTE_WA_ID = re.sub(r"\D", "", os.environ.get("SUPORTE_WA_ID", ""))



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


def marcar_lido_digitando(message_id, phone_number_id):
    """Marca a mensagem como LIDA e mostra 'digitando...' pra pessoa nao achar que o
    chat travou. O indicador some sozinho em ~25s ou quando a resposta e enviada."""
    if not (WHATSAPP_TOKEN and phone_number_id and message_id):
        return
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    corpo = json.dumps({
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }).encode("utf-8")
    req = Request(url, data=corpo, method="POST")
    req.add_header("Authorization", f"Bearer {WHATSAPP_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        print(f"[META] indicador de digitando falhou: {e!r}")


def _post_interativa(corpo_interativo, to=None, phone_number_id=None):
    """Envia mensagem interativa (botoes) pela Cloud API.
    Sem `to`/`phone_number_id`, usa o contexto da conversa atual (g). Com eles,
    envia para outra pessoa (ex.: avisar quem indicou)."""
    to = to or g.get("to")
    phone_number_id = phone_number_id or g.get("phone_number_id")
    if not (WHATSAPP_TOKEN and phone_number_id and to):
        return
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    corpo = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": corpo_interativo,
    }).encode("utf-8")
    req = Request(url, data=corpo, method="POST")
    req.add_header("Authorization", f"Bearer {WHATSAPP_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=10) as r:
            r.read()
    except HTTPError as e:
        print(f"[META] HTTP {e.code} ao enviar interativa")
    except Exception as e:
        print(f"[META] falha ao enviar interativa: {e!r}")


def enviar_botoes_meta(texto, botoes, to=None, phone_number_id=None):
    """Envia mensagem com até 3 botões clicáveis via Cloud API.
    botoes: [{"id": str, "label": str}]"""
    print(f"[RESP-BTN] {texto[:60]!r}")
    _post_interativa({
        "type": "button",
        "body": {"text": texto},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["label"][:20]}}
                for b in botoes[:3]
            ]
        },
    }, to=to, phone_number_id=phone_number_id)


def _e164(bruto):
    """Normaliza um numero pro formato +55... (E.164).

    Aceita os varios jeitos que o telefone chega de um card de contato:
      - "(11) 99999-8888" / "11999998888"  -> nacional, sem codigo do pais (BR)
      - "+55 11 99999-8888"                -> ja internacional
      - "5511999998888" (wa_id da Meta)    -> so digitos, COM codigo do pais, sem '+'
    Devolve E.164 valido, ou "" quando nao da pra validar (melhor descartar do
    que cadastrar um numero errado)."""
    bruto = (bruto or "").strip()
    if not bruto:
        return ""

    # 1) Tenta como veio. A regiao BR resolve o formato nacional "(11) 99999-8888"
    #    e tambem o internacional "+55 ...".
    e164 = normalizar_e164(bruto)
    if e164:
        return e164

    # 2) wa_id costuma vir so com digitos e ja COM o codigo do pais (sem '+').
    so_digitos = re.sub(r"\D", "", bruto)
    if so_digitos:
        e164 = normalizar_e164("+" + so_digitos)
        if e164:
            return e164

    return ""


def _button_id(msg):
    """ID do botao/opcao clicada numa mensagem interativa (ou '' se nao houver)."""
    if msg.get("type") == "interactive":
        inter = msg.get("interactive") or {}
        sub = inter.get(inter.get("type", ""), {}) or {}
        return (sub.get("id") or "").strip()
    return ""


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
        # Retorna lista de (e164, nome) — o nome do card vai pra IA, o numero fica como ficha.
        # Se o numero nao chegar valido, inclui ("", nome) pra IA saber que o card veio
        # e poder pedir o telefone pelo nome, em vez de ignorar o contato.
        contatos = []
        vistos = set()
        for c in msg.get("contacts", []):
            nome_card = (c.get("name") or {}).get("formatted_name", "").strip()
            teve_numero = False
            for tel in c.get("phones", []):
                numero = _e164(tel.get("wa_id") or tel.get("phone") or "")
                if numero and numero not in vistos:
                    contatos.append((numero, nome_card))
                    vistos.add(numero)
                    teve_numero = True
            if not teve_numero and nome_card:
                contatos.append(("", nome_card))
        return "", contatos
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


def registrar_busca(servico, bairro, cidade, resultado, member_id=None):
    try:
        row = {"servico": servico.lower(), "bairro": bairro, "resultado": resultado}
        if cidade:
            row["cidade"] = cidade
        if member_id:
            row["member_id"] = member_id
        supabase.table("searches").insert(row).execute()
    except Exception as erro:
        print(f"[METRICA] nao consegui registrar a busca: {erro}")


def excluir_membro(membro):
    supabase.table("members").delete().eq("id", membro["id"]).execute()


# --- Estado de fluxo (multi-passo, deterministico) --------------------------
# Guardado como JSON na coluna members.estado. Ex.: o cliente indicando um
# profissional passa por contato -> detalhes -> validacao antes de gerar o link.
def _fluxo_get(membro):
    bruto = membro.get("estado")
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except Exception:
        return {}


def _fluxo_set(membro, dados):
    membro["estado"] = json.dumps(dados, ensure_ascii=False)
    try:
        supabase.table("members").update({"estado": membro["estado"]}).eq("id", membro["id"]).execute()
    except Exception:
        traceback.print_exc()


def _fluxo_limpar(membro):
    membro["estado"] = None
    try:
        supabase.table("members").update({"estado": None}).eq("id", membro["id"]).execute()
    except Exception:
        traceback.print_exc()


# ===========================================================================
# AVALIACAO DAS INDICACOES (qualifica depois do uso -> relevancia na rede)
# ===========================================================================

# So puxamos o follow-up ("usou? como foi?") se a indicacao tiver pelo menos
# este tempo de vida - pra nao perguntar no mesmo instante em que mostramos.
MIN_HORAS_PARA_AVALIAR = 1


def registrar_indicacao_recebida(member_id, provider, servico, bairro, cidade):
    """Marca que este prestador foi MOSTRADO a esta pessoa (base do follow-up).
    Nao duplica nem reabre uma indicacao que ja foi avaliada."""
    try:
        existe = (supabase.table("indicacoes_recebidas").select("id,status")
                  .eq("member_id", member_id).eq("provider_id", provider["id"])
                  .limit(1).execute().data)
        if existe:
            # Ja existe: se ja foi avaliada, deixa quieto. Senao, refresca pra pendente.
            if existe[0]["status"] != "avaliada":
                supabase.table("indicacoes_recebidas").update({
                    "status": "pendente",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", existe[0]["id"]).execute()
            return
        supabase.table("indicacoes_recebidas").insert({
            "member_id": member_id, "provider_id": provider["id"],
            "servico": servico, "bairro": bairro, "cidade": cidade,
            "status": "pendente",
        }).execute()
    except Exception as erro:
        print(f"[AVALIACAO] nao consegui registrar indicacao recebida: {erro}")


def _parse_ts(valor):
    """Le um timestamp ISO do Supabase como datetime aware (UTC)."""
    try:
        return datetime.fromisoformat((valor or "").replace("Z", "+00:00"))
    except Exception:
        return None


def buscar_avaliacao_pendente(membro):
    """Devolve a indicacao pendente mais recente (com idade minima) pra Dorote.ia
    perguntar 'usou? como foi?'. Retorna dict {nome, servico, bairro, cidade} ou None."""
    try:
        pend = (supabase.table("indicacoes_recebidas").select("*")
                .eq("member_id", membro["id"]).eq("status", "pendente")
                .order("created_at", desc=True).limit(5).execute().data)
    except Exception as erro:
        print(f"[AVALIACAO] nao consegui buscar pendentes: {erro}")
        return None

    agora = datetime.now(timezone.utc)
    for ind in pend:
        criada = _parse_ts(ind.get("created_at"))
        if criada is None:
            continue
        horas = (agora - criada).total_seconds() / 3600
        if horas < MIN_HORAS_PARA_AVALIAR:
            continue
        prestador = buscar_provider(ind["provider_id"])
        if prestador is None:
            continue
        return {
            "nome": prestador["nome"],
            "servico": ind.get("servico") or prestador.get("servico"),
            "bairro": ind.get("bairro") or prestador.get("bairro"),
            "cidade": ind.get("cidade") or "",
        }
    return None


def _recalcular_nota_provider(provider_id):
    """Recalcula media e quantidade de avaliacoes de um prestador e grava."""
    try:
        notas = [a["nota"] for a in (supabase.table("avaliacoes").select("nota")
                 .eq("provider_id", provider_id).execute().data)]
        qtd = len(notas)
        media = round(sum(notas) / qtd, 2) if qtd else 0
        supabase.table("providers").update({
            "nota_media": media, "qtd_avaliacoes": qtd,
        }).eq("id", provider_id).execute()
    except Exception as erro:
        print(f"[AVALIACAO] nao consegui recalcular nota: {erro}")


def _relevancia(provider):
    """Chave de ordenacao: bem avaliados primeiro; sem avaliacao fica neutro (3.0)."""
    qtd = provider.get("qtd_avaliacoes") or 0
    if qtd > 0:
        return (float(provider.get("nota_media") or 0), qtd)
    return (3.0, 0)


# ===========================================================================
# CONTATOS -> HASH -> GRAFO
# ===========================================================================

def processar_contatos(membro, numeros_e164):
    """Salva os contatos como hashes no grafo e classifica em membros vs nao-membros.

    Retorna (total, membros_na_rede, nao_membros) onde:
    - membros_na_rede: lista de nomes de perfil dos contatos ja na Dorote.ia
    - nao_membros: lista de (indice_original, e164) dos que ainda nao sao membros
      (indice_original preserva a ficha [CONTATO_n] que a IA conhece)
    """
    member_id = membro["id"]
    minha_e164 = normalizar_e164(membro.get("wa_id") or "")

    existentes = supabase.table("edges").select("contact_hash").eq("member_id", member_id).execute()
    hashes_existentes = {linha["contact_hash"] for linha in existentes.data}

    registros_novos = []
    membros_na_rede = []
    nao_membros = []

    for i, numero in enumerate(numeros_e164):
        if minha_e164 and numero == minha_e164:
            continue
        outro = buscar_membro(numero)
        if outro is not None:
            nome = (outro.get("nome_perfil") or "").strip()
            membros_na_rede.append(nome or "alguem")
        else:
            nao_membros.append((i, numero))
        codigo = calcular_contact_hash(numero)
        if codigo not in hashes_existentes:
            registros_novos.append({"member_id": member_id, "contact_hash": codigo})
            hashes_existentes.add(codigo)

    if registros_novos:
        supabase.table("edges").insert(registros_novos).execute()

    return len(numeros_e164), membros_na_rede, nao_membros


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


def montar_link_convite(numero_bot, codigo=None):
    """Link wa.me que abre a conversa com a Dorote.ia ja com uma saudacao escrita.

    O codigo do convite e detalhe TECNICO e nao precisa aparecer pra quem recebe.
    - Convite a um contato especifico: a conexao ja acontece pelo numero (convite
      pendente registrado), entao a mensagem fica LIMPA, sem codigo (codigo=None).
    - Link generico de divulgacao: nao ha numero pra casar, entao ai sim o codigo
      vai junto (e o unico jeito de saber quem convidou)."""
    mensagem = "Oi! Quero entrar na Dorote.ia 🙂"
    if codigo:
        mensagem += f" (convite: {codigo})"
    return f"https://wa.me/{numero_bot}?text={quote(mensagem)}"


def extrair_codigo_convite(texto):
    achado = re.search(r"convite:\s*([A-Za-z0-9]{6})", texto)
    return achado.group(1).upper() if achado else None


def membro_por_codigo(codigo):
    resposta = supabase.table("members").select("id").eq("invite_code", codigo).execute()
    return resposta.data[0] if resposta.data else None


def nome_do_convidante(invited_by_id):
    """Nome de perfil de quem convidou — pra Dorote.ia dar boas-vindas calorosas
    citando a pessoa e deixar a conexao transparente."""
    if not invited_by_id:
        return ""
    quem = buscar_membro_por_id(invited_by_id)
    return (quem.get("nome_perfil") or "").strip() if quem else ""


def limpar_texto_convite(texto):
    """Tira o trecho tecnico '(convite: ABC123)' do primeiro contato, pra IA nao
    repetir o codigo na conversa. O resto da mensagem fica intacto."""
    if not texto:
        return texto
    return re.sub(r"\(?\s*convite:\s*[A-Za-z0-9]{6}\s*\)?", "", texto).strip()


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
    # So minusculas + digitos: evita qualquer problema de maiusc/minusc na URL.
    alfabeto = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def _base_publica():
    """Base pra montar os links curtos. Prioriza a env/padrao conhecido; so usa
    a URL da requisicao se nao houver outra (atras de proxy ela pode vir errada)."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    try:
        return request.url_root.rstrip("/")
    except Exception:
        return ""


def encurtar_link(url):
    """Gera um link curto /c/<code> que redireciona pra `url`. Se a gravacao falhar
    ou nao tiver base valida, devolve a propria `url` (que ja funciona) — nunca
    um link quebrado que daria 404."""
    try:
        codigo = gerar_codigo_curto()
        res = supabase.table("short_links").insert({"code": codigo, "url": url}).execute()
        if not getattr(res, "data", None):
            print(f"[ENCURTAR] insert nao retornou linha (code={codigo}); usando url crua.")
            return url
        base = _base_publica()
        if not base:
            return url
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

    com_nome: [(prestador, [nomes_de_quem_indicou])]  -> rede direta (verde)
              Um mesmo prestador pode ter sido indicado por varias pessoas da
              rede; todos os nomes sao agregados pra mostrar prova social real.
    sem_nome: [prestador]                             -> fora da rede (amarelo)
    """
    query = supabase.table("recommendations").select("*").ilike("servico", servico)
    if bairro:
        query = query.ilike("bairro", bairro)
    if cidade:
        query = query.ilike("cidade", cidade)
    recs = query.execute().data

    por_provider_rede = {}  # pid -> {"prestador", "quem_indicou": [nomes]}
    por_provider_fora = {}  # pid -> prestador (fora da rede, sem nome)

    for rec in recs:
        recomendador = buscar_membro_por_id(rec["member_id"])
        if recomendador is None or not recomendador.get("consent"):
            continue
        prestador = buscar_provider(rec["provider_id"])
        if prestador is None:
            continue
        # Regra de ouro: so aparece quem ESTA ATIVO — ou seja, quem entrou,
        # consentiu e completou o perfil. Quem foi apenas indicado ('convidado'),
        # esta em onboarding, pausou ou saiu nao aparece nas buscas.
        if prestador.get("status") != "ativo":
            continue

        pid = prestador["id"]
        if existe_vinculo(pedidor, recomendador):
            nome_rec = (recomendador.get("nome_perfil") or "").strip() or "alguem que voce conhece"
            if pid not in por_provider_rede:
                por_provider_rede[pid] = {"prestador": prestador, "quem_indicou": []}
            if nome_rec not in por_provider_rede[pid]["quem_indicou"]:
                por_provider_rede[pid]["quem_indicou"].append(nome_rec)
        else:
            if pid not in por_provider_fora:
                por_provider_fora[pid] = prestador

    # Prestadores da rede nao entram no amarelo, mesmo com indicacoes externas.
    com_nome = [(d["prestador"], d["quem_indicou"]) for d in por_provider_rede.values()]
    sem_nome = [p for pid, p in por_provider_fora.items() if pid not in por_provider_rede]

    com_nome.sort(key=lambda par: _relevancia(par[0]), reverse=True)
    sem_nome.sort(key=_relevancia, reverse=True)
    return com_nome, sem_nome


def _formatar_indicadores(nomes):
    """'Joao', 'Joao e Maria', 'Joao, Maria e mais 1'"""
    if not nomes:
        return "alguem da sua rede"
    if len(nomes) == 1:
        return nomes[0]
    if len(nomes) == 2:
        return f"{nomes[0]} e {nomes[1]}"
    return f"{nomes[0]}, {nomes[1]} e mais {len(nomes) - 2}"


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
    if not (servico and cidade):
        return "Faltou servico ou cidade. Pergunte o que faltar com naturalidade."

    com_nome, sem_nome = executar_busca(membro, servico, bairro, cidade)
    local = ", ".join(p for p in [bairro, cidade] if p)

    def _selo(p):
        # Mostra a reputacao pra IA poder destacar os bem avaliados.
        qtd = p.get("qtd_avaliacoes") or 0
        if qtd:
            return f" | avaliacao: {p.get('nota_media')}/5 ({qtd} avaliacao(oes))"
        return " | avaliacao: ainda sem notas"

    if com_nome:
        registrar_busca(servico, bairro, cidade, "verde", membro["id"])
        for p, _ in com_nome:
            registrar_indicacao_recebida(membro["id"], p, servico, bairro, cidade)
        linhas = []
        for p, quem_lista in com_nome:
            endosso = _formatar_indicadores(quem_lista)
            prova = f" | {len(quem_lista)} pessoas da sua rede indicaram" if len(quem_lista) > 1 else ""
            linhas.append(
                f"- Nome: {p['nome']} | telefone (copie EXATO): {p['telefone']} | "
                f"indicado por: {endosso}{prova}{_selo(p)}"
            )
        return ("RESULTADO=verde - indicacoes de pessoas da rede de confianca dela, em "
                f"{local}, JA ORDENADAS pelas mais bem avaliadas. Apresente com alegria, "
                "citando quem indicou (quando mais de uma pessoa indicou o mesmo, destaque "
                "isso — e prova social forte). Mantenha nome e telefone EXATOS:\n"
                + "\n".join(linhas))
    if sem_nome:
        registrar_busca(servico, bairro, cidade, "amarelo", membro["id"])
        for p in sem_nome:
            registrar_indicacao_recebida(membro["id"], p, servico, bairro, cidade)
        linhas = [f"- Nome: {p['nome']} | telefone (copie EXATO): {p['telefone']}{_selo(p)}"
                  for p in sem_nome]
        return ("RESULTADO=amarelo - ha indicacoes boas em "
                f"{local}, mas de FORA da rede dela (NAO revele quem indicou), JA ORDENADAS "
                "pelas mais bem avaliadas. Apresente mantendo o telefone EXATO, destacando a "
                "avaliacao quando houver. AO FINAL, acrescente exatamente esta frase: "
                "'Este profissional foi validado pela rede Dorote.ia. Se você encontrar alguém "
                "de confiança para esse serviço, não esqueça de registrar aqui para fortalecer "
                "a base! 💛':\n" + "\n".join(linhas))

    registrar_busca(servico, bairro, cidade, "vermelho", membro["id"])
    return (f"RESULTADO=vermelho - ninguem indicou {servico} em {local} ainda. Acolha a "
            "pessoa e incentive-a a recomendar alguem que conheca ou a convidar amigos pra "
            "fortalecer a rede.")


def _enviar_alertas_busca_vermelha(recomendador, servico, cidade):
    """Quando uma nova recomendacao e salva, notifica quem buscou o mesmo servico
    na mesma cidade, nao achou nada (vermelho) e ainda nao foi alertado."""
    try:
        candidatas = (supabase.table("searches")
                      .select("id, member_id")
                      .eq("resultado", "vermelho")
                      .eq("alerta_enviado", False)
                      .ilike("servico", servico)
                      .ilike("cidade", cidade)
                      .execute().data)
        if not candidatas:
            return

        # Uma notificacao por membro — ignorar quem acabou de recomendar.
        vistos = {recomendador["id"]}
        for busca in candidatas:
            mid = busca["member_id"]
            if not mid or mid in vistos:
                continue
            vistos.add(mid)

            destino = buscar_membro_por_id(mid)
            if not destino or not destino.get("consent"):
                continue

            primeiro_nome = ((destino.get("nome_perfil") or "").split() or [""])[0]
            saudacao = f"Oi, {primeiro_nome}!" if primeiro_nome else "Oi!"
            texto = (
                f"{saudacao} 💡 Lembra que voce buscou *{servico}* em {cidade} e nao achou nada? "
                "Acabou de aparecer uma indicacao por la — quer buscar de novo?"
            )
            phone_number_id = g.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
            enviar_mensagem_meta(destino["wa_id"], texto, phone_number_id)

            supabase.table("searches").update({"alerta_enviado": True}).eq("id", busca["id"]).execute()
    except Exception:
        traceback.print_exc()


def _ferr_recomendar(membro, entrada, numeros, interativa_enviada):
    """Regra de ouro: o profissional precisa CONSENTIR antes de ser indicado.

    Por isso a IA NAO grava mais uma indicacao 'ao vivo'. Ela so abre o fluxo
    deterministico (guiado por botoes): valida os dados com o cliente e, no fim,
    gera um link de convite para o profissional entrar e aceitar. A indicacao so
    passa a valer quando o profissional entra e o cliente confirma."""
    nome     = (entrada.get("nome")    or "").strip()
    servico  = (entrada.get("servico") or "").strip().lower()
    bairro   = (entrada.get("bairro")  or "").strip()
    detalhe  = (entrada.get("nota") or entrada.get("detalhe") or "").strip()
    telefone = _resolver_ficha(entrada.get("telefone"), numeros)

    # Sem telefone valido: comeca pedindo o contato.
    if not telefone:
        _fluxo_set(membro, {"fluxo": "indicar", "passo": "contato",
                            "nome": nome, "servico": servico,
                            "bairro": bairro, "detalhe": detalhe})
        enviar_botoes_meta(t.INDICAR_INICIO, [{"id": "menu", "label": "🏠 Menu"}])
        interativa_enviada[0] = True
        return "Fluxo de indicacao iniciado (pedindo o contato). Nao escreva mais nada."

    # Regra de ouro: ninguém indica a si mesmo como profissional.
    if _eh_proprio_numero(membro, telefone):
        _avisar_indicacao_si_mesmo()
        interativa_enviada[0] = True
        return "A pessoa tentou indicar o proprio numero. Nao registre. Mensagem ja enviada."

    nome = nome or "essa pessoa"
    fluxo = {"fluxo": "indicar", "nome": nome, "telefone": telefone,
             "servico": servico, "bairro": bairro or "não informado", "detalhe": detalhe}

    # Falta servico ou motivo: pede os detalhes num texto so.
    if not (servico and detalhe):
        fluxo["passo"] = "detalhes"
        _fluxo_set(membro, fluxo)
        enviar_botoes_meta(t.INDICAR_DETALHES.format(nome=nome), [{"id": "menu", "label": "🏠 Menu"}])
        interativa_enviada[0] = True
        return "Fluxo de indicacao iniciado (pedindo detalhes). Nao escreva mais nada."

    # Tem tudo: valida antes de gerar o link.
    fluxo["passo"] = "validar"
    _fluxo_set(membro, fluxo)
    _enviar_validacao_indicacao(membro, fluxo)
    interativa_enviada[0] = True
    return "Validacao da indicacao enviada por botoes. Nao escreva mais nada."


def _ferr_adicionar_contatos(membro, numeros):
    if not numeros:
        return ("Nenhum contato veio nesta mensagem. Peca pra ela compartilhar pelo clipe 📎 "
                "do WhatsApp ou digitar os numeros com DDD.")

    total, membros_na_rede, nao_membros = processar_contatos(membro, numeros)
    qtd_membros = len(membros_na_rede)
    qtd_fora = len(nao_membros)

    linhas = [f"Adicionei {total} contato(s) a rede de confianca dela."]

    # Quem ja e membro: anunciar com entusiasmo.
    if qtd_membros == 1:
        linhas.append(
            f"OTIMA DESCOBERTA: {membros_na_rede[0]} JA usa a Dorote.ia! "
            "Compartilhe com entusiasmo — elas estao conectadas."
        )
    elif qtd_membros > 1:
        nomes = ", ".join(membros_na_rede)
        linhas.append(
            f"OTIMA DESCOBERTA: {qtd_membros} desses JA usam a Dorote.ia: {nomes}! "
            "Compartilhe com entusiasmo — ela ja esta conectada a todas."
        )

    # Quem nao e membro: gera os convites automaticamente, sem pedir pra reenviar.
    if nao_membros:
        numero_bot = g.get("display_phone_number") or ""
        link_geral = encurtar_link(montar_link_convite(numero_bot))
        msg_amigo = t.CONVITE_MENSAGEM_AMIGO.format(link=link_geral)

        for _, numero in nao_membros:
            registrar_convite_pendente(membro, numero)

        individuais = nao_membros[:MAX_LINKS_INDIVIDUAIS]
        linhas_links = []
        for idx, numero in individuais:
            link = encurtar_link(montar_link_para_contato(numero, msg_amigo))
            linhas_links.append(f"[CONTATO_{idx + 1}] -> {link}")

        aviso_extra = ""
        if qtd_fora > MAX_LINKS_INDIVIDUAIS:
            sobra = qtd_fora - MAX_LINKS_INDIVIDUAIS
            aviso_extra = (f"\n(Os outros {sobra} tambem estao atrelados — "
                           "mande esses contatos de novo pra gerar os links deles.)")

        linhas.append(
            f"Ja preparei os convites para os {qtd_fora} que ainda nao usam a Dorote.ia. "
            "Entregue cada link pra pessoa certa, TROCANDO [CONTATO_n] pelo nome "
            "(voce sabe quem e cada ficha). Links (copie EXATOS):\n"
            + "\n".join(linhas_links) + aviso_extra
        )
    else:
        # Todos ja sao membros: nudge para primeira busca.
        linhas.append(
            "Pergunte com leveza se ela ja precisa de alguma indicacao — medico, escola, "
            "prestador, o que for."
        )

    return "\n".join(linhas)


# Quantos links "um toque pra enviar" listamos no maximo (acima disso, melhor a
# mensagem unica pra encaminhar — uma lista enorme de links fica ruim no WhatsApp).
MAX_LINKS_INDIVIDUAIS = 10


def _ferr_convidar(membro, numeros):
    if not numeros:
        return ("Nenhum contato veio nesta mensagem pra convidar. Peca pra compartilhar os "
                "contatos pelo clipe 📎 (pode mandar varios!) ou digitar os numeros com DDD.")
    numero_bot = g.get("display_phone_number") or ""

    # Atrela TODOS os contatos ao convite (conexao pelo telefone, sem codigo).
    for numero in numeros:
        registrar_convite_pendente(membro, numero)

    # Monta a mensagem que vai pre-escrita na conversa com o convidado.
    link_geral = encurtar_link(montar_link_convite(numero_bot))
    msg_amigo = t.CONVITE_MENSAGEM_AMIGO.format(link=link_geral)

    # Link "um toque pra enviar" por contato — encurtado pra IA nao ver o numero real.
    individuais = numeros[:MAX_LINKS_INDIVIDUAIS]
    linhas = []
    for i, numero in enumerate(individuais, start=1):
        link_pronto = encurtar_link(montar_link_para_contato(numero, msg_amigo))
        linhas.append(f"[CONTATO_{i}] -> {link_pronto}")

    aviso_extra = ""
    if len(numeros) > MAX_LINKS_INDIVIDUAIS:
        sobra = len(numeros) - MAX_LINKS_INDIVIDUAIS
        aviso_extra = (f"\n\n(Os outros {sobra} contato(s) tambem ja estao atrelados ao convite — "
                       "pra gerar os links deles, e so mandar esses contatos de novo.)")

    return (
        f"Convites prontos pra {len(numeros)} pessoa(s) — todas ja atreladas ao convite dela "
        "(quando entrarem, ficam conectadas automaticamente, sem precisar de codigo).\n\n"
        "Entregue o link de cada uma, TROCANDO a ficha [CONTATO_n] pelo NOME da pessoa "
        "(voce sabe quem e cada ficha). Cada link abre a conversa com aquela pessoa ja com "
        "o convite escrito; ela so toca em Enviar. Links (copie EXATOS):\n"
        + "\n".join(linhas) + aviso_extra
    )


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
        f"- Contatos na rede dela (guardados com seguranca, sem expor o numero): {contar('edges', membro['id'])}\n"
        f"- Indicacoes que ela fez: {contar('recommendations', membro['id'])}\n"
        "Reforce, de forma simples e proxima, que os numeros dos contatos ficam protegidos e "
        "nunca sao compartilhados, e lembre que ela pode pedir pra apagar tudo quando quiser."
    )


def _ferr_ver_indicacoes(membro):
    """Lista o que a pessoa ja indicou, com nota media quando houver."""
    try:
        recs = (supabase.table("recommendations")
                .select("servico, bairro, cidade, provider_id")
                .eq("member_id", membro["id"])
                .order("created_at", desc=True)
                .execute().data)
    except Exception:
        traceback.print_exc()
        return "Nao consegui carregar suas indicacoes agora. Tente de novo em instantes."

    if not recs:
        return ("Ela ainda nao fez nenhuma indicacao. Diga de forma acolhedora que, quando "
                "quiser indicar alguem, e so compartilhar o contato pelo clipe 📎.")

    linhas = []
    for r in recs:
        prestador = buscar_provider(r["provider_id"])
        if not prestador:
            continue
        local_parts = [r.get("bairro") or "", r.get("cidade") or ""]
        local = ", ".join(p for p in local_parts if p)
        nota = ""
        if prestador.get("qtd_avaliacoes"):
            nota = f" | ⭐ {prestador['nota_media']}/5 ({prestador['qtd_avaliacoes']} aval.)"
        linhas.append(
            f"- *{prestador['nome']}* ({r.get('servico') or 'servico'}"
            f"{', ' + local if local else ''}){nota}"
        )

    if not linhas:
        return "Indicacoes registradas, mas nao consegui carregar os detalhes agora."

    return (f"Ela tem {len(linhas)} indicacao(oes) registrada(s). "
            "Apresente de forma clara e calorosa, destacando as bem avaliadas:\n"
            + "\n".join(linhas))


def _ferr_ver_rede(membro):
    """Descobre quais contatos do grafo da pessoa ja sao membros com consentimento."""
    try:
        edges = (supabase.table("edges").select("contact_hash")
                 .eq("member_id", membro["id"]).execute().data)
    except Exception:
        return "Nao consegui carregar sua rede agora."

    total_contatos = len(edges)
    if total_contatos == 0:
        return ("Ela ainda nao tem contatos na rede. Incentive-a a compartilhar "
                "alguns pelo clipe 📎 para comecar a construir a rede de confianca.")

    hashes_meus = {e["contact_hash"] for e in edges}

    try:
        todos = (supabase.table("members").select("wa_id, nome_perfil")
                 .eq("consent", True).neq("id", membro["id"]).execute().data)
    except Exception:
        return "Nao consegui verificar os membros agora."

    conectados = []
    for m in todos:
        e164 = normalizar_e164(m.get("wa_id") or "")
        if e164 and calcular_contact_hash(e164) in hashes_meus:
            nome = (m.get("nome_perfil") or "").strip()
            conectados.append(nome or "alguem")

    if not conectados:
        return (f"Ela tem {total_contatos} contato(s) na rede (guardados com seguranca), mas "
                "nenhum usa a Dorote.ia ainda. Pergunte se ela quer convidar alguns agora.")

    nomes = "\n".join(f"- {n}" for n in conectados)
    fora = total_contatos - len(conectados)
    extra = f" ({fora} ainda nao usa(m))" if fora else ""
    return (f"{len(conectados)} pessoa(s) da rede dela ja usa(m) a Dorote.ia{extra}. "
            "Apresente com entusiasmo — essas pessoas ja estao conectadas a ela:\n" + nomes)


def _ferr_ver_buscas(membro):
    """Lista as ultimas buscas que a pessoa fez na Dorote.ia."""
    try:
        buscas = (supabase.table("searches")
                  .select("servico, bairro, cidade, resultado")
                  .eq("member_id", membro["id"])
                  .order("created_at", desc=True)
                  .limit(10)
                  .execute().data)
    except Exception:
        return "Nao consegui carregar o historico de buscas."

    if not buscas:
        return ("Ela ainda nao fez nenhuma busca por aqui. "
                "Pergunte o que ela precisa agora — pode ser medico, escola, prestador, o que for.")

    emoji_res = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}
    linhas = []
    for b in buscas:
        local_parts = [b.get("bairro") or "", b.get("cidade") or ""]
        local = ", ".join(p for p in local_parts if p)
        icone = emoji_res.get(b.get("resultado") or "", "⚪")
        linhas.append(f"- {icone} {b['servico']}{' em ' + local if local else ''}")

    return (f"Ultimas {len(linhas)} busca(s) dela. 🟢 achou na rede, 🟡 fora da rede, "
            "🔴 sem resultado. Apresente de forma simples:\n" + "\n".join(linhas))


def _ferr_excluir(membro, entrada):
    if entrada.get("confirmado") is True:
        excluir_membro(membro)
        return ("Todos os dados da pessoa foram apagados. Despeca-se com carinho e diga que, se "
                "um dia quiser voltar, e so mandar um oi.")
    return ("Ainda NAO foi confirmado. Pergunte com cuidado se ela tem certeza de que quer apagar "
            "TUDO (e irreversivel). So chame esta ferramenta de novo com confirmado=true depois do sim.")


def _ferr_avaliar(membro, entrada):
    """Registra a avaliacao de uma indicacao que a pessoa recebeu. So vale pra
    prestadores que JA foram mostrados a ela (integridade da rede de confianca)."""
    nome = (entrada.get("nome") or "").strip()
    usou = entrada.get("usou")
    if not nome:
        return "Faltou o nome do prestador que ela esta avaliando. Pergunte qual foi."

    # Acha a indicacao recebida que casa com esse nome (pendente tem prioridade).
    recebidas = (supabase.table("indicacoes_recebidas").select("*")
                 .eq("member_id", membro["id"]).execute().data)
    candidatos = []
    for ind in recebidas:
        prestador = buscar_provider(ind["provider_id"])
        if prestador and nome.lower() in (prestador["nome"] or "").lower():
            candidatos.append((ind, prestador))
    if not candidatos:
        return (f"Nao encontrei '{nome}' entre as indicacoes que voce ja mostrou a ela. "
                "Pergunte com gentileza qual foi a indicacao (nome do prestador) que ela usou.")
    # Prioriza pendente; se houver mais de um, pega o mais recente.
    candidatos.sort(key=lambda c: (c[0]["status"] == "pendente", c[0].get("created_at") or ""),
                    reverse=True)
    ind, prestador = candidatos[0]

    # Pessoa nao chegou a usar: marca dispensada pra Dorote.ia parar de perguntar.
    if usou is False:
        supabase.table("indicacoes_recebidas").update({
            "status": "dispensada",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", ind["id"]).execute()
        return (f"Ok, ela ainda nao usou {prestador['nome']}. Nao registre nota. Diga sem "
                "problema que e so avisar quando usar, que voce quer saber como foi.")

    # Usou: precisa de nota de 1 a 5.
    nota = entrada.get("nota")
    try:
        nota = int(nota)
    except (TypeError, ValueError):
        nota = None
    if nota is None or not (1 <= nota <= 5):
        return ("Pra registrar, preciso de uma nota de 1 a 5 estrelas. Pergunte de forma leve "
                f"que nota (1 a 5) ela da pra {prestador['nome']}.")

    comentario = (entrada.get("comentario") or "").strip() or None
    agora = datetime.now(timezone.utc).isoformat()

    # Upsert: uma avaliacao por pessoa por prestador (reavaliar atualiza).
    ja = (supabase.table("avaliacoes").select("id")
          .eq("member_id", membro["id"]).eq("provider_id", prestador["id"])
          .limit(1).execute().data)
    if ja:
        supabase.table("avaliacoes").update({
            "nota": nota, "comentario": comentario, "updated_at": agora,
        }).eq("id", ja[0]["id"]).execute()
    else:
        supabase.table("avaliacoes").insert({
            "member_id": membro["id"], "provider_id": prestador["id"],
            "nota": nota, "comentario": comentario,
        }).execute()

    supabase.table("indicacoes_recebidas").update({
        "status": "avaliada", "updated_at": agora,
    }).eq("id", ind["id"]).execute()
    _recalcular_nota_provider(prestador["id"])

    return (f"Avaliacao registrada: {nota}/5 para {prestador['nome']}. Agradeca de coracao e "
            "explique que a nota dela ajuda essa indicacao a ganhar relevancia e chegar com "
            "mais forca pra quem da rede precisar do mesmo servico.")


def _ferr_enviar_botoes(entrada, interativa_enviada):
    texto = (entrada.get("texto") or "").strip()
    botoes = entrada.get("botoes") or []
    if not texto or not botoes:
        return "Faltou texto ou botoes. Tente de novo."
    enviar_botoes_meta(texto, botoes)
    interativa_enviada[0] = True
    return "ok - mensagem com botoes enviada. Sua resposta de texto final deve ser VAZIA."


def _notificar_convidante(novo_membro):
    """Avisa quem convidou que seu contato acabou de entrar na Dorote.ia."""
    try:
        convidante = buscar_membro_por_id(novo_membro.get("invited_by"))
        if not convidante or not convidante.get("consent"):
            return
        primeiro_nome = ((novo_membro.get("nome_perfil") or "").split() or [""])[0]
        nome_exibir = primeiro_nome or "Alguem que voce convidou"
        texto = (
            f"Boa notícia! 🎉 *{nome_exibir}* acabou de entrar na Dorote.ia pelo seu convite. "
            "Agora vocês estão na mesma rede de confiança! 💛"
        )
        phone_number_id = g.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
        enviar_mensagem_meta(convidante["wa_id"], texto, phone_number_id)
    except Exception:
        traceback.print_exc()


def construir_executor(membro, interativa_enviada):
    """Devolve a funcao que a IA usa pra disparar acoes. Mantem o consentimento
    como porteiro: sem consent, so 'registrar_consentimento' funciona."""
    # enviar_botoes nao toca dados — e justamente como a Dorote.ia PEDE o consentimento.
    # Bloquea-lo aqui criava um deadlock (modelo chamava botoes -> gate recusava ->
    # loop -> "me perdi"). Por isso fica liberado mesmo sem consent.
    LIVRES_SEM_CONSENT = ("registrar_consentimento", "enviar_botoes")

    def executar(nome, entrada, numeros):
        if nome not in LIVRES_SEM_CONSENT and not membro.get("consent"):
            return ("A pessoa ainda nao consentiu. Nao execute acoes; peca o 'pode ser' dela primeiro.")
        if nome == "registrar_consentimento":
            registrar_consentimento(membro["wa_id"])
            membro["consent"] = True
            if membro.get("invited_by"):
                _notificar_convidante(membro)
            return (
                "Consentimento registrado. Responda em NO MAXIMO 3 linhas: "
                "uma frase de boas-vindas calorosa (cite quem convidou se souber), "
                "convite para compartilhar contatos pelo clipe 📎, "
                "e pergunte se ja precisa de alguma indicacao agora. Nada mais."
            )
        if nome == "buscar_servico":
            return _ferr_buscar(membro, entrada)
        if nome == "salvar_recomendacao":
            return _ferr_recomendar(membro, entrada, numeros, interativa_enviada)
        if nome == "adicionar_contatos":
            return _ferr_adicionar_contatos(membro, numeros)
        if nome == "convidar_pessoa":
            return _ferr_convidar(membro, numeros)
        if nome == "gerar_link_convite":
            return _ferr_link_generico(membro)
        if nome == "ver_meus_dados":
            return _ferr_ver_dados(membro)
        if nome == "ver_minhas_indicacoes":
            return _ferr_ver_indicacoes(membro)
        if nome == "ver_minha_rede":
            return _ferr_ver_rede(membro)
        if nome == "ver_minhas_buscas":
            return _ferr_ver_buscas(membro)
        if nome == "excluir_meus_dados":
            return _ferr_excluir(membro, entrada)
        if nome == "avaliar_indicacao":
            return _ferr_avaliar(membro, entrada)
        if nome == "registrar_ajuda":
            return _ferr_registrar_ajuda(membro, entrada)
        if nome == "enviar_botoes":
            return _ferr_enviar_botoes(entrada, interativa_enviada)
        return "Ferramenta desconhecida."
    return executar


def _ferr_registrar_ajuda(membro, entrada):
    """Registra um pedido de ajuda e avisa a equipe (se houver numero configurado)."""
    mensagem = (entrada.get("mensagem") or "").strip()
    if not mensagem:
        return "Faltou o relato. Pergunte com gentileza o que aconteceu."
    nome = (membro.get("nome_perfil") or "").strip()
    try:
        supabase.table("suporte").insert({
            "member_id": membro["id"], "wa_id": membro.get("wa_id"),
            "nome": nome or None, "mensagem": mensagem,
        }).execute()
    except Exception:
        traceback.print_exc()
    # Aviso a equipe (so funciona se a equipe tiver falado com o bot nas ultimas 24h).
    if SUPORTE_WA_ID:
        try:
            aviso = (f"🆘 *Pedido de ajuda na Dorote.ia*\n"
                     f"De: {nome or 'sem nome'} ({membro.get('wa_id')})\n\n{mensagem}")
            enviar_mensagem_meta(SUPORTE_WA_ID, aviso,
                                 g.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID)
        except Exception:
            traceback.print_exc()
    return ("Pedido de ajuda registrado e encaminhado para a equipe. Responda com acolhimento "
            "e tom proximo: diga que recebeu, que ja encaminhou para alguem da equipe e que, se "
            "precisar de retorno, a equipe responde por aqui em breve. Ofereca o MENU pra "
            "continuar enquanto isso. Nao prometa prazo exato.")


# ===========================================================================
# FOLLOW-UP PROATIVO DE AVALIACAO (cron diario)
# ===========================================================================

# Quantos dias apos a indicacao enviamos o follow-up ("usou? como foi?").
DIAS_PARA_FOLLOW_UP = 7
# Maximo de mensagens por rodada (evita rajada na API da Meta).
MAX_FOLLOW_UPS_POR_RODADA = 50


def _enviar_follow_ups():
    """Busca indicacoes pendentes sem follow-up ha >= DIAS_PARA_FOLLOW_UP dias
    e manda uma mensagem proativa pedindo a avaliacao. Retorna quantas enviou."""
    limite = (datetime.now(timezone.utc) - timedelta(days=DIAS_PARA_FOLLOW_UP)).isoformat()

    try:
        # Busca pendentes mais antigas que o limite, ordenadas da mais nova pra
        # mais antiga (se houver varias por membro, pega a mais recente).
        candidatas = (supabase.table("indicacoes_recebidas")
                      .select("*")
                      .eq("status", "pendente")
                      .is_("follow_up_at", "null")
                      .lt("created_at", limite)
                      .order("created_at", desc=True)
                      .limit(MAX_FOLLOW_UPS_POR_RODADA * 3)
                      .execute().data)
    except Exception:
        traceback.print_exc()
        return 0

    # Uma mensagem por membro por rodada (a indicacao mais recente).
    vistos = set()
    selecionadas = []
    for ind in candidatas:
        mid = ind["member_id"]
        if mid not in vistos:
            vistos.add(mid)
            selecionadas.append(ind)
        if len(selecionadas) >= MAX_FOLLOW_UPS_POR_RODADA:
            break

    enviados = 0
    agora = datetime.now(timezone.utc).isoformat()

    for ind in selecionadas:
        try:
            membro = buscar_membro_por_id(ind["member_id"])
            if not membro or not membro.get("consent"):
                continue
            prestador = buscar_provider(ind["provider_id"])
            if not prestador:
                continue

            primeiro_nome = ((membro.get("nome_perfil") or "").split() or [""])[0]
            nome_prest = prestador["nome"]
            servico = ind.get("servico") or prestador.get("servico") or ""
            local_parts = [ind.get("bairro") or "", ind.get("cidade") or ""]
            local = ", ".join(p for p in local_parts if p)

            saudacao = f"Oi, {primeiro_nome}!" if primeiro_nome else "Oi!"
            detalhe = f"{servico}{' em ' + local if local else ''}"
            texto = (
                f"{saudacao} 👋 Há alguns dias te indiquei *{nome_prest}*"
                f"{' (' + detalhe + ')' if detalhe else ''}. "
                "Você chegou a usar? Conta pra mim como foi 😊"
            )

            enviar_mensagem_meta(membro["wa_id"], texto, WHATSAPP_PHONE_NUMBER_ID)

            supabase.table("indicacoes_recebidas").update({
                "follow_up_at": agora,
            }).eq("id", ind["id"]).execute()

            enviados += 1
            time.sleep(0.3)   # respeita o rate-limit da API da Meta

        except Exception:
            traceback.print_exc()

    print(f"[FOLLOW-UP] {enviados} mensagem(ns) enviada(s).")
    return enviados


# Quantos dias apos o consent esperamos antes de lembrar de adicionar contatos.
DIAS_PARA_NUDGE_CONTATOS = 2
MAX_NUDGES_POR_RODADA = 50


def _enviar_nudge_contatos():
    """Lembra membros que consentiram ha >= DIAS_PARA_NUDGE_CONTATOS dias mas
    ainda nao adicionaram nenhum contato na rede. Envia no maximo uma vez
    (nudge_contatos_at registra o envio). Retorna quantos nudges enviou."""
    limite = (datetime.now(timezone.utc) - timedelta(days=DIAS_PARA_NUDGE_CONTATOS)).isoformat()

    try:
        candidatos = (supabase.table("members")
                      .select("id, wa_id, nome_perfil")
                      .eq("consent", True)
                      .is_("nudge_contatos_at", "null")
                      .lt("consent_at", limite)
                      .limit(MAX_NUDGES_POR_RODADA)
                      .execute().data)
    except Exception:
        traceback.print_exc()
        return 0

    enviados = 0
    agora = datetime.now(timezone.utc).isoformat()

    for membro in candidatos:
        try:
            # Marca antes de enviar — evita duplicata mesmo se o envio falhar.
            supabase.table("members").update({"nudge_contatos_at": agora}).eq("id", membro["id"]).execute()

            # So envia se a pessoa realmente nao tem contatos ainda.
            tem_contatos = (supabase.table("edges").select("id")
                            .eq("member_id", membro["id"]).limit(1).execute().data)
            if tem_contatos:
                continue

            primeiro_nome = ((membro.get("nome_perfil") or "").split() or [""])[0]
            saudacao = f"Oi, {primeiro_nome}!" if primeiro_nome else "Oi!"
            texto = (
                f"{saudacao} 😊 Voce ainda nao tem contatos na sua rede da Dorote.ia. "
                "E ai que a magica acontece — quanto mais gente de confianca voce trouxer, "
                "melhores as indicacoes que aparecem pra voce! "
                "Manda alguns pelo clipe 📎 do WhatsApp, pode ser varios de uma vez. 💛"
            )
            enviar_mensagem_meta(membro["wa_id"], texto, WHATSAPP_PHONE_NUMBER_ID)
            enviados += 1
            time.sleep(0.3)

        except Exception:
            traceback.print_exc()

    print(f"[NUDGE-CONTATOS] {enviados} nudge(s) enviado(s).")
    return enviados


@app.route("/cron/follow-up", methods=["POST"])
def cron_follow_up():
    """Endpoint chamado pelo cron diario (GitHub Actions).
    Protegido por X-Cron-Secret para impedir acionamento externo nao autorizado."""
    if CRON_SECRET and request.headers.get("X-Cron-Secret") != CRON_SECRET:
        return Response("Nao autorizado.", status=401)
    follow_ups = _enviar_follow_ups()
    nudges = _enviar_nudge_contatos()
    return Response(f"OK - {follow_ups} follow-up(s), {nudges} nudge(s) enviado(s).", status=200)


# ===========================================================================
# A PORTA PRINCIPAL (WhatsApp Cloud API)
# ===========================================================================

@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    if (request.args.get("hub.mode") == "subscribe"
            and request.args.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN):
        return Response(request.args.get("hub.challenge", ""), mimetype="text/plain")
    return Response("Token de verificacao invalido", status=403)


# Dedup: ids de mensagens ja processadas (a Meta as vezes reentrega o mesmo
# webhook, o que gerava resposta duplicada).
_MSGS_VISTAS = set()
_MSGS_VISTAS_MAX = 500


def _ja_processada(msg_id):
    if not msg_id:
        return False
    if msg_id in _MSGS_VISTAS:
        return True
    _MSGS_VISTAS.add(msg_id)
    if len(_MSGS_VISTAS) > _MSGS_VISTAS_MAX:
        for antigo in list(_MSGS_VISTAS)[:_MSGS_VISTAS_MAX // 2]:
            _MSGS_VISTAS.discard(antigo)
    return False


@app.route("/webhook", methods=["POST"])
def webhook():
    if not assinatura_meta_valida():
        print("[SEGURANCA] mensagem rejeitada: assinatura invalida.")
        return Response("Assinatura invalida", status=403)
    dados = request.get_json(silent=True) or {}
    # Responde 200 IMEDIATAMENTE e processa em segundo plano. Assim a Meta nao
    # reenvia o webhook (causa das mensagens duplicadas) e a pessoa nao fica esperando
    # o servidor "acordar" pra dar o aceite.
    threading.Thread(target=_processar_em_background, args=(dados,), daemon=True).start()
    return Response("OK", status=200)


def _processar_em_background(dados):
    with app.app_context():
        try:
            processar_eventos(dados)
        except Exception:
            traceback.print_exc()


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
                if _ja_processada(msg.get("id")):
                    continue
                origem = msg.get("from", "")
                nome_perfil = nomes.get(origem, "")
                texto, contatos = conteudo_da_mensagem(msg)
                button_id = _button_id(msg)
                # contatos: [(e164, nome_card)] para tipo=="contacts", [] nos demais casos

                g.to = origem
                g.phone_number_id = phone_number_id
                g.display_phone_number = display

                # Mostra "digitando..." na hora, pra nao parecer que travou.
                marcar_lido_digitando(msg.get("id"), phone_number_id)

                wa_id = _e164(origem)
                print(f"Mensagem de {wa_id} ({nome_perfil}): {texto!r}"
                      + (f" [botao={button_id}]" if button_id else ""))
                try:
                    _processar_mensagem(wa_id, texto, nome_perfil, contatos, button_id)
                except Exception:
                    traceback.print_exc()
                    resposta_whatsapp(t.ERRO_GENERICO)


# ===========================================================================
# MENUS DETERMINISTICOS (navegacao por botoes — sem IA, pra nao inventar fluxo)
# ===========================================================================

def enviar_menu_principal(texto=None):
    enviar_botoes_meta(texto or "O que você deseja fazer? 💛", [
        {"id": "rede_indicar",  "label": "Indicar profissional"},
        {"id": "rede_convidar", "label": "Convidar quem confio"},
        {"id": "outras_opcoes", "label": "Outras Opções"},
    ])


def enviar_outras_opcoes():
    enviar_botoes_meta("Outras opções 💛", [
        {"id": "buscar",        "label": "🔍 Buscar"},
        {"id": "quero_ser_prof", "label": "💼 Ser profissional"},
        {"id": "dados",         "label": "⚙️ Minha conta"},
    ])


def enviar_submenu_dados():
    enviar_botoes_meta("Minha conta ⚙️", [
        {"id": "dados_ver",    "label": "📋 Ver meus dados"},
        {"id": "dados_apagar", "label": "🗑️ Sair / apagar"},
        {"id": "menu",         "label": "🏠 Menu"},
    ])


def gerar_e_enviar_link_convite(membro):
    """Convite do perfil CLIENTE para trazer outra pessoa de confiança (outro cliente)
    para a rede. Entrega as duas mensagens oficiais: a que a pessoa vê (com o link) e a
    pronta para encaminhar. É um link diferente do de indicar um profissional."""
    numero_bot = g.get("display_phone_number") or ""
    codigo = obter_ou_criar_codigo(membro)
    link = encurtar_link(montar_link_convite(numero_bot, codigo))
    resposta_whatsapp(t.CONVIDAR_CLIENTE_VOCE.format(link=link))
    resposta_whatsapp(t.CONVITE_MENSAGEM_AMIGO.format(link=link))


def _perfil_tipo(membro):
    """'cliente', 'profissional' ou 'hibrido' — para diferenciar a saida."""
    prest = provider_do_membro(membro["id"])
    tem_prof = bool(prest and prest.get("status") in PRESTADOR_ATIVO_STATUS)
    if not tem_prof:
        return "cliente"
    tem_cliente = contar("edges", membro["id"]) > 0 or contar("recommendations", membro["id"]) > 0
    return "hibrido" if tem_cliente else "profissional"


def enviar_confirmar_exclusao(membro):
    tipo = _perfil_tipo(membro)
    if tipo == "hibrido":
        enviar_botoes_meta(t.SAIR_HIBRIDO, [
            {"id": "apagar_sim",     "label": "✅ Sair de tudo"},
            {"id": "sair_um_perfil", "label": "⚙️ Ficar com 1 perfil"},
            {"id": "apagar_nao",     "label": "💛 Quero ficar"},
        ])
    else:
        texto = t.SAIR_PROFISSIONAL if tipo == "profissional" else t.SAIR_CLIENTE
        enviar_botoes_meta(texto, [
            {"id": "apagar_sim", "label": "✅ Confirmar saída"},
            {"id": "apagar_nao", "label": "💛 Quero ficar"},
        ])


def enviar_escolha_ficar_um_perfil():
    enviar_botoes_meta("Qual perfil você quer manter?", [
        {"id": "sair_so_cliente", "label": "🔍 Só Cliente"},
        {"id": "sair_so_prof",    "label": "💼 Só Profissional"},
        {"id": "apagar_nao",      "label": "🔙 Voltar"},
    ])


def _resumo_dados_texto(membro):
    nome = (membro.get("nome_perfil") or "").strip() or "(sem nome)"
    n_contatos = contar("edges", membro["id"])
    n_indic = contar("recommendations", membro["id"])
    linhas = [
        "📋 *Seus dados aqui comigo:*",
        f"- Nome: {nome}",
        f"- Contatos na sua rede (guardados com segurança, sem expor o número): {n_contatos}",
        f"- Indicações que você fez: {n_indic}",
    ]
    link = os.environ.get("TERMOS_URL") or (PUBLIC_BASE_URL + "/termos")
    linhas.append("\n🔒 Os números dos seus contatos ficam protegidos e nunca são compartilhados.")
    linhas.append("Termos e privacidade:\n" + link)
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# PRESTADOR DE SERVICO (Fase 3) — onboarding e perfil profissional
# ---------------------------------------------------------------------------
def extrair_codigo_prestador(texto):
    """Le o servico de um link de prestador: '(prestador: encanador)' -> 'encanador'."""
    achado = re.search(r"prestador:\s*([\w \-]{2,40})", texto or "", re.IGNORECASE)
    return achado.group(1).strip().lower() if achado else None


def montar_link_prestador(numero_bot, servico):
    mensagem = f"Ola! Quero fazer parte da Dorote.ia como profissional (prestador: {servico})"
    return f"https://wa.me/{numero_bot}?text={quote(mensagem)}"


def provider_do_membro(member_id):
    """Perfil de prestador do membro (o mais recente em onboarding/ativo), ou None."""
    try:
        res = (supabase.table("providers").select("*")
               .eq("member_id", member_id)
               .in_("status", ["onboarding", "aguardando_perfil", "ativo", "pausado"])
               .order("created_at", desc=True).limit(1).execute().data)
        return res[0] if res else None
    except Exception:
        traceback.print_exc()
        return None


def _criar_perfil_profissional_self(membro):
    """Autocadastro de profissional: cria o perfil (aguardando_perfil) para o membro.

    Usado tanto no onboarding inicial (caminho "quero ser profissional" antes do
    aceite) quanto no menu "Outras opções" depois do aceite. Idempotente.
    """
    if provider_do_membro(membro["id"]):
        return
    agora = datetime.now(timezone.utc).isoformat()
    try:
        telefone = normalizar_e164(membro["wa_id"]) or membro["wa_id"]
        supabase.table("providers").insert({
            "member_id": membro["id"],
            "nome": (membro.get("nome_perfil") or "").strip() or "Profissional",
            "telefone": telefone, "servico": "", "cidade": "",
            "status": "aguardando_perfil",
            "termos_aceitos_em": agora, "termos_versao": termos.DATA_VIGENCIA,
        }).execute()
    except Exception:
        traceback.print_exc()


def iniciar_onboarding_prestador(membro, servico):
    """Vincula (ou cria) um cadastro de prestador ao membro e pede o aceite."""
    try:
        telefone = normalizar_e164(membro["wa_id"]) or membro["wa_id"]
        # Reaproveita um registro ja indicado com esse telefone, se houver.
        existente = (supabase.table("providers").select("*")
                     .eq("telefone", telefone).limit(1).execute().data)
        dados = {"member_id": membro["id"], "status": "onboarding"}
        if servico:
            dados["servico"] = servico
        if existente:
            prov = existente[0]
            supabase.table("providers").update(dados).eq("id", prov["id"]).execute()
            servico_final = servico or prov.get("servico") or "seu serviço"
        else:
            dados.update({
                "nome": (membro.get("nome_perfil") or "").strip() or "Profissional",
                "telefone": telefone, "servico": servico or "", "cidade": "",
            })
            supabase.table("providers").insert(dados).execute()
            servico_final = servico or "seu serviço"
        enviar_botoes_meta(t.PRESTADOR_ACOLHIDA.format(servico=servico_final), [
            {"id": "prest_aceito",  "label": "✅ Aceito e confirmo"},
            {"id": "prest_ajustar", "label": "✏️ Ajustar serviço"},
            {"id": "prest_nao",     "label": "⛔ Não desejo"},
        ])
    except Exception:
        traceback.print_exc()
        resposta_whatsapp(t.ERRO_GENERICO)


def enviar_escolha_perfil():
    enviar_botoes_meta(
        "Você tem dois perfis aqui 💛 Com qual deles quer seguir agora?\n\n"
        "🔍 *Como cliente* — buscar, indicar e convidar quem você confia.\n"
        "💼 *Como profissional* — cuidar do seu cadastro para ser recomendado.",
        [{"id": "perfil_cliente",      "label": "🔍 Como cliente"},
         {"id": "perfil_profissional", "label": "💼 Profissional"}])


def enviar_menu_prestador():
    enviar_botoes_meta("💼 Visão Profissional. Como posso ajudar com o seu cadastro hoje?", [
        {"id": "prest_editar", "label": "✏️ Editar perfil"},
        {"id": "prest_pausar", "label": "⏸️ Pausar/Ativar"},
        {"id": "menu",         "label": "🏠 Menu"},
    ])


# Acoes da IA que CONCLUEM um pedido — depois delas mostramos o menu principal.
TOOLS_TERMINAIS = {
    "buscar_servico", "salvar_recomendacao", "adicionar_contatos", "convidar_pessoa",
    "gerar_link_convite", "ver_meus_dados", "ver_minhas_indicacoes",
    "ver_minha_rede", "ver_minhas_buscas", "avaliar_indicacao", "registrar_ajuda",
}

ACEITES_TXT = {"sim", "aceito", "aceitar", "concordo", "pode ser", "bora", "ok",
               "topo", "claro", "aceito os termos"}

MENU_TRIGGERS = {"menu", "inicio", "voltar", "home", "🏠 menu", "oi", "ola", "olá",
                 "oie", "opa", "bom dia", "boa tarde", "boa noite", "menu principal"}

# Status de prestador que ja contam como "tem perfil profissional" (mostra visao dupla).
PRESTADOR_ATIVO_STATUS = {"aguardando_perfil", "ativo", "pausado"}

# Botoes que pertencem ao fluxo de indicacao (qualquer outro botao sai do fluxo).
BOTOES_INDICAR = {"ind_certo", "ind_corrigir"}


# ---------------------------------------------------------------------------
# FLUXO: CLIENTE INDICA UM PROFISSIONAL (regra de ouro — consentimento primeiro)
# ---------------------------------------------------------------------------
def _eh_proprio_numero(membro, telefone):
    """True se o telefone informado for o numero da propria pessoa — ninguem indica
    a si mesmo como profissional (usa a opcao 'Quero ser profissional')."""
    proprio = normalizar_e164(membro.get("wa_id") or "")
    return bool(telefone) and bool(proprio) and telefone == proprio


def _avisar_indicacao_si_mesmo():
    enviar_botoes_meta(t.INDICAR_SI_MESMO, [
        {"id": "quero_ser_prof", "label": "💼 Ser profissional"},
        {"id": "menu",           "label": "🏠 Menu"},
    ])


def _enviar_validacao_indicacao(membro, fluxo):
    enviar_botoes_meta(
        t.INDICAR_VALIDAR.format(
            nome=fluxo.get("nome", ""), servico=fluxo.get("servico", "") or "—",
            bairro=fluxo.get("bairro", "") or "—", detalhe=fluxo.get("detalhe", "") or "—"),
        [{"id": "ind_certo",    "label": "✅ Está certo"},
         {"id": "ind_corrigir", "label": "✏️ Corrigir"}])


def _passo_indicar(membro, fluxo, texto, button_id, contatos, cmd):
    """Conduz um passo do fluxo de indicacao. Retorna True se ja respondeu."""
    passo = fluxo.get("passo")

    # Passo 1 — receber o CONTATO (card pelo clipe ou nome+telefone digitado).
    if passo == "contato":
        nome, telefone = "", ""
        if contatos:
            telefone, nome = contatos[0][0], (contatos[0][1] or "")
        if not telefone and texto:
            achado = re.search(r"(\+?\d[\d\s().\-]{7,}\d)", texto)
            if achado:
                telefone = _e164(achado.group(1))
                nome = texto.replace(achado.group(1), " ").strip(" -·,.\n\t")
            if not telefone:
                dados = nlu.extrair_recomendacao(texto)
                telefone = _e164(dados.get("telefone", ""))
                nome = (dados.get("nome") or nome).strip()
        if not telefone:
            enviar_botoes_meta(t.INDICAR_PEDIR_TELEFONE, [{"id": "menu", "label": "🏠 Menu"}])
            return True
        if _eh_proprio_numero(membro, telefone):
            _avisar_indicacao_si_mesmo()
            return True
        nome = (nome or fluxo.get("nome") or "").strip() or "essa pessoa"
        fluxo.update({"passo": "detalhes", "nome": nome, "telefone": telefone})
        _fluxo_set(membro, fluxo)
        enviar_botoes_meta(t.INDICAR_DETALHES.format(nome=nome), [{"id": "menu", "label": "🏠 Menu"}])
        return True

    # Passo 2 — receber SERVICO + BAIRRO + MOTIVO num texto so.
    if passo == "detalhes":
        if not (texto or "").strip():
            enviar_botoes_meta(
                t.INDICAR_DETALHES.format(nome=fluxo.get("nome", "essa pessoa")),
                [{"id": "menu", "label": "🏠 Menu"}])
            return True
        dados = nlu.extrair_indicacao(texto)
        # O nome só é sobrescrito se a pessoa o repetiu (ex.: numa correção).
        if (dados.get("nome") or "").strip():
            fluxo["nome"] = dados["nome"].strip()
        fluxo["servico"] = (dados.get("servico") or fluxo.get("servico") or texto).strip()
        fluxo["bairro"]  = (dados.get("bairro") or fluxo.get("bairro") or "não informado").strip()
        fluxo["detalhe"] = (dados.get("detalhe") or texto).strip()
        fluxo["passo"] = "validar"
        _fluxo_set(membro, fluxo)
        _enviar_validacao_indicacao(membro, fluxo)
        return True

    # Passo 3 — validação (botões Está certo / Corrigir).
    if passo == "validar":
        if cmd == "ind_corrigir":
            fluxo["passo"] = "detalhes"
            _fluxo_set(membro, fluxo)
            resposta_whatsapp(t.INDICAR_CORRIGIR.format(
                nome=fluxo.get("nome", ""), servico=fluxo.get("servico", ""),
                bairro=fluxo.get("bairro", ""), detalhe=fluxo.get("detalhe", "")))
            return True
        if cmd == "ind_certo":
            _finalizar_indicacao(membro, fluxo)
            return True
        _enviar_validacao_indicacao(membro, fluxo)
        return True

    # Estado desconhecido: encerra o fluxo com segurança.
    _fluxo_limpar(membro)
    return False


def _finalizar_indicacao(membro, fluxo):
    """Cria o profissional como 'convidado', registra o convite pendente e gera o
    link para o cliente encaminhar. A indicacao só vira recomendação quando o
    profissional entra, aceita e o cliente confirma."""
    telefone = fluxo.get("telefone", "")
    nome     = (fluxo.get("nome") or "").strip() or "Profissional"
    servico  = (fluxo.get("servico") or "").strip().lower()
    bairro   = (fluxo.get("bairro") or "").strip() or "não informado"
    detalhe  = (fluxo.get("detalhe") or "").strip()
    # Regra de ouro: ninguém indica a si mesmo.
    if _eh_proprio_numero(membro, telefone):
        _fluxo_limpar(membro)
        _avisar_indicacao_si_mesmo()
        return
    try:
        existente = (supabase.table("providers").select("*")
                     .eq("telefone", telefone).limit(1).execute().data)
        if existente:
            prov = existente[0]
            # Não mexe em quem já entrou/é ativo; só completa um registro 'convidado'.
            if prov.get("status") in (None, "", "convidado", "removido"):
                supabase.table("providers").update({
                    "nome": nome, "servico": servico, "bairro": bairro,
                    "cidade": "São Paulo", "descricao": detalhe, "status": "convidado",
                }).eq("id", prov["id"]).execute()
        else:
            supabase.table("providers").insert({
                "nome": nome, "telefone": telefone, "servico": servico or "serviço",
                "bairro": bairro, "cidade": "São Paulo", "descricao": detalhe,
                "status": "convidado",
            }).execute()
        # Liga o profissional a quem indicou assim que ele entrar pelo número.
        registrar_convite_pendente(membro, telefone)
    except Exception:
        traceback.print_exc()

    _fluxo_limpar(membro)
    numero_bot = g.get("display_phone_number") or ""
    link = encurtar_link(montar_link_prestador(numero_bot, servico or "serviço")) if numero_bot else ""
    resposta_whatsapp(t.INDICAR_LINK.format(nome=nome, link=link or "(link indisponível no momento)"))
    enviar_menu_principal()


def _notificar_indicante(provider_membro, prest):
    """Avisa quem indicou que o profissional entrou e pede a confirmação final."""
    try:
        cliente = buscar_membro_por_id(provider_membro.get("invited_by"))
        if not cliente or not cliente.get("consent"):
            return
        nome = ((prest.get("nome") or "").strip()
                or (provider_membro.get("nome_perfil") or "").strip()
                or "a pessoa que você indicou")
        phone_number_id = g.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
        enviar_botoes_meta(
            t.INDICAR_CONFIRMA_CLIENTE.format(nome=nome),
            [{"id": f"ind_ok:{provider_membro['id']}", "label": "✅ Sim, confirmo"},
             {"id": f"ind_no:{provider_membro['id']}", "label": "❌ Não conheço"}],
            to=cliente["wa_id"], phone_number_id=phone_number_id)
    except Exception:
        traceback.print_exc()


def _confirmar_indicacao(cliente, provider_member_id, confirmou):
    """Cliente respondeu se conhece o profissional que indicou. Só agora (no 'sim')
    a recomendação passa a valer na rede."""
    prov = provider_do_membro(provider_member_id) if provider_member_id else None
    nome = (prov or {}).get("nome") or "essa pessoa"
    if not confirmou:
        resposta_whatsapp(t.INDICAR_NEGADA.format(nome=nome))
        enviar_menu_principal()
        return
    if not prov:
        resposta_whatsapp("Não encontrei mais essa indicação por aqui. 💛")
        enviar_menu_principal()
        return
    try:
        ja = (supabase.table("recommendations").select("id")
              .eq("member_id", cliente["id"]).eq("provider_id", prov["id"]).limit(1).execute().data)
        if not ja:
            supabase.table("recommendations").insert({
                "member_id": cliente["id"], "provider_id": prov["id"],
                "servico": prov.get("servico") or "serviço",
                "bairro": prov.get("bairro") or "não informado",
                "cidade": prov.get("cidade") or "São Paulo",
            }).execute()
    except Exception:
        traceback.print_exc()
    resposta_whatsapp(t.INDICAR_CONFIRMADA.format(nome=nome))
    enviar_menu_principal()


def rotear_menu(membro, texto, button_id, contatos=None):
    """Trata a navegacao deterministica (botoes/menus/comandos fixos).
    Retorna True se ja respondeu (nao precisa chamar a IA)."""
    cmd = (button_id or re.sub(r"\s+", " ", (texto or "").strip().lower()))
    consentiu = bool(membro.get("consent"))

    # -------- Exclusao (SAIR) — vale antes e depois do aceite --------
    # Os botoes de confirmacao vem PRIMEIRO; senao o gatilho generico de "apagar"
    # capturaria 'apagar_sim'/'apagar_nao' e a confirmacao entraria em loop.
    if cmd == "apagar_sim":
        # Sair de tudo: tira o perfil profissional das buscas e apaga o cadastro.
        prest = provider_do_membro(membro["id"])
        if prest:
            try:
                supabase.table("providers").update(
                    {"status": "removido", "member_id": None}).eq("id", prest["id"]).execute()
            except Exception:
                traceback.print_exc()
        excluir_membro(membro)
        resposta_whatsapp(t.ADEUS)
        return True
    if cmd == "apagar_nao":
        resposta_whatsapp("Ufa, não apaguei nada! 😌 Está tudo no lugar.")
        if consentiu:
            enviar_menu_principal()
        return True
    if cmd == "sair_um_perfil":
        enviar_escolha_ficar_um_perfil()
        return True
    if cmd == "sair_so_cliente":
        prest = provider_do_membro(membro["id"])
        if prest:
            supabase.table("providers").update(
                {"status": "removido"}).eq("id", prest["id"]).execute()
        resposta_whatsapp("Pronto! 💛 Mantivemos apenas o seu perfil de cliente. "
                          "Você não será mais recomendado como profissional.")
        enviar_menu_principal()
        return True
    if cmd == "sair_so_prof":
        try:
            supabase.table("edges").delete().eq("member_id", membro["id"]).execute()
        except Exception:
            traceback.print_exc()
        resposta_whatsapp("Pronto! 💼 Mantivemos apenas o seu perfil profissional. "
                          "As suas conexões de cliente foram removidas.")
        enviar_menu_prestador()
        return True
    if cmd in ("sair", "dados_apagar") or re.search(r"\b(apagar|excluir|deletar)\b", cmd):
        enviar_confirmar_exclusao(membro)
        return True

    # -------- Confirmacao final da indicacao (cliente avisado que o prof. entrou) --------
    if cmd.startswith("ind_ok:"):
        _confirmar_indicacao(membro, cmd.split(":", 1)[1], True)
        return True
    if cmd.startswith("ind_no:"):
        _confirmar_indicacao(membro, cmd.split(":", 1)[1], False)
        return True

    # -------- Fluxo ativo: o cliente esta INDICANDO um profissional --------
    fluxo = _fluxo_get(membro)
    if consentiu and fluxo.get("fluxo") == "indicar":
        # Botoes proprios do fluxo seguem para o passo certo; texto idem.
        if button_id in BOTOES_INDICAR or not button_id:
            if cmd in ("menu", "voltar", "cancelar", "inicio"):
                _fluxo_limpar(membro)
                enviar_menu_principal()
                return True
            if _passo_indicar(membro, fluxo, texto, button_id, contatos, cmd):
                return True
        else:
            # Clicou em outro botao de navegacao (menu, ser profissional, etc.):
            # encerra o fluxo e deixa o tratamento normal abaixo cuidar do botao.
            _fluxo_limpar(membro)

    # -------- Prestador de servico: onboarding e perfil --------
    prest = provider_do_membro(membro["id"])
    if prest:
        if cmd == "prest_aceito":
            agora = datetime.now(timezone.utc).isoformat()
            supabase.table("providers").update({
                "status": "aguardando_perfil",
                "termos_aceitos_em": agora,
                "termos_versao": termos.DATA_VIGENCIA,
            }).eq("id", prest["id"]).execute()
            if not membro.get("consent"):
                registrar_consentimento(membro["wa_id"]); membro["consent"] = True
            # Se este profissional foi INDICADO por alguem (regra de ouro), avisa
            # quem indicou para a confirmacao final "vocês se conhecem?".
            if membro.get("invited_by") and (prest.get("descricao") or "").strip():
                _notificar_indicante(membro, prest)
            resposta_whatsapp(t.PRESTADOR_REFINAMENTO)
            return True
        if cmd == "prest_ajustar":
            resposta_whatsapp(t.PRESTADOR_AJUSTAR)
            return True
        if cmd == "prest_nao":
            supabase.table("providers").update({"status": "removido"}).eq("id", prest["id"]).execute()
            resposta_whatsapp(t.PRESTADOR_NAO)
            return True
        if cmd == "prest_editar":
            supabase.table("providers").update({"status": "aguardando_perfil"}).eq("id", prest["id"]).execute()
            resposta_whatsapp(t.PRESTADOR_REFINAMENTO)
            return True
        if cmd == "prest_pausar":
            novo = "ativo" if prest.get("status") == "pausado" else "pausado"
            supabase.table("providers").update({"status": novo}).eq("id", prest["id"]).execute()
            resposta_whatsapp(
                "Cadastro *pausado* — você não receberá indicações por ora. Quando quiser "
                "voltar, é só clicar de novo. 💛" if novo == "pausado" else
                "Cadastro *reativado*! 💼 Você voltou a aparecer para quem busca o seu serviço.")
            return True
        # Texto livre durante o onboarding (nao e botao nem comando de menu):
        if not button_id and cmd not in MENU_TRIGGERS:
            if prest.get("status") == "aguardando_perfil":
                supabase.table("providers").update({
                    "descricao": (texto or "").strip(), "status": "ativo",
                }).eq("id", prest["id"]).execute()
                # Conta do banco (§7.8): sem recomendação, o perfil fica invisível
                # na busca — então a mensagem é honesta sobre isso (§5.1 / Mensagem 6).
                tem_reco = bool(supabase.table("recommendations").select("id")
                                .eq("provider_id", prest["id"]).limit(1).execute().data)
                resposta_whatsapp(t.PRESTADOR_PERFIL_OK if tem_reco
                                  else t.PRESTADOR_PERFIL_INVISIVEL)
                return True
            if prest.get("status") == "onboarding":
                servico_novo = (texto or "").strip().lower()
                supabase.table("providers").update({"servico": servico_novo}).eq("id", prest["id"]).execute()
                enviar_botoes_meta(t.PRESTADOR_ACOLHIDA.format(servico=servico_novo or "seu serviço"), [
                    {"id": "prest_aceito",  "label": "✅ Aceito e confirmo"},
                    {"id": "prest_ajustar", "label": "✏️ Ajustar serviço"},
                    {"id": "prest_nao",     "label": "⛔ Não desejo"},
                ])
                return True

    # -------- Antes do aceite --------
    if not consentiu:
        # Aceite como CLIENTE (botao "SIM" da boas-vindas ou do SABER MAIS, ou texto).
        if cmd == "consent_sim" or cmd in ACEITES_TXT:
            registrar_consentimento(membro["wa_id"])
            membro["consent"] = True
            if membro.get("invited_by"):
                _notificar_convidante(membro)
            enviar_menu_principal(t.CLIENTE_ATIVO)
            return True
        # SABER MAIS: explica com calma e abre os 3 caminhos por botao.
        if cmd == "consent_saber_mais" or "saber mais" in cmd or cmd == "voltar_saber":
            enviar_botoes_meta(t.SABER_MAIS.format(link=LINK_TERMOS), [
                {"id": "consent_sim", "label": "SIM, aceito"},
                {"id": "prof_quero",  "label": "Quero ser prof."},
                {"id": "adiar",       "label": "Deixa pra depois"},
            ])
            return True
        # Caminho profissional: escolher entre os dois perfis ou so o profissional.
        if cmd == "prof_quero":
            enviar_botoes_meta(t.PROF_ESCOLHA, [
                {"id": "prof_dual",    "label": "Cliente e prof."},
                {"id": "prof_so",      "label": "Só profissional"},
                {"id": "voltar_saber", "label": "Voltar"},
            ])
            return True
        # Perfil DUAL: precisa aceitar os DOIS termos (cliente + profissional).
        if cmd == "prof_dual":
            enviar_botoes_meta(
                t.PROF_DUAL.format(link_cli=LINK_TERMOS, link_prof=LINK_TERMOS_PROF), [
                    {"id": "prest_self_ok", "label": "Aceito os dois"},
                    {"id": "voltar_saber",  "label": "Voltar"},
                ])
            return True
        # So PROFISSIONAL: aceita apenas os termos do profissional.
        if cmd == "prof_so":
            enviar_botoes_meta(t.PROF_SO.format(link_prof=LINK_TERMOS_PROF), [
                {"id": "prest_self_ok", "label": "Aceito os termos"},
                {"id": "voltar_saber",  "label": "Voltar"},
            ])
            return True
        # Aceite dos termos do profissional (vale para dual e so-profissional).
        if cmd == "prest_self_ok":
            registrar_consentimento(membro["wa_id"])
            membro["consent"] = True
            if membro.get("invited_by"):
                _notificar_convidante(membro)
            _criar_perfil_profissional_self(membro)
            resposta_whatsapp(t.PRESTADOR_QUERO_SER_OK)
            return True
        # Deixar para depois.
        if cmd == "adiar":
            resposta_whatsapp(t.ADIAR)
            return True
        # Qualquer outra coisa antes do aceite: um lembrete curto, em texto.
        resposta_whatsapp("Para começar, responda *SIM* para aceitar os termos, ou digite "
                          "*SABER MAIS* se quiser entender melhor. 💛")
        return True

    # -------- Depois do aceite: navegacao --------
    # Quem tambem tem perfil profissional escolhe a visao (Cliente x Profissional).
    tem_perfil_prof = bool(prest and prest.get("status") in PRESTADOR_ATIVO_STATUS)
    if cmd in MENU_TRIGGERS:
        if tem_perfil_prof:
            enviar_escolha_perfil()
        else:
            enviar_menu_principal()
        return True
    if cmd == "perfil_cliente":
        enviar_menu_principal(); return True
    if cmd == "perfil_profissional":
        enviar_menu_prestador(); return True

    if cmd == "outras_opcoes":
        enviar_outras_opcoes(); return True
    if cmd == "dados":
        enviar_submenu_dados(); return True

    if cmd == "buscar":
        # Cliente novo (sem rede ainda): explica e oferece montar a rede ou rede geral.
        if contar("edges", membro["id"]) == 0:
            enviar_botoes_meta(t.BUSCAR_SEM_REDE, [
                {"id": "gerar_link",  "label": "🔗 Gerar meu link"},
                {"id": "buscar_geral", "label": "🔍 Buscar rede geral"},
            ])
        else:
            enviar_botoes_meta("Me conta o que você precisa e em qual bairro ou região de "
                               "São Paulo. 🙂\nEx.: *pediatra em Pinheiros*, *encanador em "
                               "Perdizes*.",
                               [{"id": "menu", "label": "🏠 Menu"}])
        return True
    if cmd == "buscar_geral":
        enviar_botoes_meta("Me conta o que você precisa e em qual bairro ou região de "
                           "São Paulo. 🙂\nEx.: *pediatra em Pinheiros*, *encanador em "
                           "Perdizes*.",
                           [{"id": "menu", "label": "🏠 Menu"}])
        return True
    if cmd == "gerar_link":
        gerar_e_enviar_link_convite(membro)
        enviar_menu_principal(); return True

    if cmd == "quero_ser_prof":
        if prest:   # ja tem perfil profissional
            resposta_whatsapp("Você já tem um perfil profissional aqui! 💼")
            enviar_menu_prestador()
            return True
        enviar_botoes_meta(t.PRESTADOR_QUERO_SER, [
            {"id": "prest_self", "label": "✅ Aceito e configuro"},
            {"id": "menu",       "label": "🔙 Voltar"},
        ])
        return True
    if cmd == "prest_self":
        if prest:
            enviar_menu_prestador()
            return True
        _criar_perfil_profissional_self(membro)
        resposta_whatsapp(t.PRESTADOR_QUERO_SER_OK)
        return True

    if cmd == "rede_indicar":
        _fluxo_set(membro, {"fluxo": "indicar", "passo": "contato"})
        enviar_botoes_meta(t.INDICAR_INICIO, [{"id": "menu", "label": "🏠 Menu"}])
        return True
    if cmd == "rede_convidar":
        enviar_botoes_meta(
            "Compartilhe pelo clipe 📎 o contato de quem você quer convidar — "
            "ou toque abaixo para gerar um link e divulgar para várias pessoas. 💛",
            [{"id": "gerar_link", "label": "🔗 Gerar meu link"},
             {"id": "menu",       "label": "🏠 Menu"}])
        return True

    if cmd == "dados_ver":
        resposta_whatsapp(_resumo_dados_texto(membro))
        enviar_menu_principal(); return True

    return False


def _processar_mensagem(wa_id, texto_recebido, nome_perfil, contatos_compartilhados, button_id=""):
    # contatos_compartilhados: [(e164, nome_card)] ou []
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

    # Convite: enquanto a pessoa nao consentiu, a Dorote.ia da as boas-vindas
    # citando quem a convidou (a conexao ja esta feita via invited_by). Isso vale
    # mesmo se ela voltar depois sem ter consentido na primeira vez.
    if not membro.get("consent") and membro.get("invited_by"):
        membro["convidado_por_nome"] = nome_do_convidante(membro["invited_by"])

    # PRESTADOR: chegou por um link de prestador -> inicia o onboarding de profissional
    # (tem prioridade sobre o fluxo de cliente). Vale para membro novo ou que ja existe.
    slug_prest = extrair_codigo_prestador(texto_recebido)
    if slug_prest is not None:
        iniciar_onboarding_prestador(membro, slug_prest)
        return

    # Limpa o codigo tecnico do convite do texto antes de mandar pra IA.
    texto_recebido = limpar_texto_convite(texto_recebido)

    # PRIMEIRO CONTATO (sem consent, sem historico e sem onboarding de prestador):
    # o cerebro manda a mensagem de boas-vindas fixa. Nao passa pelo roteador de menu.
    # (O 2o teste so faz a consulta extra quando a pessoa ainda nao consentiu.)
    primeiro_contato = (not membro.get("consent") and not membro.get("historico")
                        and not provider_do_membro(membro["id"]))

    # NAVEGACAO DETERMINISTICA: botoes/menus/comandos sao tratados aqui, sem IA,
    # pra ela nao inventar fluxos. So o texto livre de captura vai pra IA.
    if not primeiro_contato and rotear_menu(membro, texto_recebido, button_id, contatos_compartilhados):
        return

    # Se houver uma indicacao antiga ainda sem nota, a Dorote.ia pode puxar o
    # follow-up ("usou? como foi?") com naturalidade nesta conversa.
    membro["avaliacao_pendente"] = buscar_avaliacao_pendente(membro)

    # Flag: se a IA mandar botoes via ferramenta, nao envia texto duplicado.
    interativa_enviada = [False]

    usados = cerebro.conversar(
        membro,
        texto_recebido,
        contatos_compartilhados,
        executar_ferramenta=construir_executor(membro, interativa_enviada),
        enviar_texto=lambda texto: (None if interativa_enviada[0] else resposta_whatsapp(texto)),
        salvar_historico=lambda hist: salvar_historico(wa_id, hist),
    ) or set()

    # Depois de uma acao concluida pela IA, oferece o menu — pra nunca ficar solto.
    if membro.get("consent") and not interativa_enviada[0] and (usados & TOOLS_TERMINAIS):
        enviar_menu_principal()


@app.route("/termos", methods=["GET"])
def pagina_termos():
    """Termos de Uso e Politica de Privacidade (cliente)."""
    return Response(termos.pagina_termos(), mimetype="text/html")


@app.route("/termos/profissional", methods=["GET"])
def pagina_termos_profissional():
    """Termos de Uso do Profissional."""
    return Response(termos.pagina_termos_profissional(), mimetype="text/html")


@app.route("/c/<codigo>", methods=["GET"])
def redirecionar_link(codigo):
    try:
        achado = (supabase.table("short_links").select("url")
                  .eq("code", codigo).limit(1).execute().data)
        if not achado:
            # Rede de seguranca: tenta ignorando maiusc/minusc (codigos antigos).
            achado = (supabase.table("short_links").select("url")
                      .ilike("code", codigo).limit(1).execute().data)
        if achado:
            return Response(status=302, headers={"Location": achado[0]["url"]})
        print(f"[REDIRECT] code nao encontrado: {codigo!r}")
    except Exception:
        traceback.print_exc()
    return Response("Link nao encontrado.", status=404)


@app.route("/", methods=["GET"])
def home():
    return "A Dorote.ia esta viva! 🎉"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
