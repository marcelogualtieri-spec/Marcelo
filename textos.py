# textos.py
# ===========================================================================
# TODAS AS FALAS DA DOROTEIA FICAM AQUI.
# Pode editar as PALAVRAS a vontade, sem medo! 💛
#
# So nao apague os "encaixes" entre chaves { }, porque eles sao preenchidos
# pela Dorote.ia na hora de enviar:
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
    "Oi! Sou a Dorote.ia 💛\n"
    "Central de indicações de confiança — organizada, sem grupo confuso e sem avaliação paga.\n\n"
    "🔎 Busque: especialistas sob recomendação de quem você confia ou da nossa rede qualificada.\n"
    "📣 Indique: traga quem presta um serviço de excelência.\n"
    "✉️ Convide: quanto mais gente de confiança, melhores as indicações.\n\n"
    "✓ Rede exclusiva: a curadoria é sua! Só se conecta a você quem você aprovar.\n"
    "🔒 Privacidade: só quem você libera tem acesso ao seu contato — registramos apenas seu nome e telefone.\n\n"
    "📄 Aceite os Termos para começar: {link}"
)

# Boas-vindas de quem chega POR UM CONVITE PESSOAL. Deixa claro que, ao entrar por
# este convite, a pessoa já está se conectando com quem convidou (é o consentimento
# do vínculo). {nome} = primeiro nome de quem convidou; {link} = termos.
BOAS_VINDAS_CONVIDADO = (
    "Oi! {nome} te indicou para fazer parte da Dorote.ia — Central de indicações de "
    "confiança, organizada, sem grupo confuso e sem avaliação paga.\n\n"
    "🔎 Busque: especialistas sob recomendação de quem você confia ou da nossa rede qualificada.\n"
    "📣 Indique: traga quem presta um serviço de excelência.\n"
    "✉️ Convide: quanto mais gente de confiança, melhores as indicações.\n\n"
    "✓ Rede exclusiva: a curadoria é sua! Só se conecta a você quem você aprovar.\n"
    "🔒 Privacidade: só quem você libera tem acesso ao seu contato — registramos apenas seu nome e telefone.\n\n"
    "📄 Aceite os Termos para começar: {link}"
)

# Enviada COM BOTÕES (SIM, aceito · Quero ser prof. · Deixa pra depois).
# O {link} vira o endereço dos Termos de Uso do cliente.
SABER_MAIS = (
    "A Dorote.ia é uma central de indicações de confiança: você pede um profissional — "
    "médica, encanador, professora — e a busca traz quem sua rede já indicou ou "
    "recomendações qualificadas de outros membros.\n\n"
    "Sem grupo de WhatsApp confuso, sem indicação duvidosa.\n\n"
    "🔒 Privacidade: registramos seu nome e telefone. Seus contatos ficam protegidos e seu "
    "nome só aparece para quem você aprovar. Para sair a qualquer momento, digite SAIR.\n\n"
    "Você também presta algum serviço? Depois de entrar, é só ativar seu perfil profissional pelo menu.\n\n"
    "📄 Para continuar, leia e aceite os termos de uso: {link}"
)

# Caminho profissional — escolha entre os dois perfis ou só o profissional.
PROF_ESCOLHA = (
    "💼 Que ótimo que você presta um serviço!\n\n"
    "Aqui você pode ter os dois perfis — *cliente* (para pedir indicações de confiança) "
    "e *profissional* (para ser recomendado) — ou apenas o perfil *profissional*.\n\n"
    "Como você prefere começar?"
)

# Perfil DUAL: aceita os dois termos (cliente + profissional).
PROF_DUAL = (
    "Perfeito! Você terá os dois perfis: *cliente* e *profissional*. 💛💼\n\n"
    "Para começar, é só conferir e aceitar os dois termos de uso:\n\n"
    "📄 Termos do cliente:\n{link_cli}\n\n"
    "📄 Termos do profissional:\n{link_prof}\n\n"
    "Ao tocar em *Aceito os dois*, você confirma que leu e concorda com ambos."
)

# Apenas PROFISSIONAL: aceita só os termos do profissional.
PROF_SO = (
    "Perfeito! Você terá o perfil *profissional*. 💼\n\n"
    "Para começar, é só conferir e aceitar os termos de uso do profissional:\n\n"
    "📄 Termos do profissional:\n{link_prof}\n\n"
    "Ao tocar em *Aceito os termos*, você confirma que leu e concorda."
)

# Deixar para outro momento (antes do aceite).
ADIAR = (
    "Tudo bem, sem pressa. 💛 Quando quiser começar, é só me mandar um oi. "
    "Vou estar à disposição."
)

PRECISA_CONSENTIR = (
    "Antes de seguir, preciso do seu aceite nos Termos de uso. 💛"
)

CONSENTIMENTO_OK = "Que bom ter voce comigo{voc}! 💛 Anotei seu ok.\n\n"


# --- Fluxo: o CLIENTE indica um profissional --------------------------------
# Regra de ouro: o profissional só é indicado depois de CONSENTIR. Ao final, a
# Dorote.ia gera um link de convite; a indicação só passa a valer quando o
# profissional entra, aceita os termos e o cliente confirma que se conhecem.
INDICAR_INICIO = (
    "Que bom! Quem você quer indicar? 💛\n\n"
    "Toque no clipe 📎 (ou no ➕) e envie o contato dessa pessoa.\n\n"
    "Se preferir, escreva aqui o nome e o telefone — assim: (11) 98765-4321.\n\n"
    "Pode mandar do seu jeito, depois eu confirmo. 💛"
)

INDICAR_PEDIR_TELEFONE = (
    "Quase lá! 💛 Só me falta o celular dessa pessoa, com DDD.\n"
    "Ex.: (11) 99999-8888 — ou toque no clipe 📎 e compartilhe o contato."
)

INDICAR_DETALHES = (
    "Anotei: *{nome}*! 💛\n\n"
    "Agora me conta em uma mensagem, como se estivesse indicando num grupo:\n\n"
    "🔧 O que essa pessoa faz? (ex.: eletricista, manicure, aulas de inglês)\n\n"
    "📍 Em que parte de São Paulo atende? (um bairro, vários, a cidade toda — ou \"não sei\")\n\n"
    "💬 Por que você indica? Isso ajuda muito quem procura. "
    "(ex.: \"fez os doces do batizado, caprichou e foi pontual; também faz salgados\")\n\n"
    "Pode escrever do seu jeito 💛"
)

INDICAR_VALIDAR = (
    "Confere pra mim? 💛\n\n"
    "👤 {nome}\n"
    "🔧 {servico}\n"
    "📍 {bairro}\n"
    "💬 \"{detalhe}\"\n\n"
    "_Em Corrigir você pode ajustar o nome. O nome final será o que essa pessoa "
    "confirmar ao entrar na Dorote.ia._"
)

# Mensagem 1 (curta): instrução. A linha editável vai numa mensagem SEPARADA
# (INDICAR_CORRIGIR_LINHA), para a pessoa copiar só os dados, sem a instrução.
INDICAR_CORRIGIR = (
    "Sem problema 💛 Confira os dados que você quer registrar. É só copiar a mensagem "
    "abaixo, ajustar o que precisar e me reenviar:"
)
INDICAR_CORRIGIR_LINHA = "{nome} · {servico} · {bairro} · {detalhe}"

INDICAR_LINK = (
    "Prontinho! 💛 É só tocar no link abaixo para enviar o convite direto para *{nome}* — "
    "a conversa já abre com a mensagem pronta, você só toca em *Enviar*:\n\n"
    "{link}\n\n"
    "Quando *{nome}* entrar e aceitar, vou chamar vocês dois para confirmar que se "
    "conhecem — aí a sua indicação passa a valer na rede. 💛"
)

# Mensagem que JÁ VAI ESCRITA na conversa com o profissional (o {link} é o convite
# que abre a Dorote.ia para ele entrar como profissional).
PRESTADOR_CONVITE_MENSAGEM = (
    "Oi! 💛 Te indiquei na Dorote.ia, uma central de indicações de confiança no WhatsApp. "
    "Entra pelo meu convite para você ser recomendado e a gente se conectar por aqui:\n\n"
    "{link}"
)

# Mensagem enviada AO CLIENTE quando a pessoa indicada entra e aceita os termos.
INDICAR_CONFIRMA_CLIENTE = (
    "Boa notícia! 💛 *{nome}*, que você indicou, entrou na Dorote.ia.\n\n"
    "Vocês se conhecem e você confia no trabalho dessa pessoa?"
)

INDICAR_CONFIRMADA = (
    "Perfeito! 💛 A sua indicação de *{nome}* agora vale na rede. Quando alguém da sua "
    "rede precisar desse serviço, a sua recomendação aparece com o seu nome."
)

INDICAR_NEGADA = (
    "Tudo bem, obrigada por avisar! 💛 Não vou registrar essa indicação, e o contato "
    "dessa pessoa não fica ligado a você."
)

# --- Avaliação determinística (por botões — a IA nunca dá nota) --------------
AVALIAR_USOU = (
    "Uma perguntinha rápida 💛\n\n"
    "Você chegou a usar a indicação de *{nome}* ({servico})?"
)

AVALIAR_NOTA = (
    "Que bom! 💛 De 1 a 5, que nota você dá para *{nome}*?\n"
    "Toque para escolher."
)

AVALIAR_OBRIGADA = (
    "Obrigada! 💛 A sua nota ajuda essa indicação a chegar com mais força para quem "
    "precisar do mesmo serviço."
)

AVALIAR_AINDA = (
    "Sem problema! 💛 Quando você usar, é só me contar — quero saber como foi."
)


# --- Conexão mútua (os dois confirmam que se conhecem — §6/§7.5) -------------
# Pergunta enviada a QUEM CONVIDOU quando a pessoa convidada entra.
CONEXAO_PERGUNTA_CONVIDOU = (
    "Boa notícia! 💛 *{nome}*, que você convidou, entrou na Dorote.ia.\n\n"
    "Vocês se conhecem?"
)

# Pergunta enviada a QUEM ENTROU (pelo convite de cliente).
CONEXAO_PERGUNTA_ENTROU = (
    "*{nome}* convidou você para a Dorote.ia 💛\n\n"
    "Vocês se conhecem?"
)

# Pergunta enviada a QUEM FOI INDICADO como profissional (o outro lado da indicação).
CONEXAO_PERGUNTA_PROF = (
    "*{nome}* indicou o seu trabalho aqui na Dorote.ia 💛\n\n"
    "Vocês se conhecem?"
)

# Aviso a QUEM ENTROU por um convite pessoal: não precisa confirmar de novo (entrar já
# foi o consentimento do vínculo); só falta quem convidou confirmar.
CONEXAO_ENTROU_LIGADO = (
    "Você entrou pelo convite de *{nome}* 💛\n\n"
    "Já avisei {nome} que você entrou. Assim que {nome} confirmar que vocês se conhecem, "
    "vocês passam a trocar indicações na rede."
)

CONEXAO_VALIDADA = (
    "Pronto! 💛 Vocês confirmaram que se conhecem. Agora as indicações de vocês "
    "aparecem com o nome um do outro para a rede de confiança."
)

CONEXAO_AGUARDA_OUTRO = (
    "Obrigada! 💛 Assim que a outra pessoa também confirmar, a conexão de vocês fica "
    "completa."
)

CONEXAO_RECUSADA = (
    "Tudo bem, obrigada por avisar! 💛 Não vou registrar essa conexão."
)

# Limite diário de indicações/convites atingido (§10 — anti-spam).
LIMITE_INDICACOES = (
    "Você já fez muitas indicações hoje 💛 Para manter a rede saudável, dá uma pausinha "
    "e continue amanhã. Obrigada por fortalecer a confiança por aqui!"
)


# Regra: ninguém indica o próprio número como profissional.
INDICAR_SI_MESMO = (
    "Esse é o seu próprio contato 😊\n\n"
    "Para aparecer como profissional, use a opção *Quero ser profissional*. "
    "Para indicar, me envie o contato de *outra* pessoa em quem você confia. 💛"
)


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

# Mensagem 2 — texto pronto para encaminhar (o que a outra pessoa recebe).
# Sai pré-escrito na conversa com a pessoa convidada (dinâmica do clipe 📎 / link wa.me).
CONVITE_MENSAGEM_AMIGO = (
    "Oi! 💛 Tô usando a Dorote.ia, a central de indicações de confiança no WhatsApp. "
    "Serve para achar gente boa — dentista, eletricista, reforço escolar... — indicada por "
    "quem confiamos, sem a bagunça dos grupos ou indicação paga.\n\n"
    "Entre pelo meu convite pessoal para trocarmos indicações:\n\n{link}"
)

# Mensagem 1 — o que a Dorote.ia entrega para quem está convidando (perfil CLIENTE
# trazendo outra pessoa de confiança para a rede). Não confundir com indicar um
# profissional (esse é outro fluxo, com outro link).
CONVIDAR_CLIENTE_VOCE = (
    "Compartilhe a mensagem abaixo 👇 O link conecta você a quem você confia. 💛"
)

# O que a Dorote.ia te responde, com o link que abre a conversa com a pessoa.
CONVITE_PRONTO = (
    "Pronto! 💛 Toque no link abaixo pra abrir o convite com essa pessoa — "
    "é só enviar.\n\n{link}"
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
    "- Contatos no seu círculo (guardados com segurança, sem expor o número): {n_contatos}\n"
    "- Indicações que você fez: {n_indicacoes}\n\n"
    "Pode ficar tranquilo(a): os números dos seus contatos ficam protegidos e nunca "
    "são compartilhados. 🔒\n\n"
    "Quer apagar tudo? Escolha nos botoes abaixo. 👇"
)

EXCLUSAO_CONFIRMAR = "Pra apagar tudo, digite *EXCLUIR*. Pra voltar, e so mandar *cancelar*. 🙂"
EXCLUSAO_CANCELADA = "Ufa, nao apaguei nada! 😌 Esta tudo no lugar."
ADEUS = (
    "Pronto, sua conta foi apagada 💛 Apaguei o seu cadastro e o seu nome.\n"
    "As indicações que você fez continuam ajudando a rede, mas de forma anônima "
    "(sem o seu nome).\n"
    "Se um dia quiser voltar, é só me mandar um oi que a gente recomeça. 👋"
)

# --- Pos-consentimento e menus do cliente novo ---------------------------
CLIENTE_ATIVO = (
    "Tudo pronto! 🎉 O seu cadastro na Dorote.ia está ativo.\n\n"
    "Você faz parte da central de indicações de confiança. Como a nossa rede cresce "
    "através das conexões, o que deseja fazer primeiro?"
)

# --- Bloquear / gerenciar a rede (§7) ---------------------------------------
BLOQUEAR_OK = (
    "Pronto, *{nome}* foi bloqueado. 💛\n"
    "Vocês não aparecem mais um para o outro e as indicações não se cruzam. "
    "Você pode desbloquear quando quiser em Minha conta."
)
REMOVER_OK = "Pronto! 💛 Removi a conexão com *{nome}*."
DESBLOQUEAR_OK = "Pronto, *{nome}* foi desbloqueado. 💛"
GERIR_VAZIO = "Você ainda não tem ninguém na rede para gerenciar. 💛"
SEM_BLOQUEADOS = "Você não bloqueou ninguém. 💛"


# --- Busca SEM resultado (nunca pedir à pessoa que ela mesma indique) --------
BUSCA_SEM_RESULTADO = (
    "Ainda não achei *{servico}* na sua rede nem na Central Dorote.ia. Mas há opções 👇\n\n"
    "Posso perguntar à sua rede de confiança — assim que alguém indicar, te aviso.\n\n"
    "O que você prefere fazer agora?"
)

# PARKING_LOT (pós-teste): resposta do item "🔔 Ativar alerta" enquanto a função
# não existe. Nenhuma lógica de alerta é criada agora (sem estado, sem gatilho).
ALERTA_PARKING = "Essa função ainda não está ativa 💛 Em breve!"

# Busca — pergunta a região quando veio só o serviço (botões [Toda a cidade] / [Escrever bairro]).
BUSCA_FALTA_REGIAO = (
    "Vou procurar *{servico}* — só faltou o bairro ou região de São Paulo."
)

BUSCA_PEDIR_BAIRRO = (
    "Qual bairro ou região de São Paulo?\n"
    "*Escreva aqui embaixo* 👇 Ex.: Pinheiros, zona leste, Santana... ou toque em "
    "*Menu* para outras opções"
)

# Rede pequena (< k): só resultados ⚪ da rede geral + convite para crescer a rede.
BUSCA_REDE_PEQUENA = (
    "\n\nComo a sua rede ainda é pequena, estes vêm da rede geral da Dorote.ia. 💛\n"
    "Quer convidar mais gente de confiança? Assim as próximas indicações chegam mais perto de você."
)

PEDIR_AMIGOS_LISTA = (
    "Para quem quer perguntar? 💛\n"
    "Escolha *Perguntar a todos* ou uma pessoa por vez. A mensagem segue pelo chat da "
    "Dorote.ia."
)

PEDIR_AMIGOS_SEM_REDE = (
    "Você ainda não tem rede com conexão confirmada.\n"
    "Convide pessoas de confiança pra sua rede crescer."
)

ASK_ENVIADO = (
    "Pronto! Perguntei para *{nome}*. Se eu receber indicações, te aviso. "
    "Quer perguntar a mais alguém?"
)

# Confirmação quando perguntou a TODOS (plural — modo_pergunta = todos).
ASK_ENVIADO_TODOS = (
    "Pronto! Perguntei para {n} pessoas da sua rede! Assim que alguém responder, te aviso."
)

# Mensagem que o AMIGO recebe (vai como sendo da pessoa que está procurando).
# {onde} e {detalhe} entram só quando há bairro/característica (montados no código).
# Sem artigo antes de {servico}: "uma marcenaria" quebrava a concordância.
ASK_PARA_AMIGO = (
    "Oi! 💛 *{quem}* está procurando *{servico}*{onde}{detalhe} e lembrou de você.\n"
    "Você conhece alguém bom para indicar?"
)


# --- Troca de perfil (quem tem os dois) -------------------------------------
# Aviso mostrado UMA única vez, quando a pessoa passa a ter os dois perfis.
TROCAR_AVISO = (
    "💡 A partir de agora você tem os dois perfis aqui: 🔍 Cliente e 💼 Profissional.\n"
    "Para alternar entre eles a qualquer momento, é só escrever *TROCAR*."
)

# Confirmação depois de trocar (o {perfil} já vem com emoji, ex.: "Profissional 💼").
TROCAR_OK = (
    "Pronto! Agora você está no perfil *{perfil}*. 💛\n"
    "O que deseja fazer?"
)

# Quem só tem o perfil de cliente e tenta TROCAR.
TROCAR_SO_CLIENTE = (
    "Por aqui você tem só o perfil de 🔍 Cliente 💛\n"
    "Quer criar também o seu perfil de 💼 Profissional?"
)


BUSCAR_SEM_REDE = (
    "🔍 *Buscar profissional*\n\n"
    "Você ainda não tem conexões confirmadas. Duas opções:\n\n"
    "🌐 *Rede geral:* recomendações qualificadas por membros da Dorote.ia.\n"
    "🤝 *Monte sua rede:* convide contatos de confiança — as indicações aparecem com o "
    "nome de quem você conhece.\n\n"
    "O que deseja fazer?"
)

# Contato compartilhado FORA de fluxo: o CÓDIGO pergunta o destino por botões
# (a IA não decide caminho — §7.1). O contato fica guardado no estado.
CONTATO_RECEBIDO = (
    "Recebi o contato de *{nome}*! 💛 O que você quer fazer?"
)
CONTATO_RECEBIDO_VARIOS = (
    "Recebi {n} contatos! 💛 O que você quer fazer?"
)

# Passo 2 do Buscar — pedido de serviço + bairro (com rede ou rede geral).
BUSCA_PEDIR_QUERY = (
    "Claro, {nome}! O que precisa e em qual bairro de São Paulo?\n\n"
    "Escreva tudo em uma mensagem, como um pedido em um grupo — ex.: \"dentista "
    "pediátrica em Perdizes\" ou \"marcenaria especializada em reparos em Pinheiros\".\n\n"
    "*Digite aqui embaixo* 👇 ou toque em *Menu* para outras opções"
)

# Passo 8 — "Buscar outro": mesma instrução, abertura diferente (evita saudação robótica).
BUSCA_PEDIR_QUERY_OUTRO = (
    "Vamos de novo! O que precisa e em qual bairro de São Paulo?\n\n"
    "Escreva tudo em uma mensagem, como um pedido em um grupo — ex.: \"dentista "
    "pediátrica em Perdizes\" ou \"marcenaria especializada em reparos em Pinheiros\".\n\n"
    "*Digite aqui embaixo* 👇 ou toque em *Menu* para outras opções"
)

PRESTADOR_QUERO_SER = (
    "Que bom que você presta um serviço! 💛\n"
    "Para o seu trabalho aparecer aqui, é fundamental que clientes registrem recomendações "
    "de verdade sobre você. Para começar, aceite os Termos de Uso Profissional e configure "
    "o seu perfil.\n\n"
    "Vamos começar?"
)

PRESTADOR_QUERO_SER_OK = (
    "Perfil profissional iniciado! 🚀\n"
    "👀 Você aparece na busca confiável após a 1ª recomendação\n"
    "📈 + recomendações, + alcance\n\n"
    "📣 Conte em uma mensagem:\n"
    "1️⃣ O que você faz\n"
    "2️⃣ Onde atende\n"
    "3️⃣ Seus diferenciais\n"
    "4️⃣ Como te encontrar e pagar\n\n"
    "Ex.: _Conserto de geladeira. Atendo a zona leste de SP. Vou no mesmo dia e dou "
    "3 meses de garantia. Pix, cartão ou dinheiro. Instagram @geladeirafacil._\n\n"
    "Digite sua resposta aqui embaixo 👇 ou toque em *Menu*"
)

# Para quem já era cliente e agora vira também profissional (variação da 1ª linha).
PRESTADOR_QUERO_SER_OK_DUAL = (
    "Que bom ter você também como profissional! 🚀\n"
    "👀 Você aparece na busca confiável após a 1ª recomendação\n"
    "📈 + recomendações, + alcance\n\n"
    "📣 Conte em uma mensagem:\n"
    "1️⃣ O que você faz\n"
    "2️⃣ Onde atende\n"
    "3️⃣ Seus diferenciais\n"
    "4️⃣ Como te encontrar e pagar\n\n"
    "Ex.: Conserto de geladeira. Atendo a zona leste de SP. Vou no mesmo dia e dou "
    "3 meses de garantia. Pix, cartão ou dinheiro. Instagram @geladeirafacil.\n\n"
    "*Digite sua resposta aqui embaixo 👇* ou toque em Menu"
)

# Resumo organizado do que a Dorote.ia entendeu (validação com botões).
PRESTADOR_VALIDAR = (
    "Deixa eu ver se entendi — é assim que o seu perfil vai ficar:\n\n"
    "O que você faz: {categoria}\n"
    "Especialidade: {subcategoria}\n"
    "Onde atende: {regiao}\n"
    "Diferenciais: {diferenciais}\n"
    "Contato e pagamento: {contato}\n\n"
    "Está certo? Você pode confirmar, corrigir ou ver outras opções."
)

PRESTADOR_CORRIGIR = (
    "Sem problema! É só copiar a mensagem abaixo, ajustar o que precisar e me reenviar — "
    "eu organizo tudo de novo para você conferir:"
)


# --- Prestador de servico (Fase 3) ---------------------------------------
PRESTADOR_ACOLHIDA = (
    "Olá! 🛠️ Um contato que confia no seu trabalho indicou você para fazer parte da "
    "Dorote.ia.\n\n"
    "A Dorote.ia é uma central que conecta quem precisa de um serviço a especialistas — "
    "como você em {servico}. Quando alguém da rede precisar e receber a sua indicação, o "
    "seu contato vai só para essa pessoa. Ninguém te manda mensagem por aqui.\n\n"
    "Para ativar o seu cadastro, preciso da sua autorização para usar o seu contato e a "
    "categoria do serviço, conforme os Termos de Uso.\n"
    "📄 Termos do profissional: {link}\n\n"
    "Os seus dados serão usados apenas para conectar você a quem busca o seu trabalho. "
    "Deseja prosseguir?"
)

PRESTADOR_AJUSTAR = (
    "Claro! Qual é a categoria certa do seu serviço? "
    "Ex.: encanador, eletricista, pediatra, professor de inglês…"
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
    "Prontinho, perfil atualizado! 🎉 Já está tudo certo.\n\n"
    "A qualquer momento, toque em MENU para ajustar o seu perfil ou alternar entre as "
    "visões de cliente e profissional."
)

# Mensagem 6 (§8) — honesta: o perfil só aparece na busca depois da 1ª recomendação.
PRESTADOR_PERFIL_INVISIVEL = (
    "Seu perfil de profissional está criado. 💛\n\n"
    "Assim que a primeira pessoa recomendar o seu trabalho, você começa a aparecer para "
    "a rede. É a recomendação de verdade que dá força ao seu perfil aqui."
)


# --- Profissional pede recomendações à própria clientela ------------------
# Instruções que O PROFISSIONAL vê (curtas e diretas). O link é pessoal: pode
# encaminhar para qualquer cliente que já atendeu.
REC_PEDIR_VOCE = (
    "📣 *Peça recomendações a quem você já atendeu*\n\n"
    "É a recomendação de clientes de verdade que faz o seu trabalho aparecer aqui.\n\n"
    "Encaminhe a mensagem abaixo para clientes que você já atendeu — pode mandar para "
    "quantas pessoas quiser. Quando alguém entrar pelo seu convite, eu te aviso para "
    "você confirmar que conhece. Aí a recomendação passa a valer. 💛"
)

# Mensagem PRONTA para o profissional encaminhar (voz do profissional, com segurança).
REC_MENSAGEM_CLIENTE = (
    "Oi! 💛 Meu trabalho agora está na Dorote.ia, uma central de indicações de "
    "confiança no WhatsApp.\n"
    "Se você gostou do meu serviço, me recomenda lá? É rapidinho — entra pelo meu "
    "convite e pronto. Sua recomendação me ajuda demais:\n"
    "{link}"
)

# Boas-vindas de quem chega pelo link de RECOMENDAR um profissional.
BOAS_VINDAS_RECOMENDAR = (
    "Oi! Eu sou a Dorote.ia 💛\n\n"
    "*{nome}* pediu a sua recomendação. Ao entrar por este convite, você recomenda o "
    "trabalho de {nome} e vocês ficam conectados aqui — é assim que as boas indicações "
    "circulam entre quem se conhece.\n\n"
    "De quebra, você também passa a achar profissionais recomendados por quem confia.\n\n"
    "🔒 *Privacidade:* guardo só o seu nome e telefone. O seu número nunca é "
    "compartilhado e o seu nome só aparece para quem você aceitar. Para sair, digite "
    "*SAIR*.\n\n"
    "🔗 *Termos de uso:*\n{link}\n\n"
    "Posso registrar? Responda *SIM* para aceitar os termos e recomendar *{nome}*, ou "
    "digite *SABER MAIS*."
)

# Aviso ao PROFISSIONAL quando um cliente entra pelo link de recomendação.
REC_CONFIRMA_PROF = (
    "Boa notícia! 💛 *{nome}* entrou pelo seu convite para recomendar o seu trabalho.\n\n"
    "Vocês se conhecem?"
)

# Retorno a quem ENTROU e recomendou (aguardando só a confirmação do profissional).
REC_ENTROU_OK = (
    "Prontinho! 💛 Sua recomendação para *{nome}* foi registrada.\n"
    "Assim que {nome} confirmar que vocês se conhecem, ela passa a valer na rede e "
    "vocês ficam conectados."
)


# --- Saida (exclusao) diferenciada por perfil ----------------------------
SAIR_CLIENTE = (
    "Tem certeza que quer sair? 💛\n\n"
    "Vou apagar o seu cadastro e o seu nome. As indicações que você fez continuam "
    "ajudando a rede, mas de forma anônima (sem o seu nome)."
)

SAIR_PROFISSIONAL = (
    "Tem certeza que quer sair? 💛\n\n"
    "Vou apagar o seu cadastro e o seu nome, e o seu perfil de profissional deixa de "
    "aparecer para a rede. As indicações que você fez continuam ajudando a rede, mas de "
    "forma anônima (sem o seu nome)."
)

SAIR_HIBRIDO = (
    "Tem certeza que quer sair? 💛\n\n"
    "Você tem os dois perfis aqui. Ao sair de tudo, apago o seu cadastro e o seu nome, e "
    "o seu perfil de profissional deixa de aparecer. As indicações que você fez continuam "
    "ajudando a rede, mas de forma anônima (sem o seu nome).\n\n"
    "Se preferir, dá para ficar só com um dos perfis. O que deseja fazer?"
)


# --- Fluxo "Preciso de ajuda" (durante processo de saída) -----------
AJUDA_PEDIR_DURACAO = (
    "Pode contar! 💛 Qual é sua dúvida?"
)

AJUDA_AGRADECIDA = (
    "Obrigada por compartilhar 💛 Anotei sua mensagem.\n\n"
    "Você quer voltar e continuar usando a Dorote.ia, ou prefere sair mesmo assim?"
)


# --- Rede de seguranca (qualquer erro inesperado) ------------------------
ERRO_GENERICO = (
    "Opa, tivemos um probleminha aqui do meu lado 😅\n"
    "Pode tentar de novo daqui a pouquinho, por favor? Se continuar, é só mandar "
    "*menu* que a gente recomeça. 💛"
)
