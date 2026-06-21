# textos.py
# ===========================================================================
# TODAS AS FALAS DA DOROTEIA FICAM AQUI.
# Pode editar as PALAVRAS a vontade, sem medo! 💛
#
# So nao apague os "encaixes" entre chaves { }, porque eles sao preenchidos
# pela Doroteia na hora de enviar:
#   {voc}      -> vira ", Marcelo" quando sabemos o nome (ou nada, se nao soubermos)
#   {nome}     -> nome do prestador (nas recomendacoes/resultados)
#   {quem}     -> nome de quem indicou (no resultado verde)
#   {servico}  -> ex: "Encanador"
#   {bairro}   -> ex: "Perdizes"
#   {telefone} -> telefone do prestador
#   {link}     -> link de convite
#   {total} {ja} {rest} {n} -> numeros
# ===========================================================================

# Rodape discreto, anexado ao fim das respostas de resultado.
RODAPE = "\n\n_Dica: e so digitar *menu* quando quiser ver tudo que eu faco._"


# --- Onboarding e consentimento (tela 7.1) -------------------------------
BOAS_VINDAS = (
    "Oi{voc}! 💛 Eu sou a Doroteia.\n\n"
    "Sabe aquela amiga que sempre tem a indicacao certa na ponta da lingua? "
    "Entao, e esse o meu papel - so que aqui dentro do WhatsApp.\n\n"
    "Voce me conta o que precisa (tipo \"preciso de um encanador em Perdizes\") "
    "e eu te digo quem *da sua confianca* ja indicou alguem bom.\n\n"
    "Antes da gente comecar, so preciso do seu \"pode ser\":\n"
    "- Seu nome so aparece como quem indicou pra quem ja e seu contato aqui.\n"
    "- Voce nunca recebe mensagem de quem voce nao chamou.\n"
    "- Seu telefone fica so com voce - nunca passo pra ninguem.\n\n"
    "Combinado? Responde *SIM* que a gente comeca, ou *SABER MAIS* se quiser "
    "que eu explique com calma. 🙂"
)

SABER_MAIS = (
    "Claro, fico feliz em explicar 💛\n\n"
    "- *Sua privacidade vem primeiro:* a ligacao entre voce e seus contatos eu "
    "guardo de um jeito embaralhado - ninguem, nem eu, ve os numeros.\n"
    "- *Seu telefone* nunca e repassado pra ninguem.\n"
    "- Voce so recebe mensagem se chamar primeiro ou entrar por um convite.\n"
    "- Cansou? E so pedir que eu apago tudo na hora.\n\n"
    "Topa comecar? Responde *SIM*. 🙂"
)

PRECISA_CONSENTIR = (
    "Pra gente comecar com o pe direito, preciso so do seu \"pode ser\" 💛\n"
    "Responde *SIM* pra topar, ou *SABER MAIS* se quiser entender melhor."
)

CONSENTIMENTO_OK = "Que bom ter voce comigo{voc}! 💛 Anotei seu ok.\n\n"


# --- Contatos (telas 7.2 / 7.3) ------------------------------------------
PEDIR_CONTATOS = (
    "Agora vamos te deixar bem servido(a) 🙌\n\n"
    "Me manda os numeros das pessoas em quem voce confia - pode ser um por "
    "linha ou separados por virgula. (Por enquanto, na fase de testes, manda "
    "em texto mesmo.)\n"
    "Ex: (11) 99999-8888, (11) 98888-7777\n\n"
    "Quanto mais gente da sua confianca, melhor: assim, quando voce pedir um "
    "servico, eu ja sei em quem me apoiar. 💛"
)

CONTATOS_CABECALHO = "Recebi {total} contato(s), obrigada por confiar! 🙌\n\n"
CONTATOS_TEM_MEMBROS = ("Desses, {ja} ja estao aqui comigo - entao as indicacoes "
                        "deles ja chegam pra voce com nome. 💛\n")
CONTATOS_SEM_MEMBROS = ("Nenhum deles entrou ainda, mas relaxa: assim que "
                        "entrarem, as indicacoes aparecem sozinhas. 😉\n")
CONTATOS_RESTANTES = ("\nOs outros {rest} ainda nao chegaram. Daqui a pouco te "
                      "dou um link pra chamar. 💛")


# --- Pedido de servico (tela 7.5) ----------------------------------------
PEDIR_BAIRRO = (
    "Pra eu acertar em cheio, me diz tambem o bairro 🙂\n"
    "Manda assim: \"{servico} em [bairro]\" (ex.: \"{servico} em Perdizes\")."
)

VERDE_CABECALHO = "Achei pra voce{voc}! 💛 {servico} em {bairro}:\n"
VERDE_LINHA = "- *{nome}* - indicado por {quem} (do seu contato)\n  📞 {telefone}"
VERDE_RODAPE = "\n\nQualquer coisa, e so me chamar! 😊"

AMARELO_CABECALHO = (
    "Na sua rede direta ainda ninguem indicou {servico} em {bairro}, mas nao "
    "fica triste 💛\n"
    "Tenho {n} indicacao(oes) bem avaliada(s) (nao posso dizer quem indicou):\n"
)
AMARELO_LINHA = "- *{nome}* - 📞 {telefone}"
AMARELO_RODAPE = ("\n\nDica: chame mais gente da sua confianca que essas "
                  "indicacoes passam a aparecer com nome. 😉")

VERMELHO = (
    "Ainda nao tenho {servico} indicado em {bairro} 😕\n"
    "Mas voce pode ajudar: conhece alguem bom? Me indica! Manda o numero, o "
    "servico e o bairro - assim voce fortalece a rede da galera. 💛"
)


# --- Recomendar (tela 7.6) -----------------------------------------------
PEDIR_RECOMENDACAO = (
    "Aaah, que generoso(a) da sua parte 💛 Manda numa mensagem so: o nome do "
    "prestador, o telefone (com DDD), o servico e o bairro.\n"
    "Ex: Joao, (11) 98888-7777, encanador, Perdizes.\n\n"
    "(Mudou de ideia? E so mandar *cancelar*.)"
)

REC_INCOMPLETA = (
    "Acho que faltou um detalhezinho 😅 Me manda tudo numa mensagem so: nome, "
    "telefone (com DDD), servico e bairro.\n"
    "Ex: Joao, (11) 98888-7777, encanador, Perdizes.\n"
    "(ou *cancelar* pra deixar pra depois)"
)

REC_OK = (
    "Anotado com carinho: *{nome}*, {servico} em {bairro}! ✅\n\n"
    "Quando alguem da sua rede precisar disso, sua indicacao aparece pra essa "
    "pessoa (com seu nome, so pra ela). Valeu por ajudar a turma{voc}! 🙏"
)

REC_CANCELADA = "Tudo bem, deixamos pra depois 🙂"


# --- Convite (tela 7.4) --------------------------------------------------
CONVITE = (
    "Que ideia boa chamar mais gente 💛 Manda esse link pra quem voce confia:\n"
    "{link}\n\n"
    "Quando a pessoa entra por ele, voces ja ficam ligados aqui - e as "
    "indicacoes de voces passam a aparecer um pro outro. 🤝"
)

# Pediu pra convidar: perguntamos o numero da pessoa.
CONVIDAR_PEDIR_NUMERO = (
    "Claro! Voce pode *compartilhar o contato* da pessoa aqui (pelo clipe 📎 do "
    "WhatsApp) ou simplesmente *digitar o numero* com DDD - que eu preparo tudo 🙂\n"
    "Ex: (11) 99999-8888\n\n"
    "(Prefere um link pra divulgar pra varias pessoas? Digite *link*. "
    "Pra desistir, *cancelar*.)"
)

CONVIDAR_NUMERO_INVALIDO = (
    "Hmm, nao consegui pegar o numero 🤔 Voce pode compartilhar o contato da "
    "pessoa (pelo clipe 📎) ou digitar com DDD, ex: (11) 99999-8888.\n"
    "(ou *cancelar* pra desistir)"
)

# Quando a pessoa compartilha varios contatos de uma vez.
CONVITE_EXTRAS = (
    "\n\n(Tambem ja conectei voce com os outros {qtd} contato(s) que voce mandou - "
    "quando eles entrarem, voces se reconhecem aqui. 💛)"
)

# A mensagem que VOCE vai enviar pra pessoa (ela recebe isso).
CONVITE_MENSAGEM_AMIGO = (
    "Oi! 💛 Te indico a Doroteia: um cantinho no WhatsApp que recomenda "
    "prestadores de servico de confianca. Pra entrar (e ja ficar ligado comigo), "
    "e so abrir aqui: {link}"
)

# O que a Doroteia te responde, com o link que abre a conversa com a pessoa.
CONVITE_PRONTO = (
    "Prontinho! 🙌 Ja deixei voce e essa pessoa conectados - quando ela entrar, "
    "voces aparecem um pro outro automaticamente.\n\n"
    "Agora e um toque so: abra o link abaixo (vai abrir a conversa com ela, com o "
    "convite ja escrito) e toque em *Enviar*. 💛\n{link}"
)


# --- Menu, ajuda, saudacao, agradecimento --------------------------------
MENU = (
    "Como posso te ajudar agora{voc}? 😊\n\n"
    "*1* - Pedir um servico (ex.: \"encanador em Perdizes\")\n"
    "*2* - Recomendar alguem\n"
    "*3* - Convidar alguem\n"
    "*4* - Meus dados / sair\n\n"
    "E so responder com o numero - ou ja escrever o que voce precisa. 💛"
)

PEDIR_SERVICO = (
    "Claro{voc}! Me conta o que voce precisa e em qual bairro - "
    "ex.: \"encanador em Perdizes\". 😊"
)

AJUDA = (
    "Posso te ajudar de alguns jeitos 💛\n\n"
    "- *Pedir um servico* - ex.: \"preciso de um encanador em Perdizes\"\n"
    "- *Recomendar* alguem - digite *recomendar*\n"
    "- *Convidar* alguem - digite *convidar*\n"
    "- Me mandar os *numeros* das pessoas de confianca"
)

SAUDACAO = (
    "Oi{voc}! Que bom te ver por aqui 💛\n"
    "Ja me conta o que voce precisa, ou digite *menu* pra ver as opcoes. 😊"
)

AGRADECIMENTO = (
    "Imagina{voc}, to aqui pra isso 💛\n"
    "Se precisar de mais alguma coisa, e so me chamar!"
)


# --- Meus dados e exclusao (tela 7.7 / LGPD) -----------------------------
MEUS_DADOS = (
    "📋 *Seus dados aqui comigo{voc}:*\n"
    "- Nome: {nome}\n"
    "- Voce topou participar: {consent}\n"
    "- Contatos no seu circulo (guardados em codigo, nunca o numero): {n_contatos}\n"
    "- Indicacoes que voce fez: {n_indicacoes}\n\n"
    "Pode ficar tranquilo(a): eu nunca guardo o numero dos seus contatos, so um "
    "codigo embaralhado. 🔒\n\n"
    "Quer que eu apague *tudo*? Digite *EXCLUIR*. Se preferir voltar, e so mandar "
    "*cancelar*."
)

EXCLUSAO_CONFIRMAR = "Pra apagar tudo, digite *EXCLUIR*. Pra voltar, e so mandar *cancelar*. 🙂"
EXCLUSAO_CANCELADA = "Ufa, nao apaguei nada! 😌 Esta tudo no lugar."
ADEUS = (
    "Pronto, apaguei tudo certinho 💛 Foi um prazer te ajudar!\n"
    "Se um dia quiser voltar, e so me mandar um oi que a gente recomeca. 👋"
)

# --- Rede de seguranca (qualquer erro inesperado) ------------------------
ERRO_GENERICO = (
    "Opa, deu um probleminha aqui do meu lado 😅\n"
    "Tenta de novo daqui a pouquinho, por favor? Se continuar, e so mandar "
    "*menu* que a gente recomeca. 💛"
)
