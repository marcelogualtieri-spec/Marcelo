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
# Mensagem FIXA de boas-vindas / consentimento. Enviada exatamente assim no
# primeiro contato (o {link} vira o endereco dos Termos de Uso e Privacidade).
BOAS_VINDAS = (
    "Oi! Eu sou a Doroteia 💛\n\n"
    "Encontre profissionais recomendados por quem você confia, sem a bagunça dos "
    "grupos de WhatsApp ou recomendações suspeitas em sites de busca e redes sociais.\n\n"
    "1️⃣ 🔍 *Indicações de confiança:* busco profissionais já testados pelos seus "
    "contatos — os que você convidar ou os que já estão por aqui.\n\n"
    "2️⃣ 🤝 *Troca:* peça dicas de profissionais, recomende quem trabalha bem e "
    "convide a sua rede.\n\n"
    "3️⃣ 🔒 *Privacidade:* guardo só o seu nome e telefone. Os contatos que você "
    "escolher conectar formam a sua agenda, e só quem se conecta com você vê o seu "
    "nome. Para sair da rede, é só digitar *SAIR*.\n\n"
    "🔗 *Termos de Uso:*\n{link}\n\n"
    "Posso começar a te ajudar? Responda *SIM* para aceitar os termos e iniciar, ou "
    "digite *SABER MAIS*."
)

SABER_MAIS = (
    "Claro, deixa eu explicar com calma 💛\n\n"
    "A Doroteia é uma central de indicações de confiança: você pede um profissional "
    "(médico, encanador, professor...) e eu busco entre as recomendações de quem você "
    "conhece — nada de grupo de WhatsApp ou site duvidoso.\n\n"
    "*Privacidade:* guardo só o seu nome e telefone. A sua agenda de confiança fica "
    "embaralhada em código, e só quem se conecta com você vê o seu nome. Para sair, é "
    "só digitar *SAIR*.\n\n"
    "💼 *Você também presta algum serviço?* Dá para ter um perfil profissional aqui. Só "
    "lembre: um profissional só é encontrado quando está ligado a alguém do lado cliente "
    "— quanto mais clientes indicarem você, maior a chance de aparecer.\n\n"
    "Topa começar? Responda *SIM* para aceitar os termos. 🙂"
)

PRECISA_CONSENTIR = (
    "Pra gente comecar com o pe direito, preciso so do seu \"pode ser\" 💛\n"
    "Responde *SIM* pra topar, ou *SABER MAIS* se quiser entender melhor."
)

CONSENTIMENTO_OK = "Que bom ter voce comigo{voc}! 💛 Anotei seu ok.\n\n"


# --- Contatos (telas 7.2 / 7.3) ------------------------------------------
PEDIR_CONTATOS = (
    "Agora vamos te deixar bem servido(a) 🙌\n\n"
    "Me manda os contatos das pessoas em quem voce confia - "
    "a forma mais facil e pelo clipe 📎 do WhatsApp (\"Contato\"). "
    "Pode mandar varios de uma vez!\n\n"
    "Prefere digitar? Manda os numeros com DDD, um por linha ou separados por virgula:\n"
    "Ex: (11) 99999-8888, (11) 98888-7777\n\n"
    "Quanto mais gente da sua confianca, melhor. 💛"
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
    "Pra eu acertar em cheio, me diz o bairro e a cidade 🙂\n"
    "Ex.: \"{servico} em Perdizes, Sao Paulo\" ou \"{servico} em Savassi, BH\"."
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
    "Claro! Compartilhe o contato pelo clipe 📎 do WhatsApp "
    "ou escreva o numero com DDD:\n"
    "Ex: (11) 99999-8888\n\n"
    "(Prefere um link pra divulgar pra varias pessoas? "
    "Escolha *Meu link geral* abaixo.)"
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
    "indicacoes de confianca - medico, escola, encanador, o que voce precisar. "
    "Pra entrar (e ja ficar ligado comigo), e so abrir aqui: {link}"
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
    "Como posso te ajudar agora{voc}? 😊\n"
    "Escolha uma opcao abaixo ou ja escreva o que voce precisa. 💛"
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
    "Quer apagar tudo? Escolha nos botoes abaixo. 👇"
)

EXCLUSAO_CONFIRMAR = "Pra apagar tudo, digite *EXCLUIR*. Pra voltar, e so mandar *cancelar*. 🙂"
EXCLUSAO_CANCELADA = "Ufa, nao apaguei nada! 😌 Esta tudo no lugar."
ADEUS = (
    "Pronto, apaguei tudo certinho 💛 Foi um prazer te ajudar!\n"
    "Se um dia quiser voltar, é só me mandar um oi que a gente recomeça. 👋"
)

# --- Prestador de servico (Fase 3) ---------------------------------------
PRESTADOR_ACOLHIDA = (
    "Olá! 💼 Um contato que confia no seu trabalho indicou você para fazer parte da "
    "Doroteia.\n\n"
    "A Doroteia é uma central que conecta quem precisa de um serviço a pessoas "
    "especialistas — como você em *{servico}*. Quando alguém da rede precisar e receber "
    "a sua indicação, o seu contato vai só para essa pessoa. Ninguém te manda mensagem "
    "por aqui.\n\n"
    "Para ativar o seu cadastro, preciso da sua autorização para usar o seu contato e a "
    "categoria do serviço, conforme os Termos de Uso. Os seus dados serão usados apenas "
    "para conectar você a quem busca o seu trabalho.\n\n"
    "Deseja prosseguir?"
)

PRESTADOR_AJUSTAR = (
    "Claro! Qual é a categoria certa do seu serviço? "
    "Ex.: encanador, eletricista, pediatra, professor de inglês..."
)

PRESTADOR_NAO = (
    "Tudo bem, sem problema! 💛 Não vou ativar o seu cadastro e o seu contato não será "
    "repassado a ninguém pela rede. Se mudar de ideia, é só voltar por aqui."
)

PRESTADOR_REFINAMENTO = (
    "Perfeito, cadastro ativo! 🚀 Agora você faz parte da nossa rede de confiança.\n\n"
    "Para que os pedidos certos cheguem até você, me conte um pouco mais (pode enviar "
    "tudo em um único texto):\n"
    "1️⃣ *Região de atendimento* — toda São Paulo ou bairros específicos?\n"
    "2️⃣ *Diferenciais* — o que destaca o seu trabalho? Formas de pagamento, redes "
    "sociais...\n"
    "3️⃣ *Como você trabalha* — conte um pouco sobre o seu atendimento.\n\n"
    "Quando terminar, é só digitar *MENU* para ver as opções."
)

PRESTADOR_PERFIL_OK = (
    "Prontinho, perfil atualizado! 💼💛 Já está tudo certo para você ser recomendado.\n"
    "A qualquer momento, digite *MENU* para ajustar o seu perfil ou alternar entre as "
    "visões de cliente e profissional."
)


# --- Saida (exclusao) diferenciada por perfil ----------------------------
SAIR_CLIENTE = (
    "Tem certeza de que deseja sair? 💛\n\n"
    "Ao confirmar, o seu acesso à central de indicações será encerrado e as suas "
    "conexões serão removidas permanentemente. Você poderá voltar um dia, mas perderá "
    "todo o histórico.\n\n"
    "Se quiser explicar o que aconteceu e pedir ajuda, digite *AJUDA* e conte para nós "
    "o que houve."
)

SAIR_PROFISSIONAL = (
    "Tem certeza de que deseja sair? 💛\n\n"
    "Ao confirmar, o seu perfil de profissional de confiança será removido e você "
    "deixará de ser recomendado para novas demandas da rede. Essa ação é permanente.\n\n"
    "Se quiser explicar o que aconteceu e pedir ajuda, digite *AJUDA* e conte para nós "
    "o que houve."
)

SAIR_HIBRIDO = (
    "Tem certeza de que deseja sair? 💛\n\n"
    "Você tem os dois perfis aqui. Ao sair de tudo, todo o histórico será removido: você "
    "perderá o acesso à rede de indicações e o seu perfil profissional não será mais "
    "recomendado.\n\n"
    "Se preferir, você pode ficar só com um dos perfis. O que deseja fazer?\n\n"
    "Se quiser explicar o que aconteceu e pedir ajuda, digite *AJUDA* e conte para nós "
    "o que houve."
)


# --- Rede de seguranca (qualquer erro inesperado) ------------------------
ERRO_GENERICO = (
    "Opa, tivemos um probleminha aqui do meu lado 😅\n"
    "Pode tentar de novo daqui a pouquinho, por favor? Se continuar, é só mandar "
    "*menu* que a gente recomeça. 💛"
)
