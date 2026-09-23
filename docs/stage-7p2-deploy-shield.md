# Etapa 7P.2 - Deploy Shield e rollback idempotente

Data: 23/09/2026. Esta etapa altera somente o executor versionado, testes e
documentacao. Nenhum terceiro deploy foi executado e nenhuma pagina, CSS,
configuracao, plugin ou metadado da producao foi modificado.

## Causa do segundo rollback

O segundo deploy concluiu plugins, CSS e os 22 conteudos, mas a primeira chamada
REST do checkpoint AIOSEO recebeu HTTP 503. O maintenance mode nativo do
WordPress tambem bloqueia `/wp-json/`, portanto era incompativel com a operacao
REST oficial exigida pelo AIOSEO. O rollback restaurou conteudos, CSS e estado
dos plugins. AIOSEO e status nao tinham sido alterados.

## LPV Deploy Shield

O novo gate e o MU-plugin temporario
`wp-content/mu-plugins/lpv-deploy-shield.php`, renderizado a partir de
`wordpress/deploy/lpv-deploy-shield.php`.

- O frontend publico recebe HTTP 503, texto neutro e `Retry-After: 120`.
- REST sem o header efemero recebe 503.
- Token correto sem autenticacao WordPress continua sem permissao de edicao.
- REST do deploy exige simultaneamente Application Password e o header efemero.
- WP-CLI retorna antes do registro dos hooks; admin, cron e AJAX permanecem
  disponiveis apenas para as operacoes tecnicamente necessarias.
- O token e criado com gerador criptografico, fica em texto claro somente na
  memoria do processo e nao entra em URL, arquivo, JSON ou log.
- O MU-plugin recebe somente SHA-256 do token e timestamp de expiracao.
- A expiracao de 15 minutos e failsafe; remocao normal e obrigatoria no fluxo,
  rollback e `finally`. Arquivo remanescente e bloqueador critico.

## Journal e rollback

Cada tentativa persiste fora do Git o journal sem segredos:

`template_plugin_changed`, `language_plugin_changed`, `css_changed`,
`content_changed_ids`, `aioseo_changed_ids`, `status_changed_ids`,
`deploy_shield_installed`, `application_password_created` e `cache_purged`.

O rollback atua apenas sobre entradas registradas. Lista AIOSEO vazia produz
`NOT REQUIRED`, nao erro. Conteudo e status sao restaurados somente para os IDs
registrados. Remocao repetida do shield, maintenance ja desligado e CSS ja no
hash original sao sucessos idempotentes. A excecao primaria e preservada
separadamente das falhas secundarias. Antes do rollback, o journal e reconciliado
por leitura remota para capturar uma escrita concluida cuja confirmacao de rede
tenha falhado.

Os plugins LPV existentes sao comparados arquivo a arquivo com os ZIPs
aprovados. Quando os hashes coincidem, o deploy somente os ativa. Reinstalacao
ocorre apenas se estiverem ausentes ou divergentes, e essa mudanca entra no
journal para rollback.

## LiteSpeed 7.9.1

`wp help litespeed-purge` confirmou o subcomando oficial `all`. O codigo
instalado em `cli/purge.cls.php` mostra que ele envia a acao de purge para
`admin-ajax.php` e chama `WP_CLI::error()` quando a resposta nao tem sucesso.
Na tentativa anterior, essa chamada ocorreu dentro do maintenance mode nativo,
explicando o exit code 1.

O shield nao bloqueia `admin-ajax.php`. O executor mantem o comando oficial,
valida seu registro no dry-run e exige exit code zero. A primeira limpeza ocorre
logo apos instalar o shield, para impedir que cache anterior contorne o PHP; a
segunda ocorre apos as alteracoes e antes da remocao do shield. O relatorio
registra somente tamanho e SHA-256 da resposta do comando.

## Ordem preparada

1. Preflight, baseline, backup e dry-run aprovados.
2. Upload privado do pacote e helpers.
3. Criacao da Application Password temporaria.
4. Instalacao do shield, purge preventivo e provas 503/REST autorizada.
5. Ativacao e verificacao individual dos dois plugins LPV.
6. CSS, 22 conteudos, AIOSEO e status EN, com journal incremental.
7. Purge final protegido, remocao do shield e homepage HTTP 200.
8. Auditoria publica completa.
9. Revogacao da Application Password e verificacao final do shield no `finally`.

## Testes

A suite Python cobre o servidor REST local protegido, incluindo REST publica,
token incorreto, token sem autenticacao, autenticacao dupla, escrita AIOSEO
simulada e leitura de confirmacao. Tambem cobre journal vazio, rollback
idempotente, preservacao da causa primaria, falha durante deploy, remocao em
`finally`, revogacao e ausencia do token nos artefatos/erros.

O harness PHP valida no PHP 8.2: sintaxe, hooks reais, 503 REST, token incorreto,
token correto, texto 503 do frontend, `Retry-After`, expiracao e bypass de
WP-CLI. Ele roda fora do WordPress e nao produz escrita na instalacao.

## Operacao e rollback

Nao executar `--execute` sem novo gate humano. O dry-run deve apontar zero
blockers e registrar o plano do shield e do LiteSpeed. Em incidente, o executor
restaura apenas o journal, remove o shield, revoga a credencial e valida a
auditoria publica. O dump integral continua apenas como contingencia manual.

## Novo gate read-only

- Preflight de producao: APROVADO; maintenance nativo e shield residual ausentes.
- Baseline GET: 22/22 paginas e politica HTTP 200; os 313 achados preexistentes
  foram preservados como referencia anterior ao deploy; zero formularios enviados.
- Backup privado: `20260923T200845Z`, APROVADO, 29 arquivos e manifesto valido;
  conteudo nao versionado.
- Dry-run: APROVADO, zero blockers; 22 conteudos, CSS e 22 metadados AIOSEO
  previstos; zero alteracoes de status EN.
- Plugins LPV: instalados, inativos e byte-identicos aos dois ZIPs aprovados.
- LiteSpeed: `wp help litespeed-purge all` retornou exit code zero e confirmou o
  subcomando oficial; nenhuma limpeza foi executada nesta etapa.
- Deploy em producao: NAO EXECUTADO.
