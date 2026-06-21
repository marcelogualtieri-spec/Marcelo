# app.py
# ---------------------------------------------------------------------------
# ESQUELETO DO BOT
# Recebe uma mensagem do WhatsApp (que chega pela Twilio) e responde "oi".
# Por enquanto é só isso — sem banco de dados, sem inteligência artificial.
# A ideia é provar que a tubulação funciona de ponta a ponta.
# ---------------------------------------------------------------------------

from flask import Flask, request, Response  # Flask = a ferramenta que cria o nosso "servidor"

# Cria a aplicação web (o nosso servidor). É como ligar o motor.
app = Flask(__name__)


# Uma "rota" é um endereço DENTRO do servidor (como um cômodo de uma casa).
# Aqui dizemos: quando a Twilio bater no endereço "/webhook" usando o método POST,
# execute a função logo abaixo.
@app.route("/webhook", methods=["POST"])
def webhook():
    # A Twilio nos envia os dados da mensagem que a pessoa mandou.
    # "Body" é o texto digitado; "From" é o número de quem enviou.
    mensagem_recebida = request.form.get("Body", "")
    remetente = request.form.get("From", "")

    # Imprime no "log" (um diário do servidor) só pra gente acompanhar o que chegou.
    print(f"Mensagem recebida de {remetente}: {mensagem_recebida}")

    # A resposta para a Twilio é um pequeno texto em formato XML, chamado TwiML.
    # A linha <Message>oi</Message> significa: "responda 'oi' para quem mandou".
    resposta_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>oi</Message>
</Response>"""

    # Devolvemos esse XML para a Twilio, que o transforma na mensagem de WhatsApp.
    return Response(resposta_twiml, mimetype="application/xml")


# Uma rota extra, só pra testar no navegador: ao abrir o endereço principal ("/"),
# o servidor responde uma frase. Serve pra confirmar "o programa está no ar".
@app.route("/", methods=["GET"])
def home():
    return "O bot esta vivo! 🎉"


# Este bloco só roda quando executamos o programa no nosso próprio computador.
# Lá no Render (a hospedagem), quem liga o servidor é outra ferramenta (gunicorn),
# então este trecho é ignorado em produção. É uma rede de segurança.
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
