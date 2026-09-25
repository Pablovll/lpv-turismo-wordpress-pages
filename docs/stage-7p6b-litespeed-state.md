# Etapa 7P.6B - Estado operacional LiteSpeed

Data: 25/09/2026.

## Causa raiz

**LITESPEED TIMESTAMP ROOT CAUSE: EXPECTED OPERATIONAL MUTATION.**

O unico desvio do fingerprint depois do purge e rollback da 7P.6 foi
`litespeed.optimize.timestamp_purge_css`. A instalacao 7.9.1 armazena nessa
option um Unix timestamp numerico e o comando oficial `wp litespeed-purge all`
o atualiza como parte da limpeza autorizada. Restaurar o valor antigo criaria
um estado operacional falso.

## Classificacao estrita

O inventario read-only mantem duas representacoes:

- `litespeed_stable_configuration`: todas as options `litespeed%`, exceto uma;
- `litespeed_operational_state`: somente
  `litespeed.optimize.timestamp_purge_css`, com valor e hash.

Nao existe regex, prefixo de exclusao ou lista aberta. Toda nova option e toda
option existente fora desse nome literal entra na configuracao estavel e
continua bloqueadora. Isso inclui JS Minify, JS Defer, JS Delay, CSS Minify,
cache e qualquer outra configuracao monitorada.

## Validacao do purge

Imediatamente antes e depois do purge final, o executor captura os dois
conjuntos, o inicio e fim UTC do comando e o horario da leitura posterior.
Exige configuracao estavel identica e timestamp numerico, nao negativo, nao
absurdamente futuro e, quando alterado, dentro da janela do purge com tolerancia
restrita de relogio. Mudanca valida resulta em
`EXPECTED_OPERATIONAL_CHANGE`; ausencia de mudanca e diagnostica. Qualquer
outra option alterada bloqueia e aciona rollback.

O fingerprint material usa apenas configuracao estavel. O rollback aceita
`MATERIAL_STATE_RESTORED` com timestamp operacional diferente e registra
`OPERATIONAL_STATE_CHANGED_BY_PURGE`; o timestamp nao e regravado.

## Cache

LiteSpeed ativo, purge com exit code zero, scripts LPV nao transformados,
paginas e assets validos permanecem obrigatorios. Duas leituras GET por pagina
registram `X-LiteSpeed-Cache`, mas ausencia isolada de HIT nao bloqueia porque
warm-up e regras locais podem produzir MISS ou omitir o header.

## Decisao posterior 7P.7

A classificacao de console baseada apenas na URL atribuida pelo Playwright foi
substituida por proveniencia combinada Playwright/CDP. Detalhes e testes estao
em `docs/stage-7p7-runtime-provenance.md`; os contratos LiteSpeed desta etapa
nao foram alterados.
