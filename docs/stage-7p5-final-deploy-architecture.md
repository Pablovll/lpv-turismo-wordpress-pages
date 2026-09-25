# Etapa 7P.5 - Arquitetura final de aceite

Data da decisao: 25/09/2026.

## Motivo da mudanca

As cinco tentativas controladas comprovaram progressivamente o backup, o deploy
shield, o rollback, a escrita por APIs nativas, o pacote de plugins, o CSS, os 22
conteudos, AIOSEO, idiomas, imagens e cache. A quinta tentativa foi revertida
somente porque o auditor exigia igualdade lexical entre o JavaScript aprovado e
o JavaScript que o LiteSpeed ja havia minificado e marcado para entrega adiada.

Essa comparacao misturava fonte, renderizacao WordPress e entrega otimizada. O
hash diferente era real, mas nao demonstrava perda funcional. Nao sera criada
outra heuristica para inferir equivalencia de JavaScript minificado.

## Contratos A/B/C

### A - Stored Source Integrity

O arquivo aprovado e comparado ao `post_content` lido por WP-CLI. Conteudo,
URLs editoriais e scripts sao bloqueadores independentes. Scripts preservam
quantidade, ordem, `src` e codigo; somente BOM UTF-8 e finais de linha sao
normalizados. Cada representacao canonica recebe SHA-256.

Checks: `stored_content_preserved`, `stored_image_urls_preserved` e
`stored_script_source_preserved`.

### B - Pre-Optimization Render Fidelity

O auditor faz um GET adicional com `LSCWP_CTRL=before_optm`, preservando qualquer
query string existente. Essa resposta serve apenas para fidelidade do conteudo e
dos scripts dentro de `.wp-block-post-content`. SEO, canonical e hreflang sao
sempre avaliados na URL publica normal.

Checks: `preoptimization_rendered_content_preserved` e
`preoptimization_scripts_preserved`.

O mecanismo e documentado pelo LiteSpeed como visualizacao sem Page Optimization
para diagnostico. A documentacao tambem confirma que JS Minify remove espacos,
quebras e comentarios e que Deferred/Delayed altera o momento da execucao:

- https://docs.litespeedtech.com/lscache/lscwp/ts-optimize/
- https://docs.litespeedtech.com/lscache/lscwp/pageopt/
- https://docs.litespeedtech.com/lscache/lscwp/api/

Confirmacao local read-only na versao instalada `7.9.1`: URL normal respondeu
HTTP 200 com cache hit; `before_optm` respondeu HTTP 200 com `no-cache`. Nenhuma
configuracao do LiteSpeed foi alterada.

### C - Optimized Runtime Behavior

`scripts/audit_runtime_browser.py` usa Playwright com Chromium local, viewport de
375 x 812 e contexto novo por pagina. Ele visita as 22 URLs normais, sem
`before_optm`, e verifica:

- carga HTTP e ausencia de excecoes JavaScript LPV;
- menu mobile, `aria-expanded`, Escape e retorno de foco;
- links internos;
- formularios PT/ES/EN, contexto, idioma, validacao, estado do botao e protecao
  contra envio duplo;
- eventos locais `lpv_tour_open`, `lpv_whatsapp_click` e
  `lpv_proposal_request_submit`, sem PII.

FormSubmit, WhatsApp, Google Analytics, Google Tag Manager e todo POST externo
sao interceptados antes da saida. O auditor registra a tentativa, mas nao a
transmite. GETs de renderizacao permanecem permitidos.

No HTML otimizado, `optimized_script_delivery_detected` registra a forma de
entrega (`inline`, externa ou `litespeed/javascript`). Ele e diagnostico e nao
declara equivalencia por hash ou token.

## Decisao posterior 7P.6

O runtime otimizado real continuou bloqueando 20 paginas com
`Configuration data not found`. A Etapa 7P.6 substitui a tolerancia a essa
transformacao por um bypass estrito de Page Optimization, via
`litespeed_can_optm`, somente nas 22 paginas do mapa. A resposta publica normal
volta a exigir scripts preservados. Esta secao registra a evolucao; os
contratos de stored source, before_optm e browser runtime permanecem ativos.

## Fingerprint material

`post_modified_gmt` permanece no inventario e no backup, mas e informativo. O
fingerprint material inclui conteudo, status, path/slug/parent, AIOSEO, CSS,
options, templates e plugins. Mudanca somente de timestamp produz
`MATERIAL_STATE_UNCHANGED`; qualquer mudanca material continua bloqueando.

## Transporte e TLS

GETs read-only usam timeout explicito, ate tres tentativas e backoff curto. O
numero de erros de transporte e registrado. Falha persistente continua sendo
bloqueadora. No rollback, uma falha intermediaria exclusivamente de transporte
pode resultar em `APROVADO_COM_AVISO_TRANSITORIO` apenas quando a reconciliacao
final comprova o fingerprint material e a ausencia do shield.

## Criterio objetivo de aceite

O JavaScript e aprovado somente com A, B e C aprovados. O auditor publico normal
continua rigoroso para texto, estrutura, formularios, links, estilos, imagens,
SEO e idiomas, mas nao compara lexicalmente o codigo ja transformado pelo
LiteSpeed.

Falha de fonte armazenada, `before_optm` ou runtime real reinstala o shield,
preserva a evidencia e aciona rollback. Diferenca lexical exclusiva da saida
otimizada nao aciona rollback.

## Backup e rollback

O deploy final exige backup novo e validado imediatamente antes do dry-run. O
backup anterior `20260925T125806Z` permanece historico e nao pode ser reutilizado.
O escopo continua banco, 22 conteudos, CSS, SEO, options, status, plugins,
manifesto e hashes. Backups e evidencias privadas continuam ignorados pelo Git.

## Dependencia local

O Playwright Python esta fixado em `requirements-dev.txt`. Binarios de navegador
nao sao versionados nem instalados no WordPress; o auditor usa Chromium local.
