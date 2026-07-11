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


def _backfill_telefone_hash():
    """Backfill v19: preenche providers.telefone_hash nos registros antigos.

    Roda no boot (idempotente e barato: só pega quem ainda não tem hash). Tem que
    ser aqui no código porque o PEPPER vive só no ambiente — o SQL não consegue
    calcular o HMAC. Se a migração v19 ainda não rodou, falha em silêncio e tenta
    de novo no próximo boot."""
    try:
        rows = (supabase.table("providers").select("id, telefone")
                .is_("telefone_hash", "null").neq("telefone", "")
                .limit(500).execute().data) or []
        for r in rows:
            h = calcular_contact_hash(r["telefone"])
            supabase.table("providers").update(
                {"telefone_hash": h}).eq("id", r["id"]).execute()
        if rows:
            print(f"[V19] backfill de telefone_hash: {len(rows)} registro(s).")
    except Exception as erro:
        print(f"[V19] backfill adiado (migração v19 já rodou?): {erro}")


_backfill_telefone_hash()


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


def enviar_lista_meta(texto, botao, rows, to=None, phone_number_id=None):
    """Envia uma 'list message' (até 10 itens) via Cloud API — usada quando há mais
    de 3 opções, ou quando o documento pede lista (Outras opções / Minha conta).
    rows: [{"id": str, "title": str, "description": str (opcional)}]."""
    print(f"[RESP-LIST] {texto[:60]!r}")
    linhas = []
    for r in rows[:10]:
        linha = {"id": r["id"], "title": r["title"][:24]}
        if r.get("description"):
            linha["description"] = r["description"][:72]
        linhas.append(linha)
    _post_interativa({
        "type": "list",
        "body": {"text": texto},
        "action": {"button": botao[:20], "sections": [{"rows": linhas}]},
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
        "consent_version": termos.DATA_VIGENCIA,
        "historico": [],  # Limpa marcador pré-aceite (sem dados sensíveis); histórico post-aceite começa limpo.
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
    # LGPD §4.5: as indicações que a pessoa fez NÃO são apagadas — são anonimizadas
    # (perdem o nome de quem indicou e viram ⚪ rede geral). Desligamos o vínculo
    # ANTES de apagar o cadastro. (Pós-migração v12 a coluna aceita NULL; se a v12
    # ainda não rodou, este update falha e o cascade antigo apaga — por isso rode a v12.)
    try:
        supabase.table("recommendations").update(
            {"member_id": None}).eq("member_id", membro["id"]).execute()
    except Exception:
        traceback.print_exc()
    # LGPD: remover o RASTRO da pessoa nas redes de OUTROS. O cadastro dela (e a agenda
    # dela — edges com member_id dela) some no delete/cascade abaixo, mas o NÚMERO dela
    # (em hash) e o NOME dela ficam guardados na agenda de quem a adicionou. Apagamos
    # esses vestígios pela chave de hash do telefone dela.
    h = hash_de_membro(membro)
    if h:
        for tabela in ("edges", "pending_invites"):
            try:
                supabase.table(tabela).delete().eq("contact_hash", h).execute()
            except Exception:
                traceback.print_exc()
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
    mensagem = "Oi! Quero fazer parte da Central de indicações de confiança Dorote.ia 💛"
    if codigo:
        mensagem += f" (convite: {codigo})"
    return f"https://wa.me/{numero_bot}?text={quote(mensagem)}"


def extrair_codigo_convite(texto):
    achado = re.search(r"convite:\s*([A-Za-z0-9]{6})", texto)
    return achado.group(1).upper() if achado else None


def montar_link_recomendar(numero_bot, codigo):
    """Link pessoal do PROFISSIONAL para pedir recomendação a quem ele já atendeu.
    Quem entra por ele está RECOMENDANDO o profissional (regra do titular: entrar já
    é o consentimento de quem recomenda; o profissional confirma que conhece)."""
    mensagem = f"Oi! Vim recomendar um trabalho na Dorote.ia 💛 (recomendar: {codigo})"
    return f"https://wa.me/{numero_bot}?text={quote(mensagem)}"


def extrair_codigo_recomendar(texto):
    achado = re.search(r"recomendar:\s*([A-Za-z0-9]{6})", texto or "")
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


def registrar_convite_pendente(membro, numero_e164, nome=None):
    codigo = calcular_contact_hash(numero_e164)
    nome = (nome or "").strip() or None
    existe = (supabase.table("pending_invites").select("id")
              .eq("inviter_id", membro["id"]).eq("contact_hash", codigo).limit(1).execute().data)
    if not existe:
        dados = {"inviter_id": membro["id"], "contact_hash": codigo}
        if nome:
            dados["nome"] = nome
        supabase.table("pending_invites").insert(dados).execute()
    elif nome:
        supabase.table("pending_invites").update({"nome": nome}).eq("id", existe[0]["id"]).execute()


def _salvar_nomes_contatos(membro, contatos):
    """Backfill do NOME do contato (do cartão) na agenda da pessoa — para ela ver a
    própria rede. O número continua só em hash. Roda depois que as ferramentas já
    criaram os edges/convites (casamos pelo hash do número)."""
    for numero, nome in (contatos or []):
        nome = (nome or "").strip()
        if not numero or not nome:
            continue
        try:
            h = calcular_contact_hash(numero)
            supabase.table("edges").update({"nome": nome}).eq(
                "member_id", membro["id"]).eq("contact_hash", h).execute()
            supabase.table("pending_invites").update({"nome": nome}).eq(
                "inviter_id", membro["id"]).eq("contact_hash", h).execute()
        except Exception:
            traceback.print_exc()


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
    """🟢 só com CONEXÃO MÚTUA VALIDADA (os dois confirmaram que se conhecem — §6).
    Convite/agenda sozinhos NÃO bastam: isso é a rede pendente (🟡), tratada à parte."""
    return conexao_validada_entre(pedidor["id"], recomendador["id"])


# k-anonimato: o nível 🟡 (rede pendente, anônimo) só aparece se a pessoa tiver ao
# menos esta quantidade de contatos na rede — senão dá pra adivinhar quem indicou.
K_ANONIMATO = 5


def _qtd_rede(pedidor):
    """Quantos contatos a pessoa tem na rede (tamanho da agenda de confiança)."""
    try:
        return len((supabase.table("edges").select("id")
                    .eq("member_id", pedidor["id"]).execute().data) or [])
    except Exception:
        traceback.print_exc()
        return 0


def _na_rede_pendente(pedidor, recomendador):
    """True se a pessoa ADICIONOU quem indicou (agenda) ou há conexão PENDENTE entre
    os dois — ou seja, é da rede dela, mas a conexão ainda não foi confirmada (🟡)."""
    h = hash_de_membro(recomendador)
    try:
        if h and (supabase.table("edges").select("id").eq("member_id", pedidor["id"])
                  .eq("contact_hash", h).limit(1).execute().data):
            return True
        for a, b in ((pedidor["id"], recomendador["id"]), (recomendador["id"], pedidor["id"])):
            if (supabase.table("conexoes").select("id").eq("status", "pendente")
                    .eq("member_a", a).eq("member_b", b).limit(1).execute().data):
                return True
    except Exception:
        traceback.print_exc()
    return False


def executar_busca(pedidor, servico, bairro, cidade):
    """Roda a busca e devolve (com_nome, rede_pendente, sem_nome) — os 3 níveis (§6):
    🟢 com_nome      [(prestador, [nomes])] -> conexão mútua validada (mostra o nome).
    🟡 rede_pendente [(prestador, n)]       -> da rede dela, mas conexão não confirmada
                                              (anônimo; só com k-anonimato ≥ K_ANONIMATO).
    ⚪ sem_nome      [(prestador, n)]        -> rede geral / anonimizada (anônimo).

    `n` = quantas pessoas indicaram aquele profissional (prova social). Dentro de
    cada nível, ordena por `n` (mais indicações primeiro) e, no empate, pela nota.
    """
    query = supabase.table("recommendations").select("*").ilike("servico", servico)
    if bairro:
        query = query.ilike("bairro", bairro)
    if cidade:
        query = query.ilike("cidade", cidade)
    recs = query.execute().data

    por_provider_rede = {}      # 🟢 pid -> {"prestador", "quem_indicou": [nomes]}
    por_provider_pendente = {}  # 🟡 pid -> {"prestador", "quem": set(member_id)}
    por_provider_fora = {}      # ⚪ pid -> {"prestador", "quem": set(member_id|rec_id)}

    for rec in recs:
        prestador = buscar_provider(rec["provider_id"])
        if prestador is None or prestador.get("status") != "ativo":
            continue
        pid = prestador["id"]

        # Indicação ANONIMIZADA (quem indicou saiu — member_id NULL): ⚪ rede geral.
        if rec.get("member_id") is None:
            d = por_provider_fora.setdefault(pid, {"prestador": prestador, "quem": set()})
            d["quem"].add(rec.get("id") or id(rec))
            continue

        recomendador = buscar_membro_por_id(rec["member_id"])
        if recomendador is None or not recomendador.get("consent"):
            continue
        # Bloqueio: indicação de quem foi bloqueado (ou que bloqueou) não aparece.
        if esta_bloqueado(pedidor["id"], recomendador["id"]):
            continue

        eh_propria = recomendador["id"] == pedidor["id"]
        if eh_propria or conexao_validada_entre(pedidor["id"], recomendador["id"]):
            # A própria indicação da pessoa, ou de uma conexão mútua validada → 🟢 com nome.
            nome_rec = ("você" if eh_propria
                        else (recomendador.get("nome_perfil") or "").strip() or "alguem que voce conhece")
            d = por_provider_rede.setdefault(pid, {"prestador": prestador, "quem_indicou": []})
            if nome_rec not in d["quem_indicou"]:
                d["quem_indicou"].append(nome_rec)
        elif _na_rede_pendente(pedidor, recomendador):
            d = por_provider_pendente.setdefault(pid, {"prestador": prestador, "quem": set()})
            d["quem"].add(recomendador["id"])
        else:
            d = por_provider_fora.setdefault(pid, {"prestador": prestador, "quem": set()})
            d["quem"].add(recomendador["id"])

    # k-anonimato: sem rede grande o bastante, 🟡 vira ⚪ (anônimo geral).
    if _qtd_rede(pedidor) < K_ANONIMATO:
        for pid, d in por_provider_pendente.items():
            f = por_provider_fora.setdefault(pid, {"prestador": d["prestador"], "quem": set()})
            f["quem"] |= d["quem"]
        por_provider_pendente = {}

    com_nome = [(d["prestador"], d["quem_indicou"]) for d in por_provider_rede.values()]
    pendente = [(d["prestador"], len(d["quem"])) for pid, d in por_provider_pendente.items()
                if pid not in por_provider_rede]
    sem_nome = [(d["prestador"], len(d["quem"])) for pid, d in por_provider_fora.items()
                if pid not in por_provider_rede and pid not in por_provider_pendente]

    # Ordena por prova social (nº de indicações) e, no empate, pela nota.
    com_nome.sort(key=lambda par: (len(par[1]), _relevancia(par[0])), reverse=True)
    pendente.sort(key=lambda par: (par[1], _relevancia(par[0])), reverse=True)
    sem_nome.sort(key=lambda par: (par[1], _relevancia(par[0])), reverse=True)
    return com_nome, pendente, sem_nome


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


def _sinais_anonimos(pedidor, servico, bairro, limite=3):
    """Sinais anônimos de indicação PENDENTE (§6b): profissionais que alguém da rede
    da pessoa indicou, mas que ainda NÃO entraram (status 'convidado'). Sem nome e sem
    telefone — o contato só libera quando a pessoa indicada entra e aceita. Respeita
    k-anonimato. Devolve [{servico, bairro}]."""
    if _qtd_rede(pedidor) < K_ANONIMATO:
        return []
    try:
        q = (supabase.table("providers").select("*")
             .eq("status", "convidado").ilike("servico", servico))
        if bairro:
            q = q.ilike("bairro", bairro)
        provs = q.execute().data or []
    except Exception:
        traceback.print_exc()
        return []

    sinais, vistos = [], set()
    for p in provs:
        # LGPD: o convidado nao tem numero cru no banco — casamos pelo HASH.
        # (Fallback pro cru so em registros antigos, pre-v19.)
        tel = (p.get("telefone") or "").strip()
        h = (p.get("telefone_hash") or "").strip() or (calcular_contact_hash(tel) if tel else "")
        if not h or p["id"] in vistos:
            continue
        try:
            inviters = (supabase.table("pending_invites").select("inviter_id")
                        .eq("contact_hash", h).execute().data) or []
        except Exception:
            traceback.print_exc()
            continue
        inviter_ids = {r["inviter_id"] for r in inviters if r.get("inviter_id")}
        inviter_ids.discard(pedidor["id"])  # nao sinaliza a propria indicacao
        # Sinal só vale se quem indicou for da rede da pessoa que busca.
        da_rede = False
        for iid in inviter_ids:
            rec = buscar_membro_por_id(iid)
            if rec and _na_rede_pendente(pedidor, rec):
                da_rede = True
                break
        if da_rede:
            vistos.add(p["id"])
            sinais.append({"servico": p.get("servico") or servico,
                           "bairro": p.get("bairro") or bairro or ""})
        if len(sinais) >= limite:
            break
    return sinais


def _texto_sinais(sinais):
    """Instrução para a IA mencionar os sinais anônimos ao final (sem nome/telefone)."""
    if not sinais:
        return ""
    linhas = []
    for s in sinais:
        reg = f" na regiao de {s['bairro']}" if s.get("bairro") else ""
        linhas.append(f"- alguem da sua rede indicou um(a) {s['servico']}{reg}, "
                      "que ainda nao entrou na Dorote.ia")
    return ("\n\nSINAIS ANONIMOS DE INDICACAO PENDENTE — mencione ao final, SEM nome e SEM "
            "telefone (o contato so libera quando essa pessoa entrar e aceitar). Convide com "
            "leveza a pessoa a chamar quem indicou pra essa pessoa entrar:\n" + "\n".join(linhas))


# Quantos itens no máximo mostrar numa tela de resultado (cabe no corpo do WhatsApp).
MAX_ITENS_RESULTADO = 6


def _selo_curto(p):
    """Nota resumida para exibição (⭐ x/5) ou '' se ainda não há avaliação."""
    qtd = p.get("qtd_avaliacoes") or 0
    if qtd:
        return f"  ⭐ {p.get('nota_media')}/5"
    return ""


def _prova(n):
    return f" ({n} pessoas)" if n and n > 1 else ""


def _texto_iscas(sinais):
    """Iscas (indicação pendente, sem contato) — já filtradas por k-anonimato."""
    if not sinais:
        return ""
    linhas = []
    for s in sinais:
        reg = f" na região de {s['bairro']}" if s.get("bairro") else ""
        linhas.append(f"🔒 Alguém da sua rede indicou um(a) {s['servico']}{reg} — o contato "
                      "libera quando essa pessoa entrar na Dorote.ia.")
    return "\n\n" + "\n".join(linhas)


def _linhas_resultado(com_nome, pendente, sem_nome):
    """Monta as linhas de item, na ordem de confiança (🟢, 🟡, ⚪), com contato.
    Devolve (linhas, sobra) onde sobra = quantos ficaram de fora do teto."""
    itens = []
    for p, quem in com_nome:
        itens.append(f"🟢 *{p['nome']}* — indicado por {_formatar_indicadores(quem)}"
                     f"{_prova(len(quem))}{_selo_curto(p)}\n📞 {p['telefone']}")
    for p, n in pendente:
        itens.append(f"🟡 *{p['nome']}* — alguém da sua rede indica{_prova(n)}"
                     f"{_selo_curto(p)}\n📞 {p['telefone']}")
    for p, n in sem_nome:
        itens.append(f"⚪ *{p['nome']}* — indicado pela rede Dorote.ia{_prova(n)}"
                     f"{_selo_curto(p)}\n📞 {p['telefone']}")
    sobra = max(0, len(itens) - MAX_ITENS_RESULTADO)
    return itens[:MAX_ITENS_RESULTADO], sobra


def _registrar_mostrados(membro, servico, bairro, cidade, com_nome, pendente, sem_nome):
    for p, _ in com_nome:
        registrar_indicacao_recebida(membro["id"], p, servico, bairro, cidade)
    for p, _ in pendente:
        registrar_indicacao_recebida(membro["id"], p, servico, bairro, cidade)
    for p, _ in sem_nome:
        registrar_indicacao_recebida(membro["id"], p, servico, bairro, cidade)


def _executar_e_enviar_busca(membro, servico, bairro, cidade):
    """Roda a busca e ENVIA a tela de resultado pelo código (com botões). O telefone
    do profissional nunca passa pela IA. Cobre RES_OK, RES_GERAL e RES_VAZIO (§6)."""
    com_nome, pendente, sem_nome = executar_busca(membro, servico, bairro, cidade)
    sinais = _sinais_anonimos(membro, servico, bairro)
    local = ", ".join(p for p in [bairro, cidade] if p) or "São Paulo"

    # RES_OK — há indicações da rede (🟢 e/ou 🟡). Pode listar ⚪ junto.
    if com_nome or pendente:
        registrar_busca(servico, bairro, cidade, "verde" if com_nome else "amarelo_rede", membro["id"])
        _registrar_mostrados(membro, servico, bairro, cidade, com_nome, pendente, sem_nome)
        linhas, sobra = _linhas_resultado(com_nome, pendente, sem_nome)
        corpo = f"🔍 O que encontrei para *{servico}* em {local}:\n\n" + "\n\n".join(linhas)
        if sobra:
            corpo += f"\n\n_(e mais {sobra} — refine o bairro para ver os melhores.)_"
        corpo += _texto_iscas(sinais)
        enviar_botoes_meta(corpo, [
            {"id": "buscar",       "label": "🔍 Buscar outro"},
            {"id": "rede_indicar", "label": "💛 Indicar"},
            {"id": "menu",         "label": "🏠 Menu"}])
        return

    # Só ⚪ (rede geral / anonimizado).
    if sem_nome:
        registrar_busca(servico, bairro, cidade, "amarelo", membro["id"])
        _registrar_mostrados(membro, servico, bairro, cidade, [], [], sem_nome)
        linhas, sobra = _linhas_resultado([], [], sem_nome)
        corpo = f"🔍 O que encontrei para *{servico}* em {local}:\n\n" + "\n\n".join(linhas)
        if sobra:
            corpo += f"\n\n_(e mais {sobra} — refine o bairro para ver os melhores.)_"
        corpo += _texto_iscas(sinais)
        # RES_GERAL — rede pequena (< k): enquadra como rede geral e convida a crescer.
        if _qtd_rede(membro) < K_ANONIMATO:
            corpo += t.BUSCA_REDE_PEQUENA
            enviar_botoes_meta(corpo, [
                {"id": "rede_convidar", "label": "🤝 Convidar"},
                {"id": "buscar",        "label": "🔍 Buscar outro"},
                {"id": "menu",          "label": "🏠 Menu"}])
        else:
            enviar_botoes_meta(corpo, [
                {"id": "buscar",       "label": "🔍 Buscar outro"},
                {"id": "rede_indicar", "label": "💛 Indicar"},
                {"id": "menu",         "label": "🏠 Menu"}])
        return

    # RES_VAZIO — nada na rede. NUNCA pedir a quem busca que ela mesma indique.
    registrar_busca(servico, bairro, cidade, "vermelho", membro["id"])
    _enviar_sem_resultado(membro, servico, bool(sinais))


def _perguntar_regiao_busca(membro, servico):
    """BUSCA_FALTA (§): veio só o serviço → pergunta a região por botões (a IA não
    conduz). Guarda o serviço no estado para o próximo passo ser determinístico."""
    _fluxo_set(membro, {"fluxo": "busca", "servico": servico})
    enviar_botoes_meta(t.BUSCA_FALTA_REGIAO.format(servico=servico), [
        {"id": "busca_cidade_toda", "label": "🏙️ Toda a cidade"},
        {"id": "busca_bairro",      "label": "📍 Escrever bairro"},
        {"id": "menu",              "label": "🏠 Menu"}])


def _ferr_buscar(membro, entrada, interativa_enviada=None):
    """A IA só EXTRAI {servico, região}. A partir daqui, quem conduz é o código:
    pergunta a região que falta (por botões) e envia o resultado pronto (com contato
    e botões). O telefone do profissional nunca chega ao modelo."""
    servico = (entrada.get("servico") or "").strip().lower()
    bairro  = (entrada.get("bairro")  or "").strip()
    if not servico:
        return "Faltou o servico. Pergunte O QUE a pessoa precisa (nunca 'qual cidade')."
    if interativa_enviada is None:
        interativa_enviada = [False]
    # Sem região → pergunta com botões (Toda a cidade / Escrever bairro).
    if not bairro:
        _perguntar_regiao_busca(membro, servico)
        interativa_enviada[0] = True
        return "Perguntei a regiao por botoes. NAO escreva mais nada."
    _executar_e_enviar_busca(membro, servico, bairro, "São Paulo")
    interativa_enviada[0] = True
    return "Resultado da busca ja enviado por botoes. NAO escreva mais nada."


def _enviar_sem_resultado(membro, servico, tem_sinal):
    """Mensagem determinística de 'sem indicação': oferece perguntar a amigos ou
    convidar a rede. Guarda o serviço no estado para o fluxo de 'pedir a amigos'."""
    _fluxo_set(membro, {"fluxo": "sem_resultado", "servico": servico})
    texto = t.BUSCA_SEM_RESULTADO.format(servico=servico)
    if tem_sinal:
        texto += ("\n\n💡 Alguém da sua rede já indicou um *" + servico + "* que ainda não "
                  "entrou na Dorote.ia — convide a sua rede para destravar esse contato!")
    enviar_botoes_meta(texto, [
        {"id": "pedir_amigos", "label": "👋 Perguntar a amigos"},
        {"id": "gerar_link",   "label": "➕ Convidar rede"},
        {"id": "menu",         "label": "🏠 Menu"}])


def _conexoes_confirmadas(membro):
    """Amigos com conexão VALIDADA (confirmada pelos dois): [(member_id, nome)]."""
    out, vistos = [], set()
    try:
        cons = ((supabase.table("conexoes").select("*").eq("member_a", membro["id"])
                 .eq("status", "validada").execute().data or [])
                + (supabase.table("conexoes").select("*").eq("member_b", membro["id"])
                   .eq("status", "validada").execute().data or []))
    except Exception:
        traceback.print_exc(); cons = []
    for c in cons:
        outro = _outro_lado(c, membro)
        if outro and outro["id"] not in vistos and not esta_bloqueado(membro["id"], outro["id"]):
            vistos.add(outro["id"])
            out.append((outro["id"], _nome_curto(outro)))
    return out


def _pedir_amigos_lista(membro):
    """Mostra os amigos confirmados para a pessoa escolher a quem perguntar."""
    amigos = _conexoes_confirmadas(membro)
    if not amigos:
        enviar_botoes_meta(t.PEDIR_AMIGOS_SEM_REDE, [
            {"id": "gerar_link", "label": "🔗 Gerar meu link"},
            {"id": "menu",       "label": "🏠 Menu"}])
        return
    rows = [{"id": f"ask:{mid}", "title": (nome or "Amigo")[:24],
             "description": "Perguntar para esta pessoa"} for mid, nome in amigos[:10]]
    enviar_lista_meta(t.PEDIR_AMIGOS_LISTA, "Escolher", rows)


def _enviar_ask_amigo(membro, friend_id):
    """Manda (pelo chat da Dorote.ia) a pergunta de indicação para o amigo escolhido,
    como se viesse da pessoa que está procurando."""
    fl = _fluxo_get(membro)
    servico = fl.get("servico") if fl.get("fluxo") == "sem_resultado" else ""
    servico = servico or "um serviço"
    amigo = buscar_membro_por_id(friend_id)
    if not amigo or esta_bloqueado(membro["id"], friend_id):
        resposta_whatsapp("Não consegui falar com essa pessoa. 💛")
        enviar_menu_principal(membro)
        return
    pn = g.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
    # Pergunta entregue ao amigo (chega na hora se ele falou com a bot nas últimas 24h;
    # senão, aparece quando ele reabrir o chat).
    enviar_botoes_meta(
        t.ASK_PARA_AMIGO.format(quem=_nome_curto(membro), servico=servico),
        [{"id": "rede_indicar", "label": "💛 Indicar alguém"},
         {"id": "menu",         "label": "Agora não"}],
        to=amigo["wa_id"], phone_number_id=pn)
    # Confirmação para quem pediu, com opção de perguntar a mais alguém.
    enviar_botoes_meta(t.ASK_ENVIADO.format(nome=_nome_curto(amigo)), [
        {"id": "pedir_amigos", "label": "👋 Perguntar a outro"},
        {"id": "menu",         "label": "🏠 Menu"}])


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
    interativa_enviada = [False]

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
        aviso_extra = (f"\n\n(Os outros {sobra} contato(s) tambem ja estao atrelados — "
                       "mandar esses contatos de novo gera os links.)")

    # Envia a resposta com BOTOES, nao somente texto.
    texto = (
        f"Pronto! 💛 Links prontos para {len(numeros)} convite(s) — toque em cada link "
        "e envie a quem você confia:\n\n"
        + "\n".join(linhas) + aviso_extra
    )
    resposta_whatsapp(texto)
    enviar_botoes_meta("O que você deseja fazer agora?", [
        {"id": "rede_convidar", "label": "🤝 Convidar mais"},
        {"id": "menu",          "label": "🏠 Menu"}])
    interativa_enviada[0] = True

    # Não retorna texto — a resposta já foi enviada com botoes.
    return ""


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


def _gravar_avaliacao(membro, ind, prestador, nota):
    """Grava a nota (1 a 5) que a PESSOA escolheu nos botoes — fluxo deterministico.
    Upsert: uma avaliacao por pessoa por prestador (reavaliar atualiza)."""
    agora = datetime.now(timezone.utc).isoformat()
    try:
        ja = (supabase.table("avaliacoes").select("id")
              .eq("member_id", membro["id"]).eq("provider_id", prestador["id"])
              .limit(1).execute().data)
        if ja:
            supabase.table("avaliacoes").update({
                "nota": nota, "updated_at": agora,
            }).eq("id", ja[0]["id"]).execute()
        else:
            supabase.table("avaliacoes").insert({
                "member_id": membro["id"], "provider_id": prestador["id"], "nota": nota,
            }).execute()
        supabase.table("indicacoes_recebidas").update({
            "status": "avaliada", "updated_at": agora,
        }).eq("id", ind["id"]).execute()
        _recalcular_nota_provider(prestador["id"])
    except Exception:
        traceback.print_exc()


def _ferr_enviar_botoes(entrada, interativa_enviada):
    texto = (entrada.get("texto") or "").strip()
    botoes = entrada.get("botoes") or []
    if not texto or not botoes:
        return "Faltou texto ou botoes. Tente de novo."
    enviar_botoes_meta(texto, botoes)
    interativa_enviada[0] = True
    return "ok - mensagem com botoes enviada. Sua resposta de texto final deve ser VAZIA."


def _confirmar_lado_de(con, membro_id):
    """Marca como confirmado o lado do membro dado, SEM pedir resposta a ele.

    Regra do titular: quem ENTRA por um convite pessoal já está consentindo o vínculo
    ao entrar — então esse lado é confirmado automaticamente. Só o outro lado (quem
    convidou/indicou) precisa dizer 'sim, conheço' para a conexão virar 🟢."""
    lado = "a_confirmou" if con.get("member_a") == membro_id else "b_confirmou"
    try:
        supabase.table("conexoes").update({lado: True}).eq("id", con["id"]).execute()
    except Exception:
        traceback.print_exc()
    con[lado] = True


def _abrir_conexao_cliente(novo_membro):
    """Quando alguém entra por um convite de CLIENTE: abre a conexão mútua com quem
    convidou (§6/§7.4). Regra do titular: quem ENTROU pelo convite já consentiu o
    vínculo ao entrar — esse lado é confirmado automaticamente. Só quem CONVIDOU
    recebe a pergunta 'vocês se conhecem?'. Ao confirmar, a conexão vira 🟢.

    §7.5: Não enviamos proativo — se estiver fora da janela de 24h, Meta rejeita.
    Em vez disso, guardamos como pendente e exibimos quando o convidante reabrir."""
    try:
        convidante = buscar_membro_por_id(novo_membro.get("invited_by"))
        if not convidante or not convidante.get("consent"):
            return
        con = criar_conexao_pendente(convidante["id"], novo_membro["id"], "cliente")
        if not con:
            return
        # Quem entrou (member_b) já confirmou ao entrar pelo convite pessoal.
        _confirmar_lado_de(con, novo_membro["id"])
        # Confirmação fica pendente; será exibida quando o convidante reabrir o chat.
    except Exception:
        traceback.print_exc()


def _conectar_por_link_cliente(membro, texto):
    """CORE (correção de conexão). Quem JÁ é membro e JÁ consentiu, ao abrir um link
    de convite de cliente, NÃO passa de novo pelo aceite — então o vínculo com quem
    convidou nunca era criado (bug: a conexão só nascia na criação/consentimento).

    Aqui detectamos o convite — pelo código no texto OU por um convite pendente ligado
    ao número — e abrimos a conexão mútua na hora, perguntando aos dois se se conhecem.
    Idempotente: se já existe qualquer conexão entre os dois (em qualquer status ou
    direção), não recria nem repergunta. Retorna True se abriu a conexão (perguntou)."""
    inviter_id = None
    codigo = extrair_codigo_convite(texto)
    if codigo:
        conv = membro_por_codigo(codigo)
        if conv:
            inviter_id = conv["id"]
    if inviter_id is None:
        numero = normalizar_e164(membro.get("wa_id") or "")
        if numero:
            try:
                h = calcular_contact_hash(numero)
                row = (supabase.table("pending_invites").select("inviter_id")
                       .eq("contact_hash", h).limit(1).execute().data)
                if row:
                    inviter_id = row[0]["inviter_id"]
            except Exception:
                traceback.print_exc()
    if not inviter_id or inviter_id == membro["id"]:
        return False
    inviter = buscar_membro_por_id(inviter_id)
    if not inviter or not inviter.get("consent") or esta_bloqueado(membro["id"], inviter_id):
        return False
    # Já existe conexão (qualquer status/direção)? Consome o convite pendente e sai —
    # não recria nem repergunta.
    for a, b in ((inviter_id, membro["id"]), (membro["id"], inviter_id)):
        try:
            if (supabase.table("conexoes").select("id")
                    .eq("member_a", a).eq("member_b", b).limit(1).execute().data):
                aplicar_convite_pendente(membro["wa_id"])
                return False
        except Exception:
            traceback.print_exc()
    # Abre a conexão mútua reusando o fluxo padrão (cria pendente + pergunta aos dois).
    if not membro.get("invited_by"):
        try:
            supabase.table("members").update(
                {"invited_by": inviter_id}).eq("id", membro["id"]).execute()
        except Exception:
            traceback.print_exc()
    membro["invited_by"] = inviter_id
    aplicar_convite_pendente(membro["wa_id"])   # consome o convite pendente pelo número
    _abrir_conexao_cliente(membro)
    # Quem entrou não é perguntado de novo (entrar já foi o consentimento do vínculo);
    # damos um retorno claro + navegação.
    resposta_whatsapp(t.CONEXAO_ENTROU_LIGADO.format(nome=_nome_curto(inviter)))
    enviar_menu_do_perfil_ativo(membro)
    return True


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
                _abrir_conexao_cliente(membro)
            return (
                "Consentimento registrado. Responda em NO MAXIMO 3 linhas: "
                "uma frase de boas-vindas calorosa (cite quem convidou se souber), "
                "convite para compartilhar contatos pelo clipe 📎, "
                "e pergunte se ja precisa de alguma indicacao agora. Nada mais."
            )
        if nome == "buscar_servico":
            return _ferr_buscar(membro, entrada, interativa_enviada)
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

            # Pergunta por BOTOES (avaliação determinística, stateless). Dentro das
            # 24h chega direto; fora delas só entra quando a pessoa reabre o chat
            # (o gatilho de reabertura faz a mesma pergunta) — sem Template.
            _enviar_pergunta_avaliacao(membro, ind, prestador,
                                       to=membro["wa_id"],
                                       phone_number_id=WHATSAPP_PHONE_NUMBER_ID)

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

# --- Perfil ativo e troca (quem tem Cliente + Profissional) ------------------
def tem_perfil_profissional(membro):
    prest = provider_do_membro(membro["id"])
    return bool(prest and prest.get("status") in PRESTADOR_ATIVO_STATUS)


def perfil_ativo(membro):
    """Perfil em uso agora: 'cliente' ou 'profissional'. Padrão cliente. Só devolve
    'profissional' se a pessoa realmente tiver um perfil profissional ativo."""
    valor = (membro.get("perfil_ativo") or "cliente").strip().lower()
    if valor == "profissional" and tem_perfil_profissional(membro):
        return "profissional"
    return "cliente"


def set_perfil_ativo(membro, valor):
    valor = "profissional" if valor == "profissional" else "cliente"
    membro["perfil_ativo"] = valor
    try:
        supabase.table("members").update({"perfil_ativo": valor}).eq("id", membro["id"]).execute()
    except Exception:
        traceback.print_exc()


def _label_perfil(p):
    return "Profissional 💼" if p == "profissional" else "Cliente 🔍"


def _talvez_avisar_troca(membro):
    """Avisa UMA única vez que a pessoa pode escrever TROCAR (quando vira dual)."""
    if not tem_perfil_profissional(membro) or membro.get("avisou_troca"):
        return
    resposta_whatsapp(t.TROCAR_AVISO)
    membro["avisou_troca"] = True
    try:
        supabase.table("members").update({"avisou_troca": True}).eq("id", membro["id"]).execute()
    except Exception:
        traceback.print_exc()


def enviar_menu_do_perfil_ativo(membro, texto=None):
    """Abre o menu do perfil ATIVO (não pergunta 'qual perfil?' toda vez)."""
    _talvez_avisar_troca(membro)
    if perfil_ativo(membro) == "profissional":
        enviar_menu_prestador()
    else:
        enviar_menu_principal(membro, texto)


def enviar_menu_principal(membro, texto=None):
    """Menu do cliente como LIST MESSAGE (expande no WhatsApp) — assim o *Buscar*
    fica no topo e fácil, sem o limite de 3 botões."""
    rows = [
        {"id": "buscar",        "title": "🔍 Buscar uma indicação",
         "description": "Achar um profissional de confiança"},
        {"id": "rede_indicar",  "title": "💛 Indicar profissional",
         "description": "Recomendar alguém bom que você conhece"},
        {"id": "rede_convidar", "title": "🤝 Convidar rede",
         "description": "Trazer gente de sua confiança"},
    ]
    if tem_perfil_profissional(membro):
        rows.append({"id": "trocar", "title": "🔁 Trocar de perfil",
                     "description": "Ir para o seu perfil profissional"})
    else:
        rows.append({"id": "quero_ser_prof", "title": "💼 Ser profissional",
                     "description": "Criar o seu perfil para ser recomendado"})
    rows.append({"id": "dados", "title": "⚙️ Minha conta",
                 "description": "Sua rede e indicações que você fez"})
    enviar_lista_meta(texto or "O que você deseja fazer? 💛", "Ver opções", rows)


def enviar_outras_opcoes(membro):
    """Outras opções do PERFIL ATIVO. Cliente vê Buscar/Ser profissional|Trocar/Minha
    conta; Profissional vê Editar/Pausar/Minha conta/Trocar."""
    dual = tem_perfil_profissional(membro)
    if perfil_ativo(membro) == "profissional":
        rows = [
            {"id": "prof_pedir_rec", "title": "📣 Pedir recomendação",
             "description": "Convite para clientes que você já atendeu"},
            {"id": "prest_editar", "title": "✏️ Editar perfil",
             "description": "Atualizar o seu serviço e dados"},
            {"id": "prest_pausar", "title": "⏸️ Pausar / Ativar",
             "description": "Aparecer ou não nas buscas"},
            {"id": "dados",        "title": "⚙️ Minha conta",
             "description": "Seu perfil e quem te recomendou"},
            {"id": "trocar",       "title": "🔁 Trocar de perfil",
             "description": "Ir para o perfil de cliente"},
        ]
        enviar_lista_meta("Outras opções 💼", "Ver opções", rows)
        return
    rows = [{"id": "buscar", "title": "🔍 Buscar",
             "description": "Achar um profissional de confiança"}]
    if dual:
        rows.append({"id": "trocar", "title": "🔁 Trocar de perfil",
                     "description": "Ir para o perfil profissional"})
    else:
        rows.append({"id": "quero_ser_prof", "title": "💼 Ser profissional",
                     "description": "Criar o seu perfil para ser recomendado"})
    rows.append({"id": "dados", "title": "⚙️ Minha conta",
                 "description": "Sua rede e indicações que você fez"})
    enviar_lista_meta("Outras opções 💛", "Ver opções", rows)


_BOTOES_CONTA = [{"id": "dados", "label": "⚙️ Minha conta"},
                 {"id": "menu",  "label": "🏠 Menu"}]


def enviar_submenu_dados(membro):
    """Minha conta do PERFIL ATIVO (cada perfil tem a sua agenda). SAIR sempre visível."""
    if perfil_ativo(membro) == "profissional":
        enviar_lista_meta("Minha conta 💼", "Abrir", [
            {"id": "dados_meu_perfil", "title": "💼 Meu perfil",
             "description": "Situação na busca e nº de recomendações"},
            {"id": "dados_recomend",   "title": "⭐ Quem me recomendou",
             "description": "Quem registrou recomendações sobre você"},
            {"id": "dados_apagar",     "title": "🗑️ Sair / apagar",
             "description": "Encerrar a sua conta"},
            {"id": "menu",             "title": "🏠 Menu",
             "description": "Voltar ao início"},
        ])
        return
    enviar_lista_meta("Minha conta ⚙️", "Abrir", [
        {"id": "dados_rede",       "title": "🤝 Minha rede",
         "description": "Suas conexões e o status de cada uma"},
        {"id": "dados_indicacoes", "title": "📤 Indicações que fiz",
         "description": "Profissionais que você indicou"},
        {"id": "gerenciar_rede",   "title": "🚫 Bloquear e gerenciar",
         "description": "Bloquear, remover ou desbloquear"},
        {"id": "dados_apagar",     "title": "🗑️ Sair / apagar",
         "description": "Encerrar a sua conta"},
        {"id": "menu",             "title": "🏠 Menu",
         "description": "Voltar ao início"},
    ])


def _ver_minha_rede(membro):
    confirmadas, aguardando, aguardando_ids = [], [], []
    try:
        cons = ((supabase.table("conexoes").select("*").eq("member_a", membro["id"]).execute().data or [])
                + (supabase.table("conexoes").select("*").eq("member_b", membro["id"]).execute().data or []))
    except Exception:
        traceback.print_exc(); cons = []
    for c in cons:
        outro = _outro_lado(c, membro)
        nome = _nome_curto(outro) if outro else "Alguém"
        if c.get("status") == "validada":
            confirmadas.append(nome)
        elif c.get("status") == "pendente":
            aguardando.append(nome)
            if outro:
                aguardando_ids.append(outro["id"])
    # Convites que ela fez e que ainda não entraram (mostra o nome — é contato dela).
    convidados, convidados_ids = [], []
    try:
        inv = (supabase.table("pending_invites").select("nome", "id")
               .eq("inviter_id", membro["id"]).limit(20).execute().data or [])
        convidados = [(r.get("nome") or "").strip() for r in inv]
        convidados_ids = [r.get("id") for r in inv]
    except Exception:
        traceback.print_exc()
    com_nome = [n for n in convidados if n]
    sem_nome = len(convidados) - len(com_nome)

    linhas = ["🤝 *Minha rede*\n"]
    if confirmadas:
        linhas.append("🟢 *Confirmadas:*")
        linhas += [f"• {n}" for n in confirmadas[:10]]
    if aguardando:
        linhas.append("\n⏳ *Aguardando vocês se confirmarem:*")
        linhas += [f"• {n}" for n in aguardando[:10]]
    if com_nome or sem_nome:
        linhas.append("\n📨 *Convidei, ainda não entraram:*")
        linhas += [f"• {n}" for n in com_nome[:10]]
        if sem_nome:
            linhas.append(f"• e mais {sem_nome} convite(s)")
    if not confirmadas and not aguardando and not convidados:
        linhas.append("Você ainda não tem conexões. Convide quem você confia! 💛")

    # Se tem pendências, oferece "Gerenciar"; senão, só "Minha conta" e "Menu"
    if aguardando or com_nome or sem_nome:
        _fluxo_set(membro, {"rede_aguardando": aguardando_ids, "rede_convidados": convidados_ids})
        botoes = [
            {"id": "gerenciar_rede", "label": "✏️ Gerenciar"},
            {"id": "dados", "label": "⚙️ Minha conta"},
            {"id": "menu", "label": "🏠 Menu"}
        ]
    else:
        botoes = _BOTOES_CONTA
    enviar_botoes_meta("\n".join(linhas), botoes)


def _ver_indicacoes_feitas(membro):
    valendo, aguardando = [], []
    rec_pids = set()
    try:
        # 🟢 Valendo: indicações já confirmadas (viraram recomendação).
        recs = (supabase.table("recommendations").select("provider_id")
                .eq("member_id", membro["id"]).limit(50).execute().data or [])
        for r in recs:
            prov = buscar_provider(r["provider_id"])
            if prov:
                valendo.append(prov.get("nome") or "profissional")
                rec_pids.add(prov["id"])
        # ⏳ Aguardando: profissionais que EU indiquei e que ainda não viraram
        # recomendação (não entraram, ou ainda falta a confirmação dos dois lados).
        provs = (supabase.table("providers").select("*")
                 .eq("indicado_por", membro["id"]).limit(50).execute().data or [])
        for p in provs:
            if p["id"] not in rec_pids and p.get("status") != "removido":
                aguardando.append(p.get("nome") or "profissional")
    except Exception:
        traceback.print_exc()
    linhas = ["📤 *Indicações que fiz*\n"]
    if valendo:
        linhas.append("🟢 *Valendo na rede:*")
        linhas += [f"• {n}" for n in valendo[:10]]
    if aguardando:
        linhas.append("\n⏳ *Aguardando a pessoa entrar/confirmar:*")
        linhas += [f"• {n}" for n in aguardando[:10]]
    if not valendo and not aguardando:
        linhas.append("Você ainda não indicou ninguém. Conhece um bom profissional? Indique! 💛")
    enviar_botoes_meta("\n".join(linhas), _BOTOES_CONTA)


def _ver_meu_perfil(membro):
    prov = provider_do_membro(membro["id"])
    if not prov:
        enviar_botoes_meta("Você ainda não tem um perfil profissional. 💼", _BOTOES_CONTA)
        return
    try:
        qtd = len(supabase.table("recommendations").select("id")
                  .eq("provider_id", prov["id"]).execute().data or [])
    except Exception:
        traceback.print_exc(); qtd = 0
    status = prov.get("status")
    # Status SEMPRE claro (Ativo ou Pausado) + complemento de visibilidade embaixo.
    linha_status = "⏸️ *Pausado*" if status == "pausado" else "✅ *Ativo*"
    complementos = []
    if status == "aguardando_perfil":
        complementos.append("📝 Falta finalizar o seu perfil")
    if status == "pausado":
        complementos.append("🔍 Fora das buscas enquanto estiver pausado")
    elif qtd > 0:
        complementos.append("🔍 Aparecendo nas buscas")
    else:
        complementos.append("⏳ Aguardando a 1ª recomendação para aparecer na busca")
    linhas = ["💼 *Meu perfil*\n",
              f"🔧 Serviço: {prov.get('servico') or '—'}",
              f"📍 Região: {prov.get('regiao') or prov.get('bairro') or '—'}",
              f"📊 Recomendações: {qtd}",
              f"Status: {linha_status}"]
    linhas += complementos
    enviar_botoes_meta("\n".join(linhas), _BOTOES_CONTA)


def _ver_quem_recomendou(membro):
    prov = provider_do_membro(membro["id"])
    nomes = []
    if prov:
        try:
            recs = (supabase.table("recommendations").select("*")
                    .eq("provider_id", prov["id"]).limit(20).execute().data or [])
            for r in recs:
                mid = r.get("member_id")
                if mid is None:
                    nomes.append("Alguém da rede")
                else:
                    m = buscar_membro_por_id(mid)
                    nomes.append(_nome_curto(m) if m else "Alguém da rede")
        except Exception:
            traceback.print_exc()
    linhas = ["⭐ *Quem me recomendou*\n"]
    if nomes:
        linhas += [f"• {n}" for n in nomes[:10]]
    else:
        linhas.append("Ainda ninguém registrou uma recomendação sua. Assim que alguém "
                      "recomendar o seu trabalho, aparece aqui. 💛")
    enviar_botoes_meta("\n".join(linhas), _BOTOES_CONTA)


def _ver_gerenciar_rede(membro):
    """Mostra quem está aguardando confirmação ou convites pendentes com ações simples."""
    fluxo = _fluxo_get(membro)
    aguardando_ids = fluxo.get("rede_aguardando", []) if fluxo else []
    convidados_ids = fluxo.get("rede_convidados", []) if fluxo else []

    if not aguardando_ids and not convidados_ids:
        enviar_botoes_meta("Nada a gerenciar agora. 💛", [
            {"id": "dados_rede", "label": "🤝 Minha rede"},
            {"id": "menu",       "label": "🏠 Menu"}])
        return

    rows = []
    # Quem está aguardando confirmação
    for aid in aguardando_ids[:5]:
        outro = buscar_membro_por_id(aid)
        if outro:
            nome = _nome_curto(outro)
            rows.append({"id": f"gerir_aguarda:{aid}", "title": f"⏳ {nome}",
                         "description": "Lembrar ou remover"})

    # Quem foi convidado mas não entrou (pending_invites)
    if convidados_ids:
        for inv_id in convidados_ids[:5]:
            try:
                inv = supabase.table("pending_invites").select("nome").eq("id", inv_id).limit(1).execute().data
                if inv:
                    nome = (inv[0].get("nome") or "").strip() or "Contato"
                    rows.append({"id": f"gerir_convite:{inv_id}", "title": f"📨 {nome}",
                                 "description": "Reenviar link ou remover"})
            except Exception:
                traceback.print_exc()

    if not rows:
        enviar_botoes_meta("Nada a gerenciar agora. 💛", [
            {"id": "dados_rede", "label": "🤝 Minha rede"},
            {"id": "menu",       "label": "🏠 Menu"}])
        return

    rows.append({"id": "dados_rede", "title": "🏠 Voltar", "description": "Voltar à minha rede"})
    enviar_lista_meta("👥 Gerenciar rede", "Escolher", rows)


def _gerir_pessoa(membro, alvo_id):
    alvo = buscar_membro_por_id(alvo_id)
    nome = _nome_curto(alvo) if alvo else "essa pessoa"
    enviar_botoes_meta(f"O que você quer fazer com *{nome}*?", [
        {"id": f"bloquear:{alvo_id}", "label": "🚫 Bloquear"},
        {"id": f"remover:{alvo_id}",  "label": "🗑️ Remover"},
        {"id": "gerenciar_rede",      "label": "🔙 Voltar"}])


def _ver_bloqueados(membro):
    ids = bloqueados_de(membro)
    if not ids:
        enviar_botoes_meta(t.SEM_BLOQUEADOS, _BOTOES_CONTA)
        return
    rows = []
    for bid in ids[:10]:
        m = buscar_membro_por_id(bid)
        rows.append({"id": f"desbloquear:{bid}",
                     "title": (_nome_curto(m) if m else "Alguém")[:24],
                     "description": "Tocar para desbloquear"})
    enviar_lista_meta("🔓 Bloqueados — toque para desbloquear", "Ver", rows)


def gerar_e_enviar_link_convite(membro):
    """Convite do perfil CLIENTE para trazer outra pessoa de confiança (outro cliente)
    para a rede. Entrega as duas mensagens oficiais: a que a pessoa vê (com o link) e a
    pronta para encaminhar. É um link diferente do de indicar um profissional."""
    numero_bot = g.get("display_phone_number") or ""
    codigo = obter_ou_criar_codigo(membro)
    link = encurtar_link(montar_link_convite(numero_bot, codigo))
    resposta_whatsapp(t.CONVIDAR_CLIENTE_VOCE.format(link=link))
    resposta_whatsapp(t.CONVITE_MENSAGEM_AMIGO.format(link=link))


def gerar_e_enviar_link_recomendar(membro):
    """Kit do PROFISSIONAL para pedir recomendações a quem ele já atendeu: instruções
    curtas + a mensagem pronta para encaminhar (com o link pessoal dele). Espelho do
    'Convidar quem confio', mas na voz do profissional."""
    numero_bot = g.get("display_phone_number") or ""
    codigo = obter_ou_criar_codigo(membro)
    link = encurtar_link(montar_link_recomendar(numero_bot, codigo))
    resposta_whatsapp(t.REC_PEDIR_VOCE)
    # A mensagem pronta vai SEPARADA, para encaminhar só ela.
    resposta_whatsapp(t.REC_MENSAGEM_CLIENTE.format(link=link))
    enviar_menu_prestador()


def _abrir_conexao_recomendar(cliente, prof, prov):
    """Cliente entrou pelo link 'recomendar' do profissional: abre a conexão com o
    lado do CLIENTE já confirmado (entrar pelo link é o consentimento de quem
    recomenda) e pergunta SÓ ao profissional se conhece. Quando ele confirmar, a
    recomendação do cliente passa a valer (origem 'prof_convite')."""
    con = criar_conexao_pendente(prof["id"], cliente["id"], "prof_convite",
                                 provider_id=prov["id"])
    if not con:
        return
    _confirmar_lado_de(con, cliente["id"])
    pn = g.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
    _pedir_confirmacao_conexao(prof, con,
                               t.REC_CONFIRMA_PROF.format(nome=_nome_curto(cliente)),
                               to=prof["wa_id"], phone_number_id=pn)


def _entrada_link_recomendar(membro, codigo):
    """Trata a chegada pelo link 'recomendar' do profissional. Devolve True se cuidou
    da mensagem. Antes do aceite, NADA é gravado além do mínimo (marcador + convite);
    a conexão/recomendação só nasce depois do SIM (LGPD)."""
    ref = membro_por_codigo(codigo)
    prof = buscar_membro_por_id(ref["id"]) if ref else None
    if not prof:
        return False
    if prof["id"] == membro["id"]:
        # Ninguém recomenda a si mesmo (§4.6) — abriu o próprio link.
        enviar_botoes_meta(t.INDICAR_SI_MESMO, [
            {"id": "menu", "label": "🏠 Menu"}])
        return True
    prov = provider_do_membro(prof["id"])
    if not prov:
        return False
    # Já é membro e já aceitou: registra na hora (o profissional confirma depois).
    if membro.get("consent"):
        if esta_bloqueado(membro["id"], prof["id"]):
            return False
        _abrir_conexao_recomendar(membro, prof, prov)
        resposta_whatsapp(t.REC_ENTROU_OK.format(nome=_nome_curto(prof)))
        enviar_menu_do_perfil_ativo(membro)
        return True
    # Ainda não aceitou: guarda o marcador e dá as boas-vindas citando o profissional.
    if not membro.get("invited_by"):
        try:
            supabase.table("members").update(
                {"invited_by": prof["id"]}).eq("id", membro["id"]).execute()
            membro["invited_by"] = prof["id"]
        except Exception:
            traceback.print_exc()
    _fluxo_set(membro, {"fluxo": "entrada_rec", "prof_id": prof["id"]})
    msg = t.BOAS_VINDAS_RECOMENDAR.format(nome=_nome_curto(prof), link=LINK_TERMOS)
    resposta_whatsapp(msg)
    # Registra no histórico para o cérebro NÃO repetir a boas-vindas genérica no "SIM".
    salvar_historico(membro["wa_id"], [
        {"role": "user", "content": "(entrou pelo convite de recomendação)"},
        {"role": "assistant", "content": msg},
    ])
    membro["historico"] = [{"role": "user", "content": "(entrou pelo convite de recomendação)"},
                           {"role": "assistant", "content": msg}]
    return True


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
            {"id": "apagar_sim",    "label": "✅ Confirmar saída"},
            {"id": "apagar_nao",    "label": "💛 Quero ficar"},
            {"id": "ajuda_duracao", "label": "❓ Preciso de ajuda"},
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
    """Autocadastro de profissional: garante um perfil em 'aguardando_perfil' para o
    membro e DEVOLVE o id do provider (ou None se nem assim deu).

    Idempotente e robusto:
    - se já existe um perfil ativo/em andamento, usa esse;
    - se existe um registro antigo de testes/indicação (status 'convidado',
      'removido'…), REVIVE esse mesmo registro em vez de criar outro — evita
      duplicar e evita erro de dado repetido;
    - só cria do zero quando não há nenhum, preenchendo TODOS os campos
      obrigatórios (inclusive 'bairro', que é NOT NULL no banco — a falta dele
      fazia o insert falhar em silêncio e o cadastro não acontecia).
    """
    agora = datetime.now(timezone.utc).isoformat()
    # Já tem um perfil "vivo" (onboarding/aguardando/ativo/pausado)? Usa esse.
    atual = provider_do_membro(membro["id"])
    if atual:
        return atual["id"]
    # Pode haver um registro antigo fora dos status vivos (ex.: 'convidado' de uma
    # indicação anterior, ou 'removido'): revive em vez de inserir um novo.
    try:
        antigos = (supabase.table("providers").select("id")
                   .eq("member_id", membro["id"])
                   .order("created_at", desc=True).limit(1).execute().data)
    except Exception:
        traceback.print_exc()
        antigos = None
    telefone = normalizar_e164(membro["wa_id"]) or membro["wa_id"]
    tel_hash = calcular_contact_hash(telefone)
    if antigos:
        pid = antigos[0]["id"]
        try:
            # Autocadastro = consentimento dado: pode gravar o numero cru (+ hash).
            supabase.table("providers").update({
                "status": "aguardando_perfil",
                "termos_aceitos_em": agora, "termos_versao": termos.DATA_VIGENCIA,
                "telefone": telefone, "telefone_hash": tel_hash,
            }).eq("id", pid).execute()
        except Exception:
            traceback.print_exc()
        return pid
    # Não existe nenhum: cria do zero com todos os campos obrigatórios preenchidos.
    try:
        res = supabase.table("providers").insert({
            "member_id": membro["id"],
            "nome": (membro.get("nome_perfil") or "").strip() or "Profissional",
            "telefone": telefone, "telefone_hash": tel_hash,
            "servico": "", "bairro": "", "cidade": "",
            "status": "aguardando_perfil",
            "termos_aceitos_em": agora, "termos_versao": termos.DATA_VIGENCIA,
        }).execute()
        return res.data[0]["id"] if getattr(res, "data", None) else None
    except Exception:
        traceback.print_exc()
        return None


def iniciar_onboarding_prestador(membro, servico):
    """Vincula (ou cria) um cadastro de prestador ao membro e pede o aceite."""
    # Quem foi indicado e ABRE o link pode JA ser membro (testes, ou já era cliente).
    # Nesse caso o vínculo com quem indicou não foi feito na criação — aplica aqui o
    # convite pendente, senão a pergunta "vocês se conhecem?" nunca dispara.
    if not membro.get("invited_by"):
        try:
            inv = aplicar_convite_pendente(membro["wa_id"])
            if inv:
                supabase.table("members").update(
                    {"invited_by": inv}).eq("id", membro["id"]).execute()
                membro["invited_by"] = inv
        except Exception:
            traceback.print_exc()
    try:
        telefone = normalizar_e164(membro["wa_id"]) or membro["wa_id"]
        h = calcular_contact_hash(telefone)
        # Reaproveita um registro ja indicado com esse telefone (dedupe pelo hash;
        # fallback pelo numero cru para registros antigos, pre-v19).
        existente = (supabase.table("providers").select("*")
                     .eq("telefone_hash", h).limit(1).execute().data)
        if not existente:
            existente = (supabase.table("providers").select("*")
                         .eq("telefone", telefone).limit(1).execute().data)
        dados = {"member_id": membro["id"], "status": "onboarding", "telefone_hash": h}
        if servico:
            dados["servico"] = servico
        if existente:
            prov = existente[0]
            supabase.table("providers").update(dados).eq("id", prov["id"]).execute()
            servico_final = servico or prov.get("servico") or "seu serviço"
        else:
            # LGPD §4.2: a pessoa ENTROU mas ainda nao aceitou os termos — o numero
            # cru so e gravado no aceite (prest_aceito). Ate la, so o hash.
            dados.update({
                "nome": (membro.get("nome_perfil") or "").strip() or "Profissional",
                "telefone": "", "servico": servico or "", "bairro": "", "cidade": "",
            })
            supabase.table("providers").insert(dados).execute()
            servico_final = servico or "seu serviço"
        enviar_botoes_meta(t.PRESTADOR_ACOLHIDA.format(servico=servico_final, link=LINK_TERMOS_PROF), [
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
    enviar_botoes_meta("💼 Visão Profissional. O que você quer fazer?", [
        {"id": "prest_editar",  "label": "✏️ Editar perfil"},
        {"id": "prest_pausar",  "label": "⏸️ Pausar/Ativar"},
        {"id": "outras_opcoes", "label": "☰ Outras opções"},
    ])


# Acoes da IA que CONCLUEM um pedido — depois delas mostramos o menu principal.
TOOLS_TERMINAIS = {
    "buscar_servico", "salvar_recomendacao", "adicionar_contatos", "convidar_pessoa",
    "gerar_link_convite", "ver_meus_dados", "ver_minhas_indicacoes",
    "ver_minha_rede", "ver_minhas_buscas", "registrar_ajuda",
}

ACEITES_TXT = {"sim", "aceito", "aceitar", "concordo", "pode ser", "bora", "ok",
               "topo", "claro", "aceito os termos"}

MENU_TRIGGERS = {"menu", "inicio", "voltar", "home", "🏠 menu", "oi", "ola", "olá",
                 "oie", "opa", "bom dia", "boa tarde", "boa noite", "menu principal"}

# Status de prestador que ja contam como "tem perfil profissional" (mostra visao dupla).
PRESTADOR_ATIVO_STATUS = {"aguardando_perfil", "ativo", "pausado"}

# Botoes que pertencem ao fluxo de indicacao (qualquer outro botao sai do fluxo).
BOTOES_INDICAR = {"ind_certo", "ind_corrigir"}

# Botoes do fluxo de perfil profissional (qualquer outro sai do fluxo).
BOTOES_PERFIL = {"perfil_ok", "perfil_corrigir"}


def _enviar_pedido_perfil(membro, provider_id):
    """Pede a descrição do trabalho (texto livre) e DEIXA O FLUXO ARMADO.

    Marca o estado como `perfil_prof` antes de pedir a descrição. Assim, o que a
    pessoa escrever em seguida cai no fluxo determinístico de validação de perfil
    (bloco perfil_prof), e NUNCA na conversa livre da IA. Isso conserta o bug de
    'não consigo me registrar como profissional': a descrição é sempre capturada
    pelo código, independente de sincronia do status do cadastro.
    """
    _fluxo_set(membro, {"fluxo": "perfil_prof", "provider_id": provider_id})
    # Variação: se já era cliente (consentiu), usa "também como profissional".
    msg = t.PRESTADOR_QUERO_SER_OK_DUAL if membro.get("consent") else t.PRESTADOR_QUERO_SER_OK
    enviar_botoes_meta(msg, [
        {"id": "menu", "label": "✅ Concluir"},
        {"id": "outras_opcoes", "label": "☰ Outras opções"}
    ])


def _enviar_validacao_perfil(membro, fluxo):
    enviar_botoes_meta(
        t.PRESTADOR_VALIDAR.format(
            categoria=fluxo.get("categoria") or "—",
            subcategoria=fluxo.get("subcategoria") or "—",
            regiao=fluxo.get("regiao") or "—",
            diferenciais=fluxo.get("diferenciais") or "—",
            contato=fluxo.get("contato") or "—"),
        [{"id": "perfil_ok",       "label": "✅ Confirmar"},
         {"id": "perfil_corrigir", "label": "✏️ Corrigir"},
         {"id": "outras_opcoes",   "label": "☰ Outras opções"}])


def _iniciar_validacao_perfil(membro, provider_id, texto):
    """Lê a descrição do profissional, organiza em campos (categoria/subcategoria/
    região/diferenciais/contato) e mostra para validação por botões."""
    dados = nlu.extrair_perfil_profissional(texto)
    fluxo = {"fluxo": "perfil_prof", "provider_id": provider_id,
             "raw": (texto or "").strip(),
             "categoria":    (dados.get("categoria") or "").strip(),
             "subcategoria": (dados.get("subcategoria") or "").strip(),
             "regiao":       (dados.get("regiao") or "").strip(),
             "diferenciais": (dados.get("diferenciais") or "").strip(),
             "contato":      (dados.get("contato") or "").strip()}
    _fluxo_set(membro, fluxo)
    _enviar_validacao_perfil(membro, fluxo)


def _salvar_perfil(membro, fluxo):
    """Grava o perfil validado e ativa o cadastro do profissional."""
    pid = fluxo.get("provider_id")
    categoria = (fluxo.get("categoria") or "").strip()
    regiao    = (fluxo.get("regiao") or "").strip()
    servico   = (categoria or "serviço").lower()
    # descricao rica preserva o texto original (com subcategoria e contato).
    partes = []
    if fluxo.get("subcategoria"):
        partes.append(f"Especialidade: {fluxo['subcategoria']}")
    if fluxo.get("contato"):
        partes.append(f"Contato/pagamento: {fluxo['contato']}")
    if fluxo.get("raw"):
        partes.append(fluxo["raw"])
    descricao = "\n".join(partes)
    dados = {
        "servico": servico,
        "regiao": regiao,
        "bairro": regiao or "São Paulo",
        "cidade": "São Paulo",
        "diferenciais": (fluxo.get("diferenciais") or "").strip(),
        "descricao": descricao,
        "status": "ativo",
    }
    # Regra: o nome OFICIAL é o que o profissional validou — usamos o nome do perfil
    # dele no WhatsApp (sobrepõe o nome que quem indicou tinha escrito).
    nome_prof = (membro.get("nome_perfil") or "").strip()
    if nome_prof:
        dados["nome"] = nome_prof
    try:
        supabase.table("providers").update(dados).eq("id", pid).execute()
    except Exception:
        traceback.print_exc()
    _fluxo_limpar(membro)
    try:
        tem_reco = bool(supabase.table("recommendations").select("id")
                        .eq("provider_id", pid).limit(1).execute().data)
    except Exception:
        tem_reco = False
    resposta_whatsapp(t.PRESTADOR_PERFIL_OK if tem_reco else t.PRESTADOR_PERFIL_INVISIVEL)
    # Acabou de montar o lado profissional: passa a navegar nele e mostra o menu
    # (e, se for a 1ª vez como dual, avisa que dá pra escrever TROCAR).
    set_perfil_ativo(membro, "profissional")
    enviar_menu_do_perfil_ativo(membro)


def _passo_perfil(membro, fluxo, texto, button_id, cmd):
    """Conduz um passo do fluxo de perfil profissional. Retorna True se respondeu."""
    if cmd == "perfil_ok":
        _salvar_perfil(membro, fluxo)
        return True
    if cmd == "perfil_corrigir":
        resposta_whatsapp(t.PRESTADOR_CORRIGIR)
        # O texto original vai numa mensagem SEPARADA (copia só ele) + navegação.
        enviar_botoes_meta((fluxo.get("raw") or "—"), [{"id": "menu", "label": "🏠 Menu"}])
        return True
    if (texto or "").strip():
        # Reenviou a descrição (correção ou complemento): organiza e valida de novo.
        _iniciar_validacao_perfil(membro, fluxo.get("provider_id"), texto)
        return True
    _enviar_validacao_perfil(membro, fluxo)
    return True


# ---------------------------------------------------------------------------
# FLUXO: CLIENTE INDICA UM PROFISSIONAL (regra de ouro — consentimento primeiro)
# ---------------------------------------------------------------------------
# Anti-spam (§10): teto de indicações/convites por pessoa por dia.
LIMITE_INDICACOES_DIA = 20


def _limite_indicacoes_atingido(membro):
    """True se a pessoa já passou do teto diário de indicações/convites (anti-spam).
    Contamos os convites pendentes criados nas últimas 24h (cada indicação/convite
    registra um)."""
    try:
        desde = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        n = len((supabase.table("pending_invites").select("id")
                 .eq("inviter_id", membro["id"]).gte("created_at", desde).execute().data) or [])
        return n >= LIMITE_INDICACOES_DIA
    except Exception:
        traceback.print_exc()
        return False


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
            resposta_whatsapp(t.INDICAR_CORRIGIR)
            # A linha editável vai numa mensagem SEPARADA (copia só os dados) e já
            # carrega o botão de navegação, pra nunca ficar sem saída.
            enviar_botoes_meta(
                t.INDICAR_CORRIGIR_LINHA.format(
                    nome=fluxo.get("nome", ""), servico=fluxo.get("servico", ""),
                    bairro=fluxo.get("bairro", ""), detalhe=fluxo.get("detalhe", "")),
                [{"id": "menu", "label": "🏠 Menu"}])
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
    # Anti-spam (§10): respeita o teto diário.
    if _limite_indicacoes_atingido(membro):
        _fluxo_limpar(membro)
        enviar_botoes_meta(t.LIMITE_INDICACOES, [{"id": "menu", "label": "🏠 Menu"}])
        return
    try:
        # LGPD §4.2: o dedupe é pelo HASH (com pepper). O número cru fica só na
        # memória desta função (pro link de um toque) — NUNCA no banco enquanto o
        # profissional não entrou e aceitou os termos.
        h = calcular_contact_hash(telefone)
        existente = (supabase.table("providers").select("*")
                     .eq("telefone_hash", h).limit(1).execute().data)
        if not existente:
            # Compatibilidade: registros antigos (pré-v19) ainda sem hash.
            existente = (supabase.table("providers").select("*")
                         .eq("telefone", telefone).limit(1).execute().data)
        if existente:
            prov = existente[0]
            # Não mexe em quem já entrou/é ativo; só completa um registro 'convidado'.
            if prov.get("status") in (None, "", "convidado", "removido"):
                supabase.table("providers").update({
                    "nome": nome, "servico": servico, "bairro": bairro,
                    "cidade": "São Paulo", "descricao": detalhe, "status": "convidado",
                    "indicado_por": membro["id"], "telefone_hash": h,
                }).eq("id", prov["id"]).execute()
        else:
            supabase.table("providers").insert({
                "nome": nome, "telefone": "", "telefone_hash": h,
                "servico": servico or "serviço",
                "bairro": bairro, "cidade": "São Paulo", "descricao": detalhe,
                "indicado_por": membro["id"],
                "status": "convidado",
            }).execute()
        # Liga o profissional a quem indicou assim que ele entrar pelo número.
        registrar_convite_pendente(membro, telefone, nome=nome)
    except Exception:
        traceback.print_exc()

    _fluxo_limpar(membro)
    numero_bot = g.get("display_phone_number") or ""
    # Link que o PROFISSIONAL clica para entrar (abre a conversa dele com a Dorote.ia).
    bot_link = encurtar_link(montar_link_prestador(numero_bot, servico or "serviço")) if numero_bot else ""
    # Link de UM TOQUE: abre a conversa do cliente COM o profissional, já com a
    # mensagem (que contém o convite) escrita — mesma dinâmica do "Convidar".
    um_toque = ""
    if bot_link:
        msg_prof = t.PRESTADOR_CONVITE_MENSAGEM.format(link=bot_link)
        um_toque = encurtar_link(montar_link_para_contato(telefone, msg_prof))
    resposta_whatsapp(t.INDICAR_LINK.format(
        nome=nome, link=um_toque or bot_link or "(link indisponível no momento)"))
    enviar_menu_principal(membro)


# ---------------------------------------------------------------------------
# BLOQUEIO (§7) — a pessoa pode bloquear alguém a qualquer momento
# ---------------------------------------------------------------------------
def esta_bloqueado(id_a, id_b):
    """True se A bloqueou B OU B bloqueou A (qualquer direção)."""
    if not id_a or not id_b:
        return False
    try:
        for x, y in ((id_a, id_b), (id_b, id_a)):
            if (supabase.table("bloqueios").select("id").eq("member_id", x)
                    .eq("bloqueado_id", y).limit(1).execute().data):
                return True
    except Exception:
        traceback.print_exc()
    return False


def bloqueados_de(membro):
    try:
        rows = (supabase.table("bloqueios").select("bloqueado_id")
                .eq("member_id", membro["id"]).execute().data or [])
        return [r["bloqueado_id"] for r in rows]
    except Exception:
        traceback.print_exc()
        return []


def _recusar_conexoes_entre(id_a, id_b):
    agora = datetime.now(timezone.utc).isoformat()
    try:
        for x, y in ((id_a, id_b), (id_b, id_a)):
            (supabase.table("conexoes").update({"status": "recusada", "updated_at": agora})
             .eq("member_a", x).eq("member_b", y).neq("status", "recusada").execute())
    except Exception:
        traceback.print_exc()


def bloquear_membro(membro, alvo_id):
    """Bloqueia o alvo e recusa qualquer conexão entre os dois."""
    if not alvo_id or alvo_id == membro["id"]:
        return
    try:
        ja = (supabase.table("bloqueios").select("id").eq("member_id", membro["id"])
              .eq("bloqueado_id", alvo_id).limit(1).execute().data)
        if not ja:
            supabase.table("bloqueios").insert(
                {"member_id": membro["id"], "bloqueado_id": alvo_id}).execute()
    except Exception:
        traceback.print_exc()
    _recusar_conexoes_entre(membro["id"], alvo_id)


def desbloquear_membro(membro, alvo_id):
    try:
        (supabase.table("bloqueios").delete().eq("member_id", membro["id"])
         .eq("bloqueado_id", alvo_id).execute())
    except Exception:
        traceback.print_exc()


# ---------------------------------------------------------------------------
# CONEXÕES MÚTUAS (os DOIS lados confirmam que se conhecem — §6/§7.5)
# ---------------------------------------------------------------------------
def _nome_curto(membro):
    return ((membro.get("nome_perfil") or "").split() or ["Alguém"])[0]


def criar_conexao_pendente(member_a, member_b, origem, provider_id=None, motivo=None):
    """Cria (ou reaproveita) a conexão pendente entre A (convidou/indicou) e B (entrou).
    `motivo` é o porquê da indicação (guardado para enriquecer as buscas)."""
    if not member_a or not member_b or member_a == member_b:
        return None
    if esta_bloqueado(member_a, member_b):   # bloqueio impede nova conexão
        return None
    motivo = (motivo or "").strip() or None
    try:
        existe = (supabase.table("conexoes").select("*")
                  .eq("member_a", member_a).eq("member_b", member_b).limit(1).execute().data)
        if existe:
            con = existe[0]
            patch = {}
            if provider_id and not con.get("provider_id"):
                patch["provider_id"] = provider_id
            if motivo and not con.get("motivo"):
                patch["motivo"] = motivo
            if patch:
                supabase.table("conexoes").update(patch).eq("id", con["id"]).execute()
                con.update(patch)
            return con
        dados = {"member_a": member_a, "member_b": member_b, "origem": origem}
        if provider_id:
            dados["provider_id"] = provider_id
        if motivo:
            dados["motivo"] = motivo
        res = supabase.table("conexoes").insert(dados).execute()
        return res.data[0] if getattr(res, "data", None) else None
    except Exception:
        traceback.print_exc()
        return None


def buscar_conexao(con_id):
    try:
        rows = supabase.table("conexoes").select("*").eq("id", con_id).limit(1).execute().data
        return rows[0] if rows else None
    except Exception:
        traceback.print_exc()
        return None


def conexao_validada_entre(id1, id2):
    """True se há conexão VALIDADA (mútua) entre os dois membros, em qualquer ordem.
    Se um bloqueou o outro, NÃO há vínculo."""
    if esta_bloqueado(id1, id2):
        return False
    try:
        for a, b in ((id1, id2), (id2, id1)):
            r = (supabase.table("conexoes").select("id").eq("status", "validada")
                 .eq("member_a", a).eq("member_b", b).limit(1).execute().data)
            if r:
                return True
    except Exception:
        traceback.print_exc()
    return False


def conexoes_pendentes_de(membro):
    """Conexões pendentes em que ESTE membro ainda não confirmou o seu lado."""
    out = []
    try:
        a = (supabase.table("conexoes").select("*").eq("member_a", membro["id"])
             .eq("status", "pendente").eq("a_confirmou", False).execute().data) or []
        b = (supabase.table("conexoes").select("*").eq("member_b", membro["id"])
             .eq("status", "pendente").eq("b_confirmou", False).execute().data) or []
        out = a + b
    except Exception:
        traceback.print_exc()
    return out


def _pedir_confirmacao_conexao(destino_membro, con, texto, to=None, phone_number_id=None):
    """Envia a pergunta 'vocês se conhecem?' com botões que carregam o id da conexão."""
    enviar_botoes_meta(
        texto,
        [{"id": f"conf_sim:{con['id']}", "label": "✅ Sim, confirmo"},
         {"id": f"conf_nao:{con['id']}", "label": "❌ Não conheço"}],
        to=to, phone_number_id=phone_number_id)


def _outro_lado(con, membro):
    """Devolve o membro do OUTRO lado da conexão."""
    outro_id = con["member_b"] if con["member_a"] == membro["id"] else con["member_a"]
    return buscar_membro_por_id(outro_id)


def _efeitos_conexao_validada(con):
    """Quando a conexão valida: se envolver um profissional, a recomendação passa a
    valer (🟢). Quem recomenda depende da origem:
    - 'profissional'  → member_a (o cliente que INDICOU o profissional);
    - 'prof_convite'  → member_b (o cliente que entrou pelo link do profissional —
      o profissional NUNCA recomenda a si mesmo).
    Para 'cliente', a própria conexão validada já serve de vínculo."""
    origem = con.get("origem")
    if origem in ("profissional", "prof_convite") and con.get("provider_id"):
        recomendador_id = con["member_a"] if origem == "profissional" else con["member_b"]
        prov = buscar_provider(con["provider_id"])
        if not prov:
            return
        try:
            ja = (supabase.table("recommendations").select("id")
                  .eq("member_id", recomendador_id).eq("provider_id", prov["id"])
                  .limit(1).execute().data)
            if not ja:
                supabase.table("recommendations").insert({
                    "member_id": recomendador_id, "provider_id": prov["id"],
                    "servico": prov.get("servico") or "serviço",
                    "bairro": prov.get("bairro") or "não informado",
                    "cidade": prov.get("cidade") or "São Paulo",
                    # O "porquê" da indicação enriquece a recomendação (e a busca).
                    "nota": con.get("motivo") or None,
                }).execute()
            # §5.3: com uma recomendação REAL, e já tendo entrado e aceitado os termos,
            # o profissional passa a ATIVO — ou seja, aparece na busca. É a recomendação
            # de verdade que dá visibilidade (não a configuração do perfil, que pode vir
            # depois). Não mexe em quem saiu (removido) ou pausou de propósito.
            if prov.get("status") not in ("removido", "pausado", "ativo"):
                supabase.table("providers").update(
                    {"status": "ativo"}).eq("id", prov["id"]).execute()
        except Exception:
            traceback.print_exc()


def _aplicar_confirmacao_conexao(membro, con, confirmou):
    """Registra o sim/não do lado de quem respondeu. Quando os DOIS confirmam, a
    conexão vira validada e dispara os efeitos."""
    if con["member_a"] == membro["id"]:
        lado = "a_confirmou"
    elif con["member_b"] == membro["id"]:
        lado = "b_confirmou"
    else:
        return
    agora = datetime.now(timezone.utc).isoformat()
    if not confirmou:
        try:
            supabase.table("conexoes").update(
                {"status": "recusada", "updated_at": agora}).eq("id", con["id"]).execute()
        except Exception:
            traceback.print_exc()
        resposta_whatsapp(t.CONEXAO_RECUSADA)
        enviar_menu_principal(membro)
        return
    try:
        supabase.table("conexoes").update({lado: True, "updated_at": agora}).eq("id", con["id"]).execute()
    except Exception:
        traceback.print_exc()
    con[lado] = True
    if con.get("a_confirmou") and con.get("b_confirmou"):
        try:
            supabase.table("conexoes").update(
                {"status": "validada", "updated_at": agora}).eq("id", con["id"]).execute()
        except Exception:
            traceback.print_exc()
        _efeitos_conexao_validada(con)
        resposta_whatsapp(t.CONEXAO_VALIDADA)
    else:
        resposta_whatsapp(t.CONEXAO_AGUARDA_OUTRO)
    enviar_menu_principal(membro)


def _tratar_botao_conexao(membro, cmd):
    """Trata conf_sim:/conf_nao: — retorna True se tratou."""
    if cmd.startswith("conf_sim:") or cmd.startswith("conf_nao:"):
        con = buscar_conexao(cmd.split(":", 1)[1])
        if not con or con.get("status") != "pendente":
            resposta_whatsapp("Essa confirmação já foi resolvida. 💛")
            enviar_menu_principal(membro)
            return True
        _aplicar_confirmacao_conexao(membro, con, cmd.startswith("conf_sim:"))
        return True
    return False


def _abrir_conexao_indicacao(provider_membro, prest):
    """No aceite do profissional INDICADO: cria a conexão pendente com quem indicou
    e pergunta aos DOIS lados se se conhecem (§6/§7.5).

    §7.5: Não enviamos proativo — se estiver fora da janela de 24h, Meta rejeita.
    Em vez disso, guardamos como pendente e exibimos quando o cliente reabrir."""
    cliente = buscar_membro_por_id(provider_membro.get("invited_by"))
    if not cliente or not cliente.get("consent"):
        return
    # O motivo da indicação está na descrição do convidado (antes de o profissional
    # preencher o próprio perfil) — guardamos na conexão para virar nota da recomendação.
    con = criar_conexao_pendente(cliente["id"], provider_membro["id"], "profissional",
                                 provider_id=prest.get("id"),
                                 motivo=(prest.get("descricao") or "").strip())
    if not con:
        return
    # O profissional (member_b) entrou pelo link da indicação — isso já é o consentimento
    # do vínculo. Só quem INDICOU (cliente) é perguntado se conhece.
    _confirmar_lado_de(con, provider_membro["id"])
    # Confirmação fica pendente; será exibida quando o cliente reabrir o chat.


# ---------------------------------------------------------------------------
# FLUXO: AVALIACAO POR BOTOES (a IA nunca da nota — §1/§9.9)
# ---------------------------------------------------------------------------
# Só perguntamos "usou?" ao reabrir o chat depois de tempo suficiente pra ser
# plausível que a pessoa tenha usado a indicação (não logo após a busca).
HORAS_MIN_AVALIAR_REABERTURA = 48


def _avaliacao_pendente_ind(membro):
    """Indicacao recebida pendente, com idade minima, pronta pra avaliar.
    Retorna (ind_row, prestador) ou None."""
    try:
        pend = (supabase.table("indicacoes_recebidas").select("*")
                .eq("member_id", membro["id"]).eq("status", "pendente")
                .order("created_at", desc=True).limit(5).execute().data)
    except Exception:
        traceback.print_exc()
        return None
    agora = datetime.now(timezone.utc)
    for ind in pend:
        criada = _parse_ts(ind.get("created_at"))
        if criada is None:
            continue
        if (agora - criada).total_seconds() / 3600 < HORAS_MIN_AVALIAR_REABERTURA:
            continue
        prestador = buscar_provider(ind["provider_id"])
        if prestador is None:
            continue
        return ind, prestador
    return None


_NOTAS_ROWS_BASE = [
    ("5", "⭐⭐⭐⭐⭐ 5", "Excelente"),
    ("4", "⭐⭐⭐⭐ 4", "Muito bom"),
    ("3", "⭐⭐⭐ 3", "Bom"),
    ("2", "⭐⭐ 2", "Regular"),
    ("1", "⭐ 1", "Fraco"),
]


def _enviar_pergunta_avaliacao(membro, ind, prestador, to=None, phone_number_id=None):
    """Pergunta (por botoes) se a pessoa usou a indicacao. STATELESS: o id da
    indicacao vai codificado nos botoes — nada fica preso em estado (evita travar a
    proxima mensagem da pessoa)."""
    iid = ind["id"]
    enviar_botoes_meta(
        t.AVALIAR_USOU.format(nome=prestador.get("nome") or "essa pessoa",
                              servico=prestador.get("servico") or "serviço"),
        [{"id": f"aval_usei:{iid}",  "label": "✅ Usei"},
         {"id": f"aval_ainda:{iid}", "label": "⏳ Ainda não"}],
        to=to, phone_number_id=phone_number_id)


def _enviar_lista_notas(nome, iid):
    enviar_lista_meta(
        t.AVALIAR_NOTA.format(nome=nome), "Dar nota",
        [{"id": f"aval_nota:{iid}:{n}", "title": titulo, "description": desc}
         for n, titulo, desc in _NOTAS_ROWS_BASE])


def _ind_e_prestador(iid):
    try:
        rows = (supabase.table("indicacoes_recebidas").select("*")
                .eq("id", iid).limit(1).execute().data)
        if not rows:
            return None, None
        return rows[0], buscar_provider(rows[0]["provider_id"])
    except Exception:
        traceback.print_exc()
        return None, None


def _tratar_botao_avaliacao(membro, cmd):
    """Trata os botoes de avaliacao (aval_usei:/aval_ainda:/aval_nota:). Retorna
    True se tratou. Stateless: tudo vem codificado no id do botao."""
    if cmd.startswith("aval_usei:"):
        iid = cmd.split(":", 1)[1]
        _, prest = _ind_e_prestador(iid)
        _enviar_lista_notas((prest or {}).get("nome") or "essa pessoa", iid)
        return True
    if cmd.startswith("aval_ainda:"):
        iid = cmd.split(":", 1)[1]
        try:
            supabase.table("indicacoes_recebidas").update({
                "status": "dispensada",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", iid).execute()
        except Exception:
            traceback.print_exc()
        resposta_whatsapp(t.AVALIAR_AINDA)
        enviar_menu_principal(membro)
        return True
    m = re.match(r"aval_nota:([^:]+):([1-5])$", cmd)
    if m:
        iid, nota = m.group(1), int(m.group(2))
        ind, prest = _ind_e_prestador(iid)
        if ind and prest:
            _gravar_avaliacao(membro, ind, prest, nota)
        resposta_whatsapp(t.AVALIAR_OBRIGADA)
        enviar_menu_principal(membro)
        return True
    return False


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
                # LGPD: saiu -> o numero cru sai do cadastro (fica so o hash de dedupe).
                supabase.table("providers").update(
                    {"status": "removido", "member_id": None,
                     "telefone": ""}).eq("id", prest["id"]).execute()
            except Exception:
                traceback.print_exc()
        excluir_membro(membro)
        resposta_whatsapp(t.ADEUS)
        return True
    if cmd == "apagar_nao":
        resposta_whatsapp("Ufa, não apaguei nada! 😌 Está tudo no lugar.")
        if consentiu:
            enviar_menu_principal(membro)
        return True
    if cmd == "sair_um_perfil":
        enviar_escolha_ficar_um_perfil()
        return True
    if cmd == "sair_so_cliente":
        prest = provider_do_membro(membro["id"])
        if prest:
            supabase.table("providers").update(
                {"status": "removido", "telefone": ""}).eq("id", prest["id"]).execute()
        resposta_whatsapp("Pronto! 💛 Mantivemos apenas o seu perfil de cliente. "
                          "Você não será mais recomendado como profissional.")
        enviar_menu_principal(membro)
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

    # -------- Fluxo: PRECISO DE AJUDA (durante processo de saída) --------
    if cmd == "ajuda_duracao":
        _fluxo_set(membro, {"fluxo": "ajuda"})
        resposta_whatsapp(t.AJUDA_PEDIR_DURACAO)
        return True

    fajuda = _fluxo_get(membro)
    if fajuda.get("fluxo") == "ajuda":
        if cmd == "voltar_ajuda":
            _fluxo_limpar(membro)
            resposta_whatsapp("Que bom! 💛 Tá tudo aqui esperando você.")
            if consentiu:
                enviar_menu_principal(membro)
            return True
        if cmd == "sair_mesmo":
            _fluxo_limpar(membro)
            # Volta para o fluxo de saída sem fazer nada
            return False
        if not button_id and (texto or "").strip():
            # Recebeu a resposta de ajuda
            _fluxo_limpar(membro)
            enviar_botoes_meta(t.AJUDA_AGRADECIDA, [
                {"id": "voltar_ajuda", "label": "🏠 Voltar e continuar"},
                {"id": "sair_mesmo",   "label": "🚪 Sair mesmo assim"},
            ])
            return True
        return True

    # -------- TROCAR de perfil (comando global, só para quem tem os dois) --------
    if consentiu and cmd in ("trocar", "trocar perfil", "trocar de perfil"):
        _fluxo_limpar(membro)
        if not tem_perfil_profissional(membro):
            enviar_botoes_meta(t.TROCAR_SO_CLIENTE, [
                {"id": "quero_ser_prof", "label": "💼 Ser profissional"},
                {"id": "menu",           "label": "🏠 Menu"}])
            return True
        novo = "cliente" if perfil_ativo(membro) == "profissional" else "profissional"
        set_perfil_ativo(membro, novo)
        abrir_id = "perfil_profissional" if novo == "profissional" else "perfil_cliente"
        enviar_botoes_meta(t.TROCAR_OK.format(perfil=_label_perfil(novo)), [
            {"id": abrir_id,        "label": "📂 Abrir menu"},
            {"id": "outras_opcoes", "label": "☰ Opções"}])
        return True

    # -------- Confirmacao de conexao mutua (vocês se conhecem?) --------
    if cmd.startswith("conf_sim:") or cmd.startswith("conf_nao:"):
        if _tratar_botao_conexao(membro, cmd):
            return True

    # -------- Avaliacao por botoes (stateless) --------
    if cmd.startswith("aval_usei:") or cmd.startswith("aval_ainda:") or cmd.startswith("aval_nota:"):
        if _tratar_botao_avaliacao(membro, cmd):
            return True

    # -------- Busca sem resultado: perguntar a amigos --------
    if consentiu and cmd == "pedir_amigos":
        _pedir_amigos_lista(membro)
        return True
    if consentiu and cmd.startswith("ask:"):
        _enviar_ask_amigo(membro, cmd.split(":", 1)[1])
        return True

    # -------- Fluxo ativo: BUSCA RETOMADA (pedido que chegou pré-aceite) --------
    fbusca_retomada = _fluxo_get(membro)
    if consentiu and fbusca_retomada.get("fluxo") == "busca_retomada":
        # Extrai a intenção do pedido pré-aceite via IA e executa a busca.
        pedido_texto = fbusca_retomada.get("pedido_texto", "").strip()
        _fluxo_limpar(membro)
        if pedido_texto:
            # IA vai extrair o serviço do texto (cerebro chama buscar_servico).
            # Por enquanto, passa o texto cru pra cerebro processar.
            # cerebro.conversar vai chamar buscar_servico com o texto como serviço.
            usados = cerebro.conversar(
                membro,
                pedido_texto,
                contatos_compartilhados,
                executar_ferramenta=construir_executor(membro, [False]),
                enviar_texto=enviar_texto_com_botoes_boas_vindas,
                salvar_historico=lambda hist: salvar_historico(wa_id, hist),
            ) or set()
            return True
        return True

    # -------- Fluxo ativo: BUSCA (perguntar a região que faltou) --------
    fbusca = _fluxo_get(membro)
    if consentiu and fbusca.get("fluxo") == "busca":
        servico_b = (fbusca.get("servico") or "").strip()
        if cmd in ("menu", "voltar", "cancelar", "inicio"):
            _fluxo_limpar(membro); enviar_menu_principal(membro); return True
        if cmd == "busca_cidade_toda":
            _fluxo_limpar(membro)
            _executar_e_enviar_busca(membro, servico_b, "", "São Paulo")
            return True
        if cmd == "busca_bairro":
            fbusca["passo"] = "bairro"; _fluxo_set(membro, fbusca)
            enviar_botoes_meta(t.BUSCA_PEDIR_BAIRRO, [
                {"id": "busca_cidade_toda", "label": "🏙️ Toda a cidade"},
                {"id": "menu",              "label": "🏠 Menu"}])
            return True
        if not button_id and (texto or "").strip():
            _fluxo_limpar(membro)
            _executar_e_enviar_busca(membro, servico_b, texto.strip(), "São Paulo")
            return True
        # Outro botão de navegação: sai da busca e deixa o resto tratar.
        _fluxo_limpar(membro)

    # -------- Fluxo ativo: o cliente esta INDICANDO um profissional --------
    fluxo = _fluxo_get(membro)
    if consentiu and fluxo.get("fluxo") == "indicar":
        # Botoes proprios do fluxo seguem para o passo certo; texto idem.
        if button_id in BOTOES_INDICAR or not button_id:
            if cmd in ("menu", "voltar", "cancelar", "inicio"):
                _fluxo_limpar(membro)
                enviar_menu_principal(membro)
                return True
            if _passo_indicar(membro, fluxo, texto, button_id, contatos, cmd):
                return True
        else:
            # Clicou em outro botao de navegacao (menu, ser profissional, etc.):
            # encerra o fluxo e deixa o tratamento normal abaixo cuidar do botao.
            _fluxo_limpar(membro)

    # -------- Fluxo ativo: PERFIL profissional (validação por botões) --------
    if consentiu and fluxo.get("fluxo") == "perfil_prof":
        if button_id in BOTOES_PERFIL or not button_id:
            if cmd in ("menu", "voltar", "cancelar", "inicio"):
                _fluxo_limpar(membro)
                enviar_menu_principal(membro)
                return True
            if _passo_perfil(membro, fluxo, texto, button_id, cmd):
                return True
        else:
            _fluxo_limpar(membro)

    # -------- Prestador de servico: onboarding e perfil --------
    prest = provider_do_membro(membro["id"])
    if prest:
        if cmd == "prest_aceito":
            agora = datetime.now(timezone.utc).isoformat()
            # LGPD §4.2/§4.4: SO no aceite dos termos o numero cru e gravado no
            # cadastro do profissional — e o que sera entregue nas buscas.
            tel_prof = normalizar_e164(membro["wa_id"]) or membro["wa_id"]
            supabase.table("providers").update({
                "status": "aguardando_perfil",
                "termos_aceitos_em": agora,
                "termos_versao": termos.DATA_VIGENCIA,
                "telefone": tel_prof,
                "telefone_hash": calcular_contact_hash(tel_prof),
            }).eq("id", prest["id"]).execute()
            if not membro.get("consent"):
                registrar_consentimento(membro["wa_id"]); membro["consent"] = True
            # Se este profissional foi INDICADO por alguem (chegou pelo link, então
            # invited_by aponta para quem indicou), abre a conexão mútua e pergunta
            # aos DOIS lados se se conhecem.
            if membro.get("invited_by"):
                _abrir_conexao_indicacao(membro, prest)
            _enviar_pedido_perfil(membro, prest["id"])
            return True
        if cmd == "prest_ajustar":
            enviar_botoes_meta(t.PRESTADOR_AJUSTAR, [{"id": "menu", "label": "🏠 Menu"}])
            return True
        if cmd == "prest_nao":
            # Recusou os termos: nao ha consentimento -> nenhum numero cru no cadastro.
            supabase.table("providers").update(
                {"status": "removido", "telefone": ""}).eq("id", prest["id"]).execute()
            resposta_whatsapp(t.PRESTADOR_NAO)
            enviar_menu_do_perfil_ativo(membro)
            return True
        if cmd == "prest_editar":
            supabase.table("providers").update({"status": "aguardando_perfil"}).eq("id", prest["id"]).execute()
            _enviar_pedido_perfil(membro, prest["id"])
            return True
        if cmd == "prof_pedir_rec":
            gerar_e_enviar_link_recomendar(membro)
            return True
        if cmd == "prest_pausar":
            novo = "ativo" if prest.get("status") == "pausado" else "pausado"
            supabase.table("providers").update({"status": novo}).eq("id", prest["id"]).execute()
            # Sempre termina com botões (o mesmo botão liga/desliga) — nunca sem saída.
            if novo == "pausado":
                enviar_botoes_meta(
                    "Cadastro *pausado* — você não vai receber indicações por ora. 💛",
                    [{"id": "prest_pausar", "label": "▶️ Reativar"},
                     {"id": "menu",         "label": "🏠 Menu"}])
            else:
                enviar_botoes_meta(
                    "Cadastro *reativado*! 💼 Você voltou a aparecer para quem busca o seu serviço.",
                    [{"id": "prest_pausar", "label": "⏸️ Pausar"},
                     {"id": "menu",         "label": "🏠 Menu"}])
            return True
        # Texto livre durante o onboarding (nao e botao nem comando de menu):
        if not button_id and cmd not in MENU_TRIGGERS:
            if prest.get("status") == "aguardando_perfil":
                # Organiza a descrição em campos e mostra para validação por botões.
                _iniciar_validacao_perfil(membro, prest["id"], texto)
                return True
            if prest.get("status") == "onboarding":
                servico_novo = (texto or "").strip().lower()
                supabase.table("providers").update({"servico": servico_novo}).eq("id", prest["id"]).execute()
                enviar_botoes_meta(t.PRESTADOR_ACOLHIDA.format(servico=servico_novo or "seu serviço", link=LINK_TERMOS_PROF), [
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
            # Se pessoa fez um pedido antes de aceitar, retoma agora.
            fluxo_pre = _fluxo_get(membro)
            pedido_pre = fluxo_pre.get("pedido_pre_aceite") if fluxo_pre else None
            if pedido_pre:
                _fluxo_limpar(membro)
                # Guarda o pedido pra retomar depois — o cerebro vai extrair a intenção.
                resposta_whatsapp("Que bom! Vou procurar por isso pra você. 💛")
                _fluxo_set(membro, {"fluxo": "busca_retomada", "pedido_texto": pedido_pre})
                # Na próxima mensagem, vai retomar a busca (ver linha ~3273).
                return True
            # Entrou pelo link 'recomendar' de um profissional: com o aceite dado,
            # registra a recomendação (aguardando só a confirmação do profissional).
            fl_rec = _fluxo_get(membro)
            if fl_rec.get("fluxo") == "entrada_rec":
                _fluxo_limpar(membro)
                prof_rec = buscar_membro_por_id(fl_rec.get("prof_id"))
                prov_rec = provider_do_membro(prof_rec["id"]) if prof_rec else None
                if prof_rec and prov_rec:
                    _abrir_conexao_recomendar(membro, prof_rec, prov_rec)
                    resposta_whatsapp(t.REC_ENTROU_OK.format(nome=_nome_curto(prof_rec)))
                    enviar_menu_principal(membro)
                    return True
            if membro.get("invited_by"):
                _abrir_conexao_cliente(membro)
            enviar_menu_principal(membro, t.CLIENTE_ATIVO)
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
                _abrir_conexao_cliente(membro)
            _pid = _criar_perfil_profissional_self(membro)
            if _pid:
                _enviar_pedido_perfil(membro, _pid)
            else:
                enviar_menu_principal(membro)
            return True
        # Deixar para depois — mas sempre com um caminho de volta (botões).
        if cmd == "adiar":
            enviar_botoes_meta(t.ADIAR, [
                {"id": "consent_sim",        "label": "✅ Começar agora"},
                {"id": "consent_saber_mais", "label": "ℹ️ Saber mais"},
            ])
            return True
        # Qualquer outra coisa antes do aceite: reconhece gentilmente (se parece um pedido),
        # guarda a intenção, e pede o aceite.
        palavras_pedido = ["preciso", "quero", "tenho", "procuro", "busco", "precisa", "achei", "need", "help"]
        parece_pedido = any(p in texto_recebido.lower() for p in palavras_pedido) and len(texto_recebido) > 5

        if parece_pedido:
            # Reconhece o pedido com gentileza, guarda em fluxo.
            _fluxo_set(membro, {"pedido_pre_aceite": texto_recebido})
            msg_reconhece = (
                f"Posso te ajudar com isso 💛\n"
                f"Só preciso que você aceite os termos primeiro — é rapidinho."
            )
            enviar_botoes_meta(msg_reconhece, [
                {"id": "consent_sim",        "label": "✅ Aceito e começar"},
                {"id": "consent_saber_mais", "label": "ℹ️ Saber mais"},
            ])
        else:
            # Texto aleatório: reforça o convite normal.
            enviar_botoes_meta(t.PRECISA_CONSENTIR, [
                {"id": "consent_sim",        "label": "✅ Aceito e começar"},
                {"id": "consent_saber_mais", "label": "ℹ️ Saber mais"},
            ])
        return True

    # -------- Depois do aceite: navegacao --------
    # MENU abre o menu do PERFIL ATIVO (não pergunta mais "qual perfil?" toda vez).
    if cmd in MENU_TRIGGERS:
        # Ao reabrir o chat (fora das 24h não dá pra avisar proativo — §7.5), mostra
        # ANTES do menu o que ficou pendente: 1º confirmação de conexão, depois nota.
        cons_pend = conexoes_pendentes_de(membro)
        if cons_pend:
            con = cons_pend[0]
            outro = _outro_lado(con, membro)
            nome = _nome_curto(outro) if outro else "essa pessoa"
            if con.get("member_a") == membro["id"]:
                # Quem convidou/indicou (é sempre este lado que confirma, pela regra nova).
                if con.get("origem") == "profissional":
                    texto = t.INDICAR_CONFIRMA_CLIENTE.format(nome=nome)
                elif con.get("origem") == "prof_convite":
                    texto = t.REC_CONFIRMA_PROF.format(nome=nome)
                else:
                    texto = t.CONEXAO_PERGUNTA_CONVIDOU.format(nome=nome)
            elif con.get("origem") == "profissional":
                # Legado: conexões antigas em que o profissional ainda não confirmou.
                texto = t.CONEXAO_PERGUNTA_PROF.format(nome=nome)
            else:
                texto = t.CONEXAO_PERGUNTA_ENTROU.format(nome=nome)
            _pedir_confirmacao_conexao(membro, con, texto)
            return True
        # Indicacao usada ainda sem nota: avaliacao por botoes (a IA nunca da nota).
        pendente = _avaliacao_pendente_ind(membro)
        if pendente:
            _enviar_pergunta_avaliacao(membro, pendente[0], pendente[1])
            return True
        enviar_menu_do_perfil_ativo(membro)
        return True
    if cmd == "perfil_cliente":
        set_perfil_ativo(membro, "cliente")
        enviar_menu_principal(membro); return True
    if cmd == "perfil_profissional":
        set_perfil_ativo(membro, "profissional")
        enviar_menu_prestador(); return True

    if cmd == "outras_opcoes":
        enviar_outras_opcoes(membro); return True
    if cmd == "dados":
        enviar_submenu_dados(membro); return True
    if cmd == "dados_rede":
        _ver_minha_rede(membro); return True
    if cmd == "dados_indicacoes":
        _ver_indicacoes_feitas(membro); return True
    if cmd == "dados_meu_perfil":
        _ver_meu_perfil(membro); return True
    if cmd == "dados_recomend":
        _ver_quem_recomendou(membro); return True

    # -------- Bloquear / gerenciar a rede --------
    if cmd == "gerenciar_rede":
        _ver_gerenciar_rede(membro); return True
    if cmd == "ver_bloqueados":
        _ver_bloqueados(membro); return True
    if cmd.startswith("gerir:"):
        _gerir_pessoa(membro, cmd.split(":", 1)[1]); return True
    if cmd.startswith("gerir_aguarda:"):
        alvo_id = cmd.split(":", 1)[1]
        alvo = buscar_membro_por_id(alvo_id)
        nome = _nome_curto(alvo) if alvo else "essa pessoa"
        enviar_botoes_meta(f"*{nome}* — aguardando confirmação", [
            {"id": f"remover:{alvo_id}", "label": "🗑️ Remover"},
            {"id": "gerenciar_rede",      "label": "🔙 Voltar"}])
        return True
    if cmd.startswith("gerir_convite:"):
        inv_id = cmd.split(":", 1)[1]
        try:
            inv = supabase.table("pending_invites").select("nome").eq("id", inv_id).limit(1).execute().data
            nome = (inv[0].get("nome") or "").strip() if inv else "esse contato"
        except Exception:
            nome = "esse contato"
        enviar_botoes_meta(f"*{nome}* — ainda não entrou", [
            {"id": f"deletar_convite:{inv_id}", "label": "🗑️ Remover"},
            {"id": "gerenciar_rede",             "label": "🔙 Voltar"}])
        return True
    if cmd.startswith("deletar_convite:"):
        inv_id = cmd.split(":", 1)[1]
        try:
            supabase.table("pending_invites").delete().eq("id", inv_id).execute()
            resposta_whatsapp("Removido 💛")
        except Exception:
            traceback.print_exc()
        _ver_gerenciar_rede(membro)
        return True
    if cmd.startswith("bloquear:"):
        alvo_id = cmd.split(":", 1)[1]
        alvo = buscar_membro_por_id(alvo_id)
        bloquear_membro(membro, alvo_id)
        resposta_whatsapp(t.BLOQUEAR_OK.format(nome=_nome_curto(alvo) if alvo else "essa pessoa"))
        enviar_menu_do_perfil_ativo(membro); return True
    if cmd.startswith("remover:"):
        alvo_id = cmd.split(":", 1)[1]
        alvo = buscar_membro_por_id(alvo_id)
        _recusar_conexoes_entre(membro["id"], alvo_id)
        resposta_whatsapp(t.REMOVER_OK.format(nome=_nome_curto(alvo) if alvo else "essa pessoa"))
        enviar_menu_do_perfil_ativo(membro); return True
    if cmd.startswith("desbloquear:"):
        alvo_id = cmd.split(":", 1)[1]
        alvo = buscar_membro_por_id(alvo_id)
        desbloquear_membro(membro, alvo_id)
        resposta_whatsapp(t.DESBLOQUEAR_OK.format(nome=_nome_curto(alvo) if alvo else "essa pessoa"))
        enviar_menu_do_perfil_ativo(membro); return True

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
        enviar_menu_principal(membro); return True

    if cmd == "quero_ser_prof":
        if prest:   # ja tem perfil profissional
            enviar_botoes_meta("Você já tem um perfil profissional 💛\n\nQuer editar?", [
                {"id": "prest_editar", "label": "✏️ Editar perfil"},
                {"id": "menu",         "label": "🏠 Menu"},
            ])
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
        _pid = _criar_perfil_profissional_self(membro)
        if _pid:
            _enviar_pedido_perfil(membro, _pid)
        else:
            enviar_menu_principal(membro)
        return True

    if cmd == "rede_indicar":
        if _limite_indicacoes_atingido(membro):
            enviar_botoes_meta(t.LIMITE_INDICACOES, [{"id": "menu", "label": "🏠 Menu"}])
            return True
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
        enviar_menu_principal(membro); return True

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

    # RECOMENDAR: chegou pelo link pessoal de um profissional pedindo recomendação.
    # Quem entra por ele está recomendando (regra do titular); o profissional confirma.
    cod_rec = extrair_codigo_recomendar(texto_recebido)
    if cod_rec is not None and _entrada_link_recomendar(membro, cod_rec):
        return

    # CORE (conexão): quem JÁ é membro e JÁ consentiu, ao abrir um link de convite de
    # cliente, não passa de novo pelo aceite — então o vínculo nunca era criado. Aqui
    # conectamos na hora (idempotente). Precisa do texto CRU (com o código), por isso
    # roda ANTES de limpar_texto_convite.
    if membro.get("consent") and _conectar_por_link_cliente(membro, texto_recebido):
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

    # Flag: se a IA mandar botoes via ferramenta, nao envia texto duplicado.
    interativa_enviada = [False]

    def enviar_texto_com_botoes_boas_vindas(texto):
        """Se for a 1ª mensagem de boas-vindas (pré-aceite), envia com botões.
        Senão, envia como texto normal."""
        if interativa_enviada[0]:
            return
        # Detecta se é uma das boas-vindas (contém a estrutura típica).
        if ("Dorote.ia" in texto and ("Responda SIM" in texto or "Posso te ajudar" in texto or "Posso começar" in texto)
            and "Termos de uso" in texto):
            # É boas-vindas: envia com botões.
            enviar_botoes_meta(texto, [
                {"id": "consent_sim",        "label": "✅ Aceito e começar"},
                {"id": "consent_saber_mais", "label": "ℹ️ Saber mais"},
            ])
        else:
            resposta_whatsapp(texto)

    usados = cerebro.conversar(
        membro,
        texto_recebido,
        contatos_compartilhados,
        executar_ferramenta=construir_executor(membro, interativa_enviada),
        enviar_texto=enviar_texto_com_botoes_boas_vindas,
        salvar_historico=lambda hist: salvar_historico(wa_id, hist),
    ) or set()

    # Guarda o NOME dos contatos do cartão na agenda da pessoa (número fica só em
    # hash) — para ela ver, na Minha rede, quem convidou e ainda não respondeu.
    if contatos_compartilhados:
        _salvar_nomes_contatos(membro, contatos_compartilhados)

    # NUNCA FICAR SOLTO (regra firme): se a pessoa já consentiu e a IA respondeu em
    # texto (não mandou botões próprios), o sistema SEMPRE mostra o menu logo depois —
    # seja após uma ação, uma saudação ou um papo fora do tema. Assim toda mensagem
    # termina com navegação clara.
    if membro.get("consent") and not interativa_enviada[0]:
        enviar_menu_do_perfil_ativo(membro)


@app.route("/ping", methods=["GET"])
def ping():
    """Endpoint leve de keep-alive — um monitor (ex.: UptimeRobot) batendo aqui a
    cada ~10 min impede a instância gratuita do Render de 'dormir' e cortar a
    lentidão do primeiro retorno."""
    return Response("ok", mimetype="text/plain")


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
