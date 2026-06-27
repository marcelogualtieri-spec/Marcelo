# termos.py
# ===========================================================================
# TERMOS DE USO E POLITICA DE PRIVACIDADE da Doroteia.
# Servidos como pagina HTML em /termos (link que aparece na mensagem de
# boas-vindas). O texto reflete as praticas REAIS de seguranca do produto
# (hash HMAC dos contatos, sem guardar numero de nao-membro, etc.) e a LGPD.
#
# ANTES DE PUBLICAR, preencha os campos marcados com [AJUSTAR ...]:
#   - identificacao do controlador (nome/razao social/CNPJ, se houver);
#   - e-mail de contato do Encarregado (DPO).
# ===========================================================================

# Atualize quando mudar a politica.
DATA_VIGENCIA = "27 de junho de 2026"

# Preencha com os dados reais antes de divulgar publicamente.
CONTROLADOR = "Doroteia [AJUSTAR: nome/razao social do responsavel]"
CONTATO_DPO = "[AJUSTAR: e-mail de contato para questoes de privacidade]"


TERMOS_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Termos de Uso e Privacidade — Doroteia</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         line-height: 1.6; max-width: 760px; margin: 0 auto; padding: 24px;
         color: #1c1c1e; background: #fff; }}
  h1 {{ font-size: 1.6rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 2rem; }}
  .meta {{ color: #666; font-size: .9rem; }}
  code {{ background: #f2f2f2; padding: 1px 5px; border-radius: 4px; }}
  ul {{ padding-left: 1.2rem; }}
  .box {{ background: #fdf6e3; border: 1px solid #f0e3b8; border-radius: 8px; padding: 12px 16px; }}
  footer {{ margin-top: 3rem; color: #666; font-size: .85rem; }}
</style>
</head>
<body>
<h1>Termos de Uso e Política de Privacidade — Doroteia 💛</h1>
<p class="meta">Última atualização: {data}</p>

<p>A Doroteia é uma assistente no WhatsApp que ajuda você a encontrar
profissionais e serviços recomendados por pessoas da sua própria rede de
confiança. Estes Termos explicam como o serviço funciona e como cuidamos dos
seus dados, em conformidade com a <strong>Lei Geral de Proteção de Dados
(Lei nº 13.709/2018 — LGPD)</strong>.</p>

<div class="box">
<strong>Resumo honesto:</strong> guardamos só o seu nome e os contatos que
<em>você</em> escolher conectar. Os contatos são guardados de forma
embaralhada (não vemos os números). Nunca repassamos o telefone de ninguém,
exceto o do profissional que foi indicado — que é justamente o objetivo. Você
pode apagar tudo a qualquer momento digitando <code>SAIR</code> no chat.
</div>

<h2>1. Quem é o responsável (Controlador)</h2>
<p>O tratamento dos seus dados é feito por: <strong>{controlador}</strong>.
Para qualquer questão sobre privacidade ou para exercer seus direitos, fale com
o nosso Encarregado (DPO): <strong>{dpo}</strong>.</p>

<h2>2. O aceite dos termos</h2>
<p>Ao responder <strong>SIM</strong> na conversa, você declara ter lido e
concordado com estes Termos e com o tratamento dos seus dados aqui descrito.
O aceite é a base legal (consentimento) para o serviço funcionar. Você pode
retirar o consentimento a qualquer momento (veja a seção 9).</p>

<h2>3. Dados que coletamos</h2>
<ul>
  <li><strong>Seu nome de perfil e número do WhatsApp</strong>, para te
  identificar e conversar com você.</li>
  <li><strong>O conteúdo das mensagens</strong> que você troca com a Doroteia,
  para entender seus pedidos e manter o contexto da conversa.</li>
  <li><strong>Contatos de confiança que você compartilha</strong>: guardamos
  apenas um <strong>código irreversível</strong> (hash) de cada número — não
  guardamos os números de telefone dos seus contatos. Esse código serve só para
  reconhecer conexões em comum dentro da rede.</li>
  <li><strong>Indicações que você faz</strong>: o nome e o telefone do
  profissional que você recomenda (ex.: um encanador), para podermos mostrá-lo a
  outras pessoas da sua rede que precisarem daquele serviço.</li>
  <li><strong>Suas buscas, avaliações e comunidades</strong> em que você entra,
  para melhorar as recomendações.</li>
</ul>

<h2>4. Como usamos os dados</h2>
<ul>
  <li>Buscar e apresentar indicações de confiança para os serviços que você pede.</li>
  <li>Mostrar o seu nome como quem indicou <strong>apenas</strong> para pessoas
  conectadas a você (seus contatos ou membros da mesma comunidade) — e vice-versa.</li>
  <li>Conectar pessoas de confiança e fortalecer a rede.</li>
  <li>Lembrar você de avaliar um serviço que usou e avisar quando surgir uma
  indicação que você procurava.</li>
</ul>
<p><strong>Nós não vendemos os seus dados</strong> e não os usamos para
publicidade de terceiros.</p>

<h2>5. Inteligência Artificial</h2>
<p>Para entender e responder em linguagem natural, o conteúdo de texto das suas
mensagens é processado por um modelo de IA (Anthropic Claude). Antes do envio,
números de telefone presentes na mensagem são substituídos por fichas
(ex.: <code>[CONTATO_1]</code>): <strong>a IA não recebe números de telefone
reais</strong>.</p>

<h2>6. Compartilhamento</h2>
<ul>
  <li>Seu <strong>nome</strong> como recomendante é visível apenas para pessoas
  conectadas a você.</li>
  <li>O <strong>telefone de um profissional que você indicou</strong> é
  compartilhado com quem busca aquele serviço na sua rede — esse é o propósito
  do serviço.</li>
  <li>Seu <strong>telefone pessoal nunca é repassado</strong> a outros usuários.</li>
</ul>

<h2>7. Segurança</h2>
<ul>
  <li>Comunicação protegida por <strong>HTTPS/TLS</strong>.</li>
  <li>A rede de contatos é guardada como <strong>código HMAC-SHA256</strong>,
  gerado com uma chave secreta que nunca é exposta — não é possível voltar do
  código para o número.</li>
  <li>As mensagens recebidas têm a <strong>assinatura da Meta validada</strong>
  para evitar fraudes.</li>
  <li>Acesso ao banco de dados restrito e segredos guardados apenas em variáveis
  de ambiente, nunca no código.</li>
</ul>

<h2>8. Operadores e transferência internacional</h2>
<p>Para operar, usamos provedores que atuam como operadores de dados e podem
processar informações fora do Brasil (ex.: Estados Unidos), com as salvaguardas
previstas no art. 33 da LGPD:</p>
<ul>
  <li><strong>Meta Platforms (WhatsApp Cloud API)</strong> — entrega das mensagens;</li>
  <li><strong>Anthropic</strong> — processamento de linguagem (IA);</li>
  <li><strong>Supabase</strong> — banco de dados;</li>
  <li><strong>Render</strong> — hospedagem do servidor.</li>
</ul>

<h2>9. Seus direitos (art. 18 da LGPD)</h2>
<p>Você pode, a qualquer momento: confirmar a existência de tratamento; acessar,
corrigir, anonimizar, bloquear ou eliminar seus dados; pedir a portabilidade;
ser informado sobre o compartilhamento; e <strong>retirar o consentimento</strong>.</p>
<p>Como exercer:</p>
<ul>
  <li>Para <strong>apagar todos os seus dados</strong> (e encerrar o uso): digite
  <code>SAIR</code> no chat a qualquer momento. Confirmamos antes de excluir.</li>
  <li>Para os demais pedidos: é só pedir no chat ou escrever para o Encarregado
  (seção 1).</li>
</ul>

<h2>10. Retenção e exclusão</h2>
<p>Guardamos seus dados enquanto você usar o serviço. Ao pedir a exclusão,
apagamos seu cadastro, suas conexões, indicações e avaliações. Registros
estatísticos podem ser mantidos de forma <strong>desvinculada da sua
identidade</strong>, sem permitir identificar você.</p>

<h2>11. Menores de idade</h2>
<p>O serviço não é destinado a menores de 18 anos.</p>

<h2>12. Alterações nestes Termos</h2>
<p>Podemos atualizar estes Termos. Mudanças relevantes serão comunicadas pelo
próprio WhatsApp. A data no topo indica a versão vigente.</p>

<footer>
Doroteia — feito com 💛 para conectar pessoas de confiança.
</footer>
</body>
</html>"""


def pagina_termos():
    return TERMOS_HTML.format(
        data=DATA_VIGENCIA,
        controlador=CONTROLADOR,
        dpo=CONTATO_DPO,
    )
