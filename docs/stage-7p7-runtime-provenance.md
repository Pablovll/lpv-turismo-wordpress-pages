# Etapa 7P.7 - Proveniencia do runtime

Data: 25/09/2026.

## Motivo

A candidata 1.0.1 removeu `Configuration data not found`, mas a execucao 7P.6B
foi revertida porque o Playwright atribuiu automaticamente ao documento atual
o texto `Provider's accounts list is empty.`. Sem stack ou origem de execucao,
essa localizacao nao prova que JavaScript LPV chamou `console.error`.

## Captura

O auditor mantem os eventos Playwright `pageerror`, `console`, request failed e
response HTTP falha. Em paralelo, quando suportado, habilita via CDP:

- `Runtime.enable`, com `Runtime.exceptionThrown` e `Runtime.consoleAPICalled`;
- `Log.enable`, com `Log.entryAdded`;
- `Network.enable`, com request, response e loading failure.

Cada evento registra somente mensagem limitada, canal, source, level, URL sem
query, linha/coluna, URLs de stack, URL de recurso, tipo, same-origin,
browser-internal, blocker e motivo. Cookies, headers, tokens e credenciais nao
sao coletados.

## Classificacao

Excecao ou `console.error` com URL de script/stack same-origin e bloqueadora.
Falha de documento, JS, CSS, imagem ou fonte first-party e bloqueadora. Falha
funcional de menu, foco, Escape, links, formulario ou double submit tambem e
bloqueadora independentemente do console.

`Log.entryAdded` com source `other`, `security`, `rendering`, `intervention`,
`deprecation`, `recommendation` ou `violation`, sem stack first-party, e
diagnostico de navegador. O caso FedCM exige simultaneamente canal CDP Log,
source `other`, ausencia de stack first-party e assinatura accounts-list-empty.
O evento Playwright duplicado so herda essa classificacao quando nao existe
`Runtime.consoleAPICalled` first-party com a mesma mensagem.

Assim, a regra nao e uma allowlist textual: `throw` ou `console.error` LPV com
o mesmo texto continua bloqueando. Erro third-party sem impacto demonstrado e
registrado; passa a bloquear se quebrar recurso necessario, DOM ou interacao.

## Acceptance

O relatorio agrega separadamente:

- `FIRST_PARTY_EXCEPTIONS`;
- `FIRST_PARTY_CONSOLE_ERRORS`;
- `FIRST_PARTY_CRITICAL_RESOURCE_FAILURES`;
- `THIRD_PARTY_DIAGNOSTICS`;
- `BROWSER_DIAGNOSTICS`;
- `FEDCM_DIAGNOSTICS`;
- `FUNCTIONAL_FAILURES`.

Os campos materiais first-party e funcionais devem ficar em zero. Diagnosticos
browser, FedCM e third-party podem ser maiores que zero sem aprovar uma
interacao quebrada. FormSubmit, WhatsApp, GA/GTM e POST externo continuam
interceptados antes da rede.
