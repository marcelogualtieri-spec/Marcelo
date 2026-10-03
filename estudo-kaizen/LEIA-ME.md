# Kaizen Quest — app de estudo (arquivo único)

App de estudo independente (não faz parte da Dorote.ia). Tudo está em `kaizen-quest.html`.

## Como usar
1. Baixe o arquivo `kaizen-quest.html` (ou copie o código para um arquivo com esse nome).
2. Abra com dois cliques no Chrome, Edge, Safari ou Firefox: funciona no computador, no tablet e no celular.
3. No celular/tablet: salve o arquivo no aparelho e abra pelo navegador. Para ficar como um app,
   use "Adicionar à tela inicial".

O progresso fica salvo no navegador (localStorage). Use **Perfil → Configurações → Exportar** para
fazer backup ou trocar de aparelho.

## Modos do Scanner
- **Local (grátis):** lê o texto da foto (OCR via Tesseract.js, precisa de internet só na
  primeira vez para baixar o leitor) e gera resumo, mapa mental, exercícios e quiz a partir do texto.
- **IA (opcional):** com uma chave da API Anthropic (console.anthropic.com), a IA Claude lê
  as fotos diretamente e gera um material mais rico. Cada análise tem um pequeno custo.
