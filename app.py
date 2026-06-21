# app.py
# ---------------------------------------------------------------------------
# DOROTEIA - Camada 2/3: reconhecer a pessoa + boas-vindas + consentimento (7.1)
#
# O que este programa faz quando chega uma mensagem do WhatsApp:
#   1. Descobre QUEM mandou (pelo número do WhatsApp).
#   2. Se for alguem novo: cria o cadastro na tabela "members" e manda a
#      tela de boas-vindas pedindo o consentimento.
#   3. Se a pessoa responder SIM: grava o consentimento no banco.
#   4. Se responder SABER MAIS: explica melhor e repete a pergunta.
# ---------------------------------------------------------------------------

import os                                    # pra ler as "gavetas de segredos" (variaveis de ambiente)
from datetime import datetime, timezone      # pra registrar data/hora do consentimento
from html import escape                      # pra montar a resposta com seguranca (escapa caracteres especiais)

from flask import Flask, request, Response    # Flask = a ferramenta que cria o servidor
from supabase import create_client            # a "peca" que conversa com o banco no Supabase


# ---------------------------------------------------------------------------
# CONEXAO COM O BANCO (Supabase)
# Lemos a URL e a chave das variaveis de ambiente (que voce cadastrou no Render).
# Elas NUNCA ficam escritas aqui no codigo - so os NOMES das gavetas aparecem.
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]     # endereco do banco
SUPABASE_KEY = os.environ["SUPABASE_KEY"]     # chave secreta de acesso (fica so no Render)

# Cria o "cliente" do banco: o objeto pelo qual a gente le e escreve nas tabelas.
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cria a aplicacao web (o servidor).
app = Flask(__name__)


# ===========================================================================
# FUNCOES AUXILIARES (pequenas tarefas que o codigo reusa)
# ===========================================================================

def buscar_membro(wa_id):
    """Procura na tabela members a pessoa com aquele numero de WhatsApp.
    Devolve os dados dela, ou None se ainda nao existir."""
    resposta = supabase.table("members").select("*").eq("wa_id", wa_id).execute()
    if resposta.data:                 # se a lista veio com algo dentro...
        return resposta.data[0]       # ...devolve o primeiro (e unico) resultado
    return None                       # senao, a pessoa ainda nao esta cadastrada


def criar_membro(wa_id, nome_perfil):
    """Cria um cadastro novo na tabela members (ainda SEM consentimento)."""
    supabase.table("members").insert({
        "wa_id": wa_id,
        "nome_perfil": nome_perfil,
        "consent": False,             # comeca como "ainda nao deu o ok"
    }).execute()


def registrar_consentimento(wa_id):
    """Marca que a pessoa deu o 'ok' de privacidade, com a data/hora de agora."""
    agora = datetime.now(timezone.utc).isoformat()   # data/hora atual em formato padrao
    supabase.table("members").update({
        "consent": True,
        "consent_at": agora,
    }).eq("wa_id", wa_id).execute()


def resposta_whatsapp(texto):
    """Embrulha um texto no formato (TwiML) que a Twilio entende e devolve.
    O 'escape' troca caracteres especiais (como & < >) por versoes seguras."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escape(texto)}</Message>
</Response>"""
    return Response(twiml, mimetype="application/xml")


# ===========================================================================
# TEXTOS QUE A DOROTEIA FALA (roteiro 7.1 do briefing, adaptado para texto)
# Obs: o sandbox da Twilio nao permite botoes, entao usamos SIM / SABER MAIS.
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

TEXTO_CONSENTIMENTO_OK = (
    "Perfeito, anotei seu ok! ✅\n\n"
    "Por enquanto ainda estou aprendendo o resto - em breve vou te pedir os "
    "contatos de confianca e voce ja vai poder pedir servicos. 🙂"
)

TEXTO_PRECISA_CONSENTIR = (
    "Pra gente comecar, eu preciso do seu ok 🙂\n"
    "Responda *SIM* pra topar, ou *SABER MAIS* pra eu explicar."
)

TEXTO_JA_CADASTRADO = (
    "Oi de novo! Voce ja esta cadastrado(a) por aqui. 🙂\n"
    "Em breve vou poder te ajudar a pedir e recomendar servicos."
)


# ===========================================================================
# A PORTA PRINCIPAL: onde a Twilio bate quando chega uma mensagem
# ===========================================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    # Dados que a Twilio envia sobre a mensagem recebida:
    texto_recebido = request.form.get("Body", "").strip()        # o que a pessoa escreveu
    remetente = request.form.get("From", "")                     # vem como "whatsapp:+5511999999999"
    nome_perfil = request.form.get("ProfileName", "")            # nome do perfil no WhatsApp

    # "wa_id": tiramos o prefixo "whatsapp:" pra guardar so o numero limpo.
    wa_id = remetente.replace("whatsapp:", "")

    # Anota no log (sem expor nada sensivel alem do necessario pro beta).
    print(f"Mensagem de {wa_id} ({nome_perfil}): {texto_recebido}")

    # Procura a pessoa no banco.
    membro = buscar_membro(wa_id)

    # CASO 1 - pessoa nova: cadastra e manda as boas-vindas.
    if membro is None:
        criar_membro(wa_id, nome_perfil)
        return resposta_whatsapp(TEXTO_BOAS_VINDAS)

    # CASO 2 - ja cadastrada e JA deu o consentimento: cumprimenta.
    if membro["consent"]:
        return resposta_whatsapp(TEXTO_JA_CADASTRADO)

    # CASO 3 - ja cadastrada mas AINDA NAO consentiu: interpreta a resposta.
    texto = texto_recebido.lower()

    if texto in ("sim", "sim, bora", "bora", "s"):
        registrar_consentimento(wa_id)
        return resposta_whatsapp(TEXTO_CONSENTIMENTO_OK)

    if "saber" in texto or "mais" in texto:
        return resposta_whatsapp(TEXTO_SABER_MAIS)

    # Nao entendeu a resposta: pede o consentimento de novo, com gentileza.
    return resposta_whatsapp(TEXTO_PRECISA_CONSENTIR)


# ===========================================================================
# Rota extra: abrir o endereco principal no navegador confirma "estou no ar".
# ===========================================================================
@app.route("/", methods=["GET"])
def home():
    return "A Doroteia esta viva! 🎉"


# So roda quando executado no nosso proprio computador (no Render quem sobe e o gunicorn).
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
