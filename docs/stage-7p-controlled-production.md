# Etapa 7P - Deploy controlado em producao

Data de preparacao: 23/09/2026. Branch: `codex/lpv-language-seo`.
Este documento registra o fluxo automatizado e reversivel para o WordPress
oficial. Nao contem credenciais, chaves, senhas, dumps ou dados pessoais.

## Alvo confirmado

- Host SSH: alias local `lpv-prod` (credencial fora do repositorio).
- WordPress: `/home/u504635074/domains/lpvturismo.com/public_html`.
- Home e site URL: `https://lpvturismo.com`.
- WordPress 7.0.5; PHP 8.2.33; Twenty Twenty-Five 1.5.
- AIOSEO 5.0.1.1 e LiteSpeed Cache 7.9.1 ativos.
- `show_on_front=page`; `page_on_front=7`; Yoast ausente.
- IDs, tipos e caminhos das 22 paginas conferidos em modo somente leitura.

## Componentes versionados

- `scripts/preflight_production.py`: pacote, historico sensivel e compatibilidade remota.
- `scripts/audit_production.py`: GET publico, sem login, JavaScript ou formularios.
- `scripts/backup_production.py`: dump integral, estado WordPress e manifesto SHA-256 privados.
- `scripts/deploy_production.py`: dry-run, execucao por checkpoints e rollback granular.
- `wordpress/deploy/`: inventario e aplicadores PHP pelas APIs nativas.

As pastas `.production-evidence/` e `.production-private-backup/` sao ignoradas
pelo Git. O banco completo fica apenas no backup local privado e serve como
contingencia; o rollback normal restaura conteudo, status, CSS, AIOSEO e plugins
por componente. Nenhuma edicao e feita no Twenty Twenty-Five.

O Hostinger desativa `proc_open()` no PHP CLI, impedindo `wp db export` de
iniciar o `mysqldump`. O fallback versionado obtem as constantes com WP-CLI,
mantem a senha somente no ambiente do processo remoto e transmite a saida do
`mysqldump` diretamente ao gzip local. Nenhum SQL temporario e criado no host.

## Seguranca e APIs

O HTML usa `wp_update_post()` e confirma o hash salvo. O CSS usa
`wp_update_custom_css_post()`. AIOSEO 5.0.1.1 expoe o campo oficial
`aioseo_meta_data` no endpoint `wp/v2/pages`; title e description sao aplicados
por REST. A Application Password temporaria e o token efemero existem somente
em memoria e sao revogados/descartados em `finally`. Canonical, Open Graph,
Twitter Cards e schema nao sao gerados pelo deployer e permanecem sob
responsabilidade do AIOSEO.

O deploy exige literalmente `DEPLOY LPV PRODUCAO`, revalida o hash do pacote e
o estado respaldado e usa o MU-plugin temporario LPV Deploy Shield durante a
janela critica. O maintenance mode nativo nao e mais usado como gate. O shield
devolve 503 no frontend e na REST publica, permite WP-CLI e exige Application
Password mais token efemero para a REST do deploy. O arquivo possui expiracao
de 15 minutos e e removido no rollback e no `finally`.

O LiteSpeed usa o subcomando oficial confirmado `wp litespeed-purge all`. Como
essa versao implementa o comando por uma requisicao a `admin-ajax.php`, a
limpeza e feita com o shield ativo, que libera AJAX administrativo. O cache e
limpo uma vez antes de comprovar o 503, evitando uma resposta antiga servida
antes do PHP, e novamente depois das alteracoes, antes de remover o shield. Um
bloqueador no auditor pos-deploy inicia rollback granular automatico; o dump
nao e importado automaticamente. Detalhes: `docs/stage-7p2-deploy-shield.md`.

## Estado da rodada

Os resultados de preflight, baseline, backup e dry-run sao mantidos fora do
Git. A primeira tentativa autorizada foi bloqueada no checkpoint CSS e a
segunda no checkpoint AIOSEO, porque o maintenance mode nativo devolveu 503
para a REST. As duas executaram rollback e a producao voltou ao baseline. Os
diagnosticos estao em `docs/stage-7p1-post-rollback-diagnosis.md` e
`docs/stage-7p2-deploy-shield.md`.

- Deploy em producao: BLOQUEADO / REVERTIDO.
- Commit implantado: NENHUM.
- Plugins LPV: instalados, byte-identicos aos pacotes e inativos.
- 22 paginas aplicadas: NAO; conteudos originais preservados.
- Sete paginas EN: ja estavam publicadas; nenhum status mudou.
- CSS: restaurado ao hash original.
- SEO: valores originais preservados.
- Cache de conclusao: o comando falhou durante o rollback da segunda tentativa;
  a causa foi diagnosticada, sem executar nova limpeza nesta etapa.
- Auditoria pos-rollback: baseline restaurado.
- Rollback executado: PARCIAL no relatorio da segunda tentativa por AIOSEO nao
  requerido e purge falho; verificacao posterior confirmou baseline restaurado,
  plugins aprovados instalados e inativos e nenhuma credencial temporaria.
- FormSubmit: NAO TESTADO.
- GA DebugView: NAO TESTADO.
- Zoom real 200%: NAO TESTADO.
