# app.py
# ---------------------------------------------------------------------------
# DOROTEIA - Camada 5: pedir um servico (entender + consultar grafo + regras)
#
# Caminhos de um membro JA consentido:
#   - Manda numeros        -> viram HASH em edges (Camada 4)
#   - Manda uma frase       -> a Claude extrai {servico, bairro} e a Doroteia
#                             consulta o grafo e responde VERDE / AMARELO / VERMELHO
# ---------------------------------------------------------------------------

import os
from datetime import datetime, timezone
from html import escape

from flask import Flask, request, Response
from supabase import create_client

# Nucleo de privacidade (Camada 4) e entendimento de linguagem (Camada 5).
from privacidade import calcular_contact_hash, extrair_numeros_de_texto, normalizar_e164
from nlu import extrair_servico_bairro, extrair_recomendacao


# ---------------------------------------------------------------------------
# CONEXAO COM O BANCO (Supabase)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)


# ===========================================================================
# FUNCOES DE BANCO
# ===========================================================================

def buscar_membro(wa_id):
    """Procura o membro pelo numero de WhatsApp. Devolve os dados ou None."""
    resposta = supabase.table("members").select("*").eq("wa_id", wa_id).execute()
    return resposta.data[0] if resposta.data else None


def buscar_membro_por_id(member_id):
    """Procura o membro pelo seu id interno (uuid)."""
    resposta = supabase.table("members").select("*").eq("id", member_id).execute()
    return resposta.data[0] if resposta.data else None


def buscar_provider(provider_id):
    """Procura um prestador pelo id."""
    resposta = supabase.table("providers").select("*").eq("id", provider_id).execute()
    return resposta.data[0] if resposta.data else None


def criar_membro(wa_id, nome_perfil):
    supabase.table("members").insert({
        "wa_id": wa_id,
        "nome_perfil": nome_perfil,
        "consent": False,
    }).execute()


def registrar_consentimento(wa_id):
    agora = datetime.now(timezone.utc).isoformat()
    supabase.table("members").update({
        "consent": True,
        "consent_at": agora,
    }).eq("wa_id", wa_id).execute()


def processar_contatos(membro, numeros_e164):
    """Camada 4: guarda os HASHES dos contatos em edges, descartando os crus."""
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


def definir_estado(wa_id, estado):
    """Guarda em que ponto da conversa a pessoa esta (ex: 'recomendando' ou 'normal')."""
    supabase.table("members").update({"estado": estado}).eq("wa_id", wa_id).execute()


def tratar_recomendacao(membro, texto):
    """Camada 6: le os dados do prestador, valida e grava em providers + recommendations."""
    dados = extrair_recomendacao(texto)
    nome = (dados.get("nome") or "").strip() or "Prestador"
    servico = (dados.get("servico") or "").strip()
    bairro = (dados.get("bairro") or "").strip()
    telefone = normalizar_e164((dados.get("telefone") or "").strip())

    # Se faltou algo essencial, pedimos de novo (sem sair do modo recomendacao).
    if not telefone or not servico or not bairro:
        return ("Faltou alguma informacao 😅. Me manda tudo numa mensagem so: "
                "nome, telefone (com DDD), servico e bairro.\n"
                "Ex: Joao, (11) 98888-7777, encanador, Perdizes.\n"
                "(ou mande *cancelar* pra desistir)")

    # Cria o prestador e a indicacao ligada a este membro.
    prestador = supabase.table("providers").insert({
        "nome": nome,
        "telefone": telefone,            # telefone do prestador, em E.164 (e o dado que se entrega)
        "servico": servico.lower(),
        "bairro": bairro,
    }).execute().data[0]

    supabase.table("recommendations").insert({
        "member_id": membro["id"],
        "provider_id": prestador["id"],
        "servico": servico.lower(),
        "bairro": bairro,
    }).execute()

    # Conversa volta ao normal.
    definir_estado(membro["wa_id"], "normal")
    return (f"Anotado: {nome} como {servico} em {bairro}! ✅\n\n"
            "Quando alguem da sua rede pedir isso, sua indicacao aparece "
            "(com seu nome, so pra eles). Valeu por ajudar! 🙏")


# ===========================================================================
# REGRAS VERDE / AMARELO / VERMELHO (item 6 do briefing)
# ===========================================================================

def hash_de_membro(membro):
    """Calcula o hash do proprio numero de um membro (usado pra achar vinculos)."""
    numero = normalizar_e164(membro["wa_id"])
    return calcular_contact_hash(numero) if numero else None


def existe_vinculo(pedidor, recomendador):
    """Existe um vinculo conhecido entre o PEDIDOR (P) e quem indicou (R)?
    Vale por convite (em qualquer direcao) ou por contato compartilhado
    (edge em qualquer direcao). E aqui que o grafo da Camada 4 e usado."""
    # 1) Vinculo por convite
    if pedidor.get("invited_by") and pedidor["invited_by"] == recomendador["id"]:
        return True
    if recomendador.get("invited_by") and recomendador["invited_by"] == pedidor["id"]:
        return True

    # 2) Vinculo por contato compartilhado (compara HASHES, nunca numeros)
    hash_p = hash_de_membro(pedidor)
    hash_r = hash_de_membro(recomendador)
    if hash_p is None or hash_r is None:
        return False

    # P guardou o contato de R?
    if supabase.table("edges").select("id").eq("member_id", pedidor["id"]).eq("contact_hash", hash_r).limit(1).execute().data:
        return True
    # R guardou o contato de P?
    if supabase.table("edges").select("id").eq("member_id", recomendador["id"]).eq("contact_hash", hash_p).limit(1).execute().data:
        return True
    return False


def tratar_pedido_servico(pedidor, servico, bairro):
    """Consulta as indicacoes que batem servico+bairro e aplica as 3 regras."""
    # ilike = busca sem diferenciar maiusculas/minusculas.
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
        return texto_verde(servico, bairro, com_nome)
    if sem_nome:
        return texto_amarelo(servico, bairro, sem_nome)
    return texto_vermelho(servico, bairro)


# ===========================================================================
# MONTAGEM DAS RESPOSTAS
# ===========================================================================

def resposta_whatsapp(texto):
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escape(texto)}</Message>
</Response>"""
    return Response(twiml, mimetype="application/xml")


def texto_verde(servico, bairro, lista):
    linhas = [f"Achei! {servico.capitalize()} em {bairro}: 🟢\n"]
    for prestador, nome_quem_indicou in lista:
        linhas.append(f"- {prestador['nome']} - indicado por {nome_quem_indicou} (do seu contato)")
        linhas.append(f"  Telefone: {prestador['telefone']}")
    linhas.append("\nQualquer coisa, e so chamar! 😊")
    return "\n".join(linhas)


def texto_amarelo(servico, bairro, prestadores):
    linhas = [
        f"Na sua rede direta ainda ninguem indicou {servico} em {bairro}.",
        f"Mas tenho {len(prestadores)} indicacao(oes) bem avaliada(s) (nao posso dizer quem indicou): 🟡\n",
    ]
    for prestador in prestadores:
        linhas.append(f"- {prestador['nome']} - Telefone: {prestador['telefone']}")
    linhas.append("\nDica: convide gente da sua confianca pra essas indicacoes aparecerem com nome. 😉")
    return "\n".join(linhas)


def texto_vermelho(servico, bairro):
    return (f"Ainda nao tenho {servico} indicado em {bairro}. 🔴\n"
            "Conhece um bom? Me indica! Manda o numero dele e diga o servico e o bairro - "
            "assim voce ajuda a galera. 🙌")


def texto_contatos_recebidos(total, ja_membros):
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
# TEXTOS FIXOS
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
    "Depois e so me pedir um servico que eu busco nas indicacoes da sua rede."
)

TEXTO_AJUDA = (
    "Posso te ajudar assim 🙂:\n"
    "- *Pedir um servico*: ex. \"preciso de um encanador em Perdizes\".\n"
    "- *Recomendar alguem*: digite *recomendar*.\n"
    "- *Adicionar contatos*: me manda os numeros das pessoas de confianca."
)

TEXTO_PEDIR_RECOMENDACAO = (
    "Que otimo! 🙌 Me manda numa mensagem so: o nome do prestador, o telefone "
    "(com DDD), o servico e o bairro.\n"
    "Ex: Joao, (11) 98888-7777, encanador, Perdizes.\n\n"
    "(Se quiser desistir, e so mandar *cancelar*.)"
)


# ===========================================================================
# A PORTA PRINCIPAL
# ===========================================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    texto_recebido = request.form.get("Body", "").strip()
    remetente = request.form.get("From", "")
    nome_perfil = request.form.get("ProfileName", "")
    wa_id = remetente.replace("whatsapp:", "")

    print(f"Mensagem de {wa_id} ({nome_perfil}): {texto_recebido}")

    membro = buscar_membro(wa_id)

    # CASO 1 - pessoa nova
    if membro is None:
        criar_membro(wa_id, nome_perfil)
        return resposta_whatsapp(TEXTO_BOAS_VINDAS)

    # CASO 2 - ja consentiu
    if membro["consent"]:
        texto_minusculo = texto_recebido.lower()
        estado = membro.get("estado") or "normal"

        # 2a) Esta no meio de uma recomendacao (Camada 6)?
        if estado == "recomendando":
            if texto_minusculo in ("cancelar", "sair", "parar"):
                definir_estado(wa_id, "normal")
                return resposta_whatsapp("Tudo bem, cancelei. 🙂\n\n" + TEXTO_AJUDA)
            return resposta_whatsapp(tratar_recomendacao(membro, texto_recebido))

        # 2b) Pediu pra recomendar alguem? Entra no modo recomendacao.
        if texto_minusculo in ("recomendar", "indicar", "recomendar alguem",
                               "recomendar um", "quero recomendar"):
            definir_estado(wa_id, "recomendando")
            return resposta_whatsapp(TEXTO_PEDIR_RECOMENDACAO)

        # 2c) Mandou numeros (sem ser recomendacao)? Tratamos como contatos (Camada 4).
        numeros = extrair_numeros_de_texto(texto_recebido)
        if numeros:
            total, ja_membros = processar_contatos(membro, numeros)
            return resposta_whatsapp(texto_contatos_recebidos(total, ja_membros))

        # 2d) Mandou uma frase? Tentamos entender como um pedido de servico.
        dados = extrair_servico_bairro(texto_recebido)
        servico = dados.get("servico", "").strip()
        bairro = dados.get("bairro", "").strip()

        if servico and bairro:
            return resposta_whatsapp(tratar_pedido_servico(membro, servico, bairro))
        if servico and not bairro:
            return resposta_whatsapp(
                f"Pra eu buscar certo, me diz tambem o bairro 🙂\n"
                f"Manda assim: \"{servico} em [bairro]\" (ex: \"{servico} em Perdizes\")."
            )
        # Nao parece pedido de servico nem contatos.
        return resposta_whatsapp(TEXTO_AJUDA)

    # CASO 3 - ainda nao consentiu
    texto = texto_recebido.lower()
    if texto in ("sim", "sim, bora", "bora", "s"):
        registrar_consentimento(wa_id)
        return resposta_whatsapp("Perfeito, anotei seu ok! ✅\n\n" + TEXTO_PEDIR_CONTATOS)
    if "saber" in texto or "mais" in texto:
        return resposta_whatsapp(TEXTO_SABER_MAIS)
    return resposta_whatsapp(TEXTO_PRECISA_CONSENTIR)


@app.route("/", methods=["GET"])
def home():
    return "A Doroteia esta viva! 🎉"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
