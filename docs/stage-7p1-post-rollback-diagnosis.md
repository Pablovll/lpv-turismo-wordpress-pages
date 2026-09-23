# Etapa 7P.1 - Diagnostico pos-rollback

Data: 23/09/2026. Producao permaneceu sem novas alteracoes durante este
diagnostico. Nenhum plugin foi ativado/removido, nenhuma pagina, configuracao,
CSS ou entrada AIOSEO foi escrita, nenhum cache foi limpo e nenhuma credencial
temporaria foi criada.

## Evidencia preservada

Os JSONs e backups privados foram inventariados por timestamp, tamanho e
SHA-256 em `.production-evidence/stage-7p1-preserved-evidence.json`, ignorado
pelo Git. Nao havia log de tentativa nem traceback primario: o executor antigo
somente imprimiu a excecao que chegou ao `main()`. `deployment.json` e
`post-deploy.json` nao existem porque a tentativa nao chegou ao aceite publico.

O codigo antigo chamava `rollback()` dentro de um `except` e usava um `raise`
nu depois. Quando `rollback()` lancou `Granular rollback incomplete: css`, essa
excecao secundaria saiu do bloco antes do `raise` original. Assim, tipo,
mensagem, exit code e traceback da falha primaria nao foram persistidos.

## Timeline comprovada

| Fase | Estado | Evidencia |
| --- | --- | --- |
| Precheck / backup / dry-run | COMPLETED | relatorios aprovados de 23/09/2026 |
| Maintenance mode | COMPLETED / depois desativado | estado final inativo; homepage HTTP 200 |
| LPV Page Templates | COMPLETED / ROLLED BACK | CSS so foi executado depois de `install_plugins()` e da verificacao runtime; arquivos ficaram inativos |
| LPV Language SEO | COMPLETED / ROLLED BACK | mesma sequencia; arquivos ficaram inativos |
| CSS: gravacao nativa | COMPLETED | revisao 812, 18:02:12 UTC, 86.373 bytes, hash aprovado |
| CSS: confirmacao pelo cliente | FAILED | o fluxo nao avancou apesar da revisao exata |
| HTML das 22 paginas | NOT STARTED | 0/22 `post_modified_gmt` mudaram em relacao ao backup |
| AIOSEO | NOT STARTED | vem depois do HTML no fluxo; 22/22 valores permaneceram originais |
| Status EN | NOT STARTED | 22/22 status permaneceram originais |
| Cache de conclusao | NOT STARTED | vem depois de EN |
| Rollback CSS: gravacao | COMPLETED | revisao 813, 18:02:20 UTC, 28.743 bytes, hash original |
| Rollback CSS: confirmacao pelo cliente | FAILED (FALSE NEGATIVE) | rollback registrou `css`, mas revisao e leitura atual sao exatas |
| Auditoria pos-rollback | COMPLETED | 22 paginas HTTP 200 e baseline de 313 achados restaurado |

Nao houve alteracoes posteriores ao primeiro erro antes do rollback. Precisaram
ser revertidos CSS e estado dos plugins. HTML, AIOSEO e status nao chegaram a
ser alterados. Os arquivos dos plugins ficaram instalados, mas inativos.

## Causa raiz

**ROOT CAUSE:** o protocolo entre helper PHP e `run_helper()` tratava stdout
inteiro como JSON puro e nao persistia resultado, stdout/stderr ou excecao
primaria. A gravacao CSS terminou e foi validada no WordPress, mas a camada de
transporte/interpretacao levantou excecao antes de devolver sucesso ao
checkpoint. O mesmo ocorreu depois da restauracao correta, gerando o falso
negativo. O sinal exato que contaminou/invalidou a resposta antiga nao pode ser
recuperado porque stdout, stderr e a excecao primaria nao foram registrados;
nao e apresentado como fato inventado.

**FAILED CHECKPOINT:** CSS.

**FAILED OPERATION:** confirmacao estruturada de
`run_helper(..., "apply-css.php", ...)` depois de
`wp_update_custom_css_post()` ter salvo o hash aprovado.

**EVIDENCE:** controle de fluxo em `scripts/deploy_production.py`; ausencia de
qualquer modificacao de pagina; revisoes 812/813 do `custom_css`; relatorio
`rollback.json`; hashes do backup e leitura atual. A falha nao foi causada por
encoding, BOM, CRLF/LF, normalizacao, tema ou diferenca do CSS salvo.

**IMPACT:** CSS aprovado ficou ativo por aproximadamente oito segundos. O
rollback restaurou o CSS anterior. Plugins novos ficaram instalados e inativos;
o restante nao foi alterado.

## Representacoes do CSS

| Representacao | Bytes | SHA-256 | Normalizacao |
| --- | ---: | --- | --- |
| A. aprovado antes do deploy | 86.373 | `55aa08538899d7310f92218cfd8df420b8556eb54fcebeae225ef04383a13145` | nenhuma; LF, sem BOM |
| B. backup original | 28.743 | `cb2a5566eaae64c129fcae4e57f5e7828b02337d66b01d35d435646355dfe259` | nenhuma; LF, sem BOM |
| C. enviado | 86.373 | igual a A | nenhuma |
| D. relido apos salvar | 86.373 | igual a A (revisao 812) | nenhuma |
| E. restaurado | 28.743 | igual a B (revisao 813) | nenhuma |
| F. leitura atual | 28.743 | igual a B | nenhuma |

## Correcoes

- Helpers retornam `LPV_RESULT:<json>`; ruido fora do marcador nao participa do parse.
- `run_helper()` captura o exit code e extrai somente o resultado marcado.
- Restauracao CSS ja idempotente retorna sucesso sem regravar.
- Resultados CSS registram bytes e SHA-256 de before, target e saved.
- Tentativas futuras geram timeline privada incremental por checkpoint.
- `primary_exception` e `rollback.exceptions[]` sao estruturas independentes.
- Rollback coleta falhas por componente e nunca substitui a causa primaria.
- Maintenance mode continua desativado em `finally` quando tecnicamente possivel.
- Application Password continua revogada em `finally` sempre que criada.
- Rollback de plugins agora verifica remocao/restauracao em vez de ignorar o resultado.

## Plugins inativos

**MATCH.** LPV Page Templates 1.0.0 tem 3/3 arquivos byte-identicos ao ZIP
aprovado; LPV Language SEO 1.0.0 tem 2/2. Tamanhos e SHA-256 coincidem, sem
arquivos extras ou ausentes. Permanecem inativos. Recomendacao: mante-los ate a
proxima janela e permitir a reinstalacao controlada `--force` do mesmo pacote;
nao ha fundamento para remove-los agora.

## Testes e nova rodada read-only

- 56 testes executados: aprovados; 5 skips dos harnesses PHP locais por ausencia
  de `PHP_BINARY`. Os quatro PHP novos passaram em `php -l` no PHP 8.2 remoto.
- Regressao cobre resultado com ruido, falha primaria com rollback aprovado,
  falha secundaria, varias excecoes, `finally` de maintenance e revogacao da
  Application Password. Auditor publico usa fixtures e nao envia formularios.
- `git diff --check`: aprovado.
- Novo preflight: APROVADO (pacote, remoto e varredura sensivel).
- Baseline GET: 22 paginas e politica HTTP 200; 313 achados preexistentes.
- Novo backup: `.production-private-backup/20260923T182751Z/`, APROVADO,
  29 arquivos, incluindo os dois plugins inativos. Nao versionado.
- Novo dry-run: APROVADO, zero blockers; 22 conteudos, CSS e 22 metadados AIOSEO
  seriam alterados; zero paginas EN precisam mudar de status.

## Riscos residuais

O stdout/stderr exato da tentativa antiga nao existe e nao pode ser recriado
sem nova escrita; a correcao elimina essa lacuna para a proxima tentativa.
FormSubmit, recebimento de e-mail, GA DebugView e zoom real 200% permanecem
NAO TESTADOS. Nenhum novo deploy foi executado nesta etapa.
