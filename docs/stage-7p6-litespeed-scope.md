# Etapa 7P.6 - Escopo LiteSpeed e release final

Data: 25/09/2026.

## Causa e contrato confirmado

**LITESPEED PAGE OPTIMIZATION CONFLICT: CONFIRMED.**

Na instalacao LiteSpeed Cache 7.9.1, a leitura remota do codigo instalado
confirmou que `Router::can_optm()` aplica `litespeed_can_optm` e que somente a
inicializacao de `Optimize` depende dessa decisao. Cache, ESI e demais modulos
sao inicializados separadamente em `src/core.cls.php`; `src/optimize.cls.php`
repete a verificacao antes de transformar a resposta.

Referencias oficiais:

- https://docs.litespeedtech.com/lscache/lscwp/api/
- https://docs.litespeedtech.com/lscache/lscwp/pageopt/

O contrato permite retornar `false` para a requisicao atual sem desativar o
plugin ou alterar suas configuracoes globais. Essa conclusao foi obtida de
documentacao oficial e inspecao read-only; nenhum arquivo LiteSpeed foi editado.

## Implementacao 1.0.1

`LPV Page Templates` usa o mesmo mapa aprovado de 22 IDs e caminhos. O filtro
retorna `false` apenas quando todas estas identidades coincidem:

- requisicao singular de pagina;
- ID consultado presente no allowlist;
- permalink com o caminho aprovado;
- request path exatamente igual, apos remover query string e normalizar apenas
  trailing slash e percent encoding seguro de caracteres nao reservados;
- tema ativo Twenty Twenty-Five e block theme;
- homepage ID 7 com a configuracao de leitura aprovada.

Qualquer outra requisicao conserva literalmente o valor recebido. Nao ha
substring, prefixo global, escrita de option, chamada externa, mudanca no tema,
`.htaccess`, CSS, conteudo, imagens, SEO, formulario ou analytics.

Exclusoes explicitas: wp-admin, wp-login, wp-json/REST, admin-ajax, cron, feed,
embed, preview, search, 404, posts, politica e paginas nao mapeadas. A rota `/`
so coincide quando o objeto consultado tambem e a homepage ID 7.

## Cache e aceite

Page Optimization e page cache sao contratos separados. O deploy final exige:

1. plugin LiteSpeed ativo e purge via CLI registrado;
2. hashes de todas as options estaveis `litespeed%` identicos antes e depois;
3. scripts LPV preservados na resposta publica normal e em `before_optm`;
4. browser runtime 22/22 sem page errors nem
   `Configuration data not found`;
5. duas leituras por pagina com HTTP 200 e headers HIT/MISS registrados como
   diagnostico, sem tornar HIT 22/22 um requisito absoluto;
6. politica, busca, 404 e post fora do template LPV.

O teste de navegador bloqueia FormSubmit, WhatsApp, GA/GTM e POST externo.
Nenhum formulario real e enviado e nenhuma coleta analitica real e produzida.

## Empacotamento e rollback

O ZIP `lpv-page-templates-1.0.1.zip` e deterministico e coberto pelo manifesto
do pacote Stage 6. O plugin de idiomas permanece 1.0.0 sem alteracao. O deploy
so pode usar backup novo validado e o pacote cujo hash foi aprovado no dry-run.

Em qualquer falha, o rollback reinstala os arquivos anteriores do plugin,
restaura os componentes registrados no journal, limpa cache, remove o shield,
revoga a credencial temporaria e comprova o fingerprint material. Configuracao
global LiteSpeed nao faz parte das escritas planejadas e qualquer mudanca nos
seus hashes estaveis e bloqueadora. `litespeed.optimize.timestamp_purge_css`
fica fora do fingerprint material somente porque o purge oficial o atualiza;
seu valor numerico e sua janela temporal continuam validados e documentados.
