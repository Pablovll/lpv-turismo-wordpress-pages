# Etapa 6 - Integracao WordPress e staging

Versao 1.0.0. Referencia: 22/09/2026. Entrega local para revisao e aplicacao
manual em staging. Nao e deploy nem autorizacao para publicar automaticamente.
Este runbook substitui a criacao/atribuicao manual de templates da Etapa 4.

## Estado aprovado e fontes

22 paginas autorizadas editorialmente: PT 8, ES 7, EN 7. EN pode ter status
publish apos aplicacao e conferencia manual. Yoast removido; AIOSEO e o unico
responsavel por canonical, title, description, Open Graph, Twitter Cards e
schema. Politica publicada em `/politica-de-privacidade/`, fora das 22 paginas.
Nao recriar a politica nem suas traducoes. A fonte juridica informada na
Etapa 4 continua externa ao checkout; nao e substituida por esta entrega.

Fontes lidas: AGENTS.md; auditoria da Etapa 3; checklist, inventario e mapas
de idiomas da Etapa 4; docs/page-map.json; documentacao da Etapa 5; template
minimo existente e README do LPV Language SEO. Os IDs, URLs, imagens, textos,
formulario, CSS e plugin de idiomas aprovados permanecem inalterados.

## Auditoria da estrutura

O `templates/page.html` padrao do Twenty Twenty-Five referencia Header,
grupo main com margem superior e grupo interno com padding, imagem destacada,
Post Title nivel 1, Post Content com largura constrained e Footer. Header e
Footer sao partes compartilhadas; o titulo vem de `core/post-title`, nao do
HTML comercial. Ocultar esses blocos por CSS nao impede sua geracao.

A observacao publica arquivada na Etapa 4 identificou blocos nativos junto
ao header/footer/H1 LPV. Isso e evidencia historica do HTML recebido, nao uma
inspecao atual do banco. Sem painel/banco nao se conhece o template realmente
atribuido, suas personalizacoes ou a configuracao atual de Leitura. Nenhuma
nova consulta autenticada ou aplicacao remota foi feita nesta etapa.

O template minimo ja existente contem apenas `core/group` com tag main,
largura full, layout default e espacamentos zero, e um `core/post-content`.
Foi preservado integralmente. Os 22 fragmentos fornecem cada um um H1,
header.topbar e footer.lpv-site-footer, sem main proprio. A composicao local
esperada tem exatamente um de cada, sem Post Title, imagem destacada ou partes
nativas extras. Nao copiar os fragmentos para dentro do template.

## Decisao de implementacao

Plugin separado **LPV Page Templates 1.0.0**, WordPress 6.7+/PHP 7.4+.
Registra `lpv-page-templates//lpv-content-only` pela API nativa. Filtra somente
`page_template_hierarchy` e `frontpage_template_hierarchy` para as 22 paginas
identificadas por ID E caminho aprovado. A origem local do template e fixa;
nao recebe entradas HTTP, nao grava no banco e nao faz chamadas externas.
Nao possui renderer de documento proprio nem adiciona SEO, CSS ou scripts.
O canvas do WordPress preserva `language_attributes`, `wp_head`,
`wp_body_open` e `wp_footer`.

Foi preferido ao tema filho para nao trocar o tema ativo nem mudar a associacao
de CSS adicional/estilos globais ao tema. Twenty Twenty-Five e seus arquivos
permanecem intactos. Politica, posts, arquivos, busca e 404 nao sao selecionados
automaticamente. O plugin nao deve ser atribuido manualmente a essas paginas.

### Homepage / Front Page

Configuracao exigida: `show_on_front=page` e `page_on_front=7`. A homepage PT
passa pelo filtro **frontpage**, pois Front Page tem precedencia sobre a
atribuicao individual. O plugin prioriza o mesmo template minimo nessa
hierarquia. Nao reescreve globalmente `front-page.html`, nao modifica Leitura
e nao aplica esse comportamento a um indice de posts ou outra homepage.
ES ID 20 e EN ID 21 continuam paginas comuns pela hierarquia **page**.
Configuracao divergente deve ser corrigida manualmente apos backup ou
submetida a revisao; nunca criar uma nova homepage para contornar o mapa.

### Sobreposicoes e CSS

Um template salvo no banco ou arquivo do tema/tema filho com slug
`lpv-content-only` pode substituir o modelo do plugin. Exportar e conferir
somente essa personalizacao antes de ativar. Se for uma copia antiga a
substituir, limpar apenas essa personalizacao no Site Editor apos backup.
Nao apagar Header/Footer compartilhados nem resetar todos os templates.
Nao editar/salvar o novo modelo no Site Editor; manter a fonte no Git.
Filtros tardios de outros plugins tambem devem ser investigados se o modelo
resolvido divergir. Nao removemos filtros de terceiros indiscriminadamente.

O CSS defensivo antigo permanece como aprovado, inclusive regras amplas
`body.wp-singular`. O novo template remove os blocos na origem e nao depende
dessas regras. Verificar separadamente a politica, que nao esta no mapa,
antes de propor qualquer reducao desse CSS em outra tarefa.

## Arquivos e responsabilidades

| Componente / arquivo | Responsabilidade |
| --- | --- |
| `wordpress/plugins/lpv-page-templates/lpv-page-templates.php` | Registro e selecao restrita do template, sem escrita no banco |
| `wordpress/plugins/lpv-page-templates/templates/lpv-content-only.html` | Copia byte-identica do template minimo existente |
| `wordpress/plugins/lpv-page-templates/README.md` | Instalacao, escopo, limites e rollback do layout |
| `scripts/build_staging_package.py` | Empacotamento local deterministico com hashes SHA-256 |
| `tests/test_stage6_integration.py` | Mapas, estrutura esperada, escopo, pacotes e PHP |
| `tests/php/test_lpv_page_templates.php` | Hooks, registro, parser e resolucao nativos com fixtures |
| `docs/stage-4-wordpress-checklist.md` | Referencia ao procedimento atual, sem apagar historico |
| `docs/stage-6-wordpress-integration.md` | Este runbook e aceite manual |
| `publication/stage-6/` e `publication/lpv-wordpress-stage-6.zip` | Pacote consolidado, sem implantacao automatica |
| `publication/stage-4/` e ZIP da Etapa 4 | Reconstruidos com a referencia documental atualizada |
| LPV Language SEO 1.0.0, sem alteracoes | Somente lang/hreflang; conferir publicacao/permalinks em runtime |
| AIOSEO, aplicacao manual | Unica origem dos seis tipos de metadados SEO aprovados |
| Site Kit, aplicacao manual | Integracao existente de analytics; nenhum novo snippet nesta entrega |
| LiteSpeed/CDN, operador | Invalidacao de caches e verificacao do HTML realmente servido |
| Proprietario/operador WordPress | Backup, staging, configuracoes, insercao de conteudo e aceite final |

`docs/page-map.json`, as fontes HTML/CSS, template original e codigo/documentacao
do plugin de idiomas nao precisaram de alteracao. O pacote da Etapa 5 deve
reconstruir identico. Nenhum framework, endpoint ou URL de imagem foi trocado.

## Pacote de staging

`publication/lpv-wordpress-stage-6.zip` e um pacote de trabalho, NAO um plugin
para enviar inteiro ao WordPress. Extrair localmente; somente os dois ZIPs
em `plugins/` sao instalaveis em Plugins > Adicionar plugin.

- `plugins/lpv-page-templates-1.0.0.zip`: template e selecao de layout.
- `plugins/lpv-language-seo-1.0.0.zip`: arquivo identico ao aprovado na Etapa 5.
- `html/`: 22 fragmentos byte-identicos as fontes; nao inserir documentos completos.
- `css/lpv-style.css`: CSS final identico ao pacote da Etapa 4.
- `aioseo-metadata.json` e CSV: tabela aprovada, sem alteracao de texto.
- `language-map.json`, `url-map.json`, `PAGE-INVENTORY.md`: equivalencias e IDs.
- `wordpress/lpv-content-only.html`: referencia do template, nao conteudo da pagina.
- `application-plan.json`: ordem e escopo; inventario declarativo, nao executor.
- `RUNBOOK.md`, READMEs, `STRUCTURAL-VALIDATION.json`, `manifest.json`: instrucoes e hashes.

Nao inclui tags hreflang estaticas para colar: a unica origem sera o plugin.
O CSV de AIOSEO e tabela de conferencia manual, nao importador nativo garantido.
Nenhum backup real nem credencial faz parte do Git/pacote.

## Sequencia exata de staging

A ordem prevista esta correta para um ambiente isolado. Fazer uma unica rodada
controlada; nao deixar templates novos ativos com conteudos antigos em producao.

1. **Backup e preflight.** Exportar banco e arquivos, CSS adicional, estilos
   globais, templates/atribuicoes, Leitura, AIOSEO e configuracoes dos plugins.
   Guardar fora do repositorio e testar restauracao. Clonar mantendo IDs e
   caminhos na raiz de outro dominio. Conferir versoes/tema e todas as 22
   correspondencias. Proteger staging por controle de acesso e indexacao
   desativada; isolar e-mails, requisicoes FormSubmit e analytics reais.
   O bloqueio de e-mail do servidor sozinho NAO bloqueia FormSubmit no navegador.
   Usar bloqueio de rede/CSP de staging para `form-action`, sem editar os HTMLs.
2. **Template.** Conferir homepage estatica ID 7 e ausencia de sobreposicao
   `lpv-content-only`. Instalar/ativar LPV Page Templates. Nao criar outro
   template manual ou mudar tema. Conferir que Post Content foi preservado;
   a composicao final so sera avaliada apos inserir os HTMLs desta versao.
3. **Plugin de idioma.** Instalar/ativar LPV Language SEO 1.0.0. Procurar e
   desativar somente emissores concorrentes de lang/hreflang, nao AIOSEO.
   Nao colar as tags estaticas do pacote antigo. Sem novo SEO/analytics/formulario.
4. **CSS.** Exportar a versao atual e aplicar o CSS final da Etapa 4 no local
   existente, sem acumular varias copias. Nao modificar imagens ou identidade.
5. **HTML.** Aplicar cada fragmento ao ID correspondente do mapa, mantendo
   slugs, hierarquia, status deliberado e conteudo aprovado. Usar o modo de
   edicao HTML existente, sem converter para blocos que reescrevam o markup.
   Conferir o conteudo salvo: permissoes/filtros do WordPress podem sanitizar
   scripts, formularios ou estilos. Nao contornar seguranca sem revisao.
6. **AIOSEO.** Conferir Yoast ausente. Aplicar title/description literais e
   conferir canonical self, Open Graph, Twitter Cards e schema sem duplicacao.
   Os canonicals do mapa sao os finais de producao: nao indexar staging ou
   mudar o mapa para seu dominio. Manter noindex/protecao do staging e revisar
   explicitamente as configuracoes de dominio/indexacao na futura producao.
7. **Status EN.** Verificar os sete IDs EN e definir/conferir publish no clone
   protegido. A autorizacao editorial ja existe, mas nao dispensa o aceite
   tecnico. O mapa e estado desejado, nao prova de publicacao atual.
8. **Limpeza de cache.** Executar o procedimento abaixo apos todas as etapas.
9. **Auditoria do HTML servido.** Conferir as 22 paginas e a politica, com
   caches renovados, pelo frontend protegido de staging (nao tornar publico).
   Registrar evidencias e pendencias. Produzir aceite para janela posterior
   de producao; nao promover automaticamente o clone inteiro ou este pacote.

### LiteSpeed Cache

Em LiteSpeed Cache > Toolbox/Ferramentas > Purge/Limpar, usar **Purge All**
apos a rodada. Se CSS/JS otimizado, Critical CSS ou Unique CSS permanecerem
antigos, limpar os respectivos caches disponiveis e aguardar regeneracao
antes de avaliar. Limpar tambem cache de CDN/proxy quando houver, e recarregar
em navegador sem cache. Nao usar **Empty Entire Cache**, reset de configuracoes,
limpeza de banco ou OPcache como passos indiscriminados desta entrega.
Repetir a limpeza apos rollback e em todo grupo de traducoes quando publicar,
despublicar ou proteger uma pagina. Comparar HTML bruto e cabecalhos de cache,
nao somente aparencia ou sessao autenticada com cache ignorado.

### Idiomas e isolamento de staging

No dominio diferente ou com `blog_public=0`, ausencia de hreflang e intencional
no LPV Language SEO. `lang` continua testavel pelos IDs. Nao liberar indexacao
do staging para forcar alternates. Testar conjuntos completos com o harness
offline ou ambiente isolado que simule as URLs oficiais. Na futura producao,
conferir reciprocidade de sete trios e PT/x-default apenas para L&P.
Noindex individual do AIOSEO nao e consultado pelo plugin: e verificacao
manual obrigatoria, assim como canonical, robots e sitemap reais.

Site Kit continua dependente dos hooks nativos. Nenhum snippet novo e incluido.
Nao considerar hooks presentes como prova de eventos corretos no GA. Manter
coleta de producao bloqueada em staging; GA DebugView fica para teste separado.

## Testes locais

Executar builds das Etapas 4, 5 e 6 antes dos testes de integridade:

```powershell
python scripts/build_wordpress_package.py
python scripts/build_language_plugin_package.py
python scripts/build_staging_package.py
$env:PHP_BINARY = 'C:/caminho/php.exe'
$env:WP_CORE_DIR = 'C:/caminho/wordpress-6.2'
$env:WP_TEMPLATE_CORE_DIR = 'C:/caminho/wordpress-6.7'
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Ambiente local de referencia: PHP 8.3.35, core WordPress 6.2 para Etapa 5 e
6.7 para Etapa 6, obtidos de distribuicoes oficiais fora do repositorio.
Esses cores sao fixtures de compatibilidade, nao recomendacao para instalar
versoes antigas em um servidor publico. Nenhum WordPress completo foi iniciado.

Resultados da rodada completa:

- 29 testes Python passaram, sem skips: 11 Etapa 4, 9 Etapa 5, 9 Etapa 6.
- Harness de idiomas: 1.368 assercoes passaram, sem alterar o plugin aprovado.
- Harness de templates: 185 assercoes passaram, incluindo homepage, IDs/caminhos,
  exclusoes, precedencia de personalizacao e retirada dos filtros no rollback.
- PHP lint dos dois plugins e dos dois harnesses passou; acesso direto aos
  plugins termina sem saida. Runtime PHP 8.3.35, nao uma matriz de todas as versoes PHP.
- Estrutura esperada das 22 composicoes: um main/H1/header LPV/footer LPV;
  tags balanceadas; template original e copia identicos.
- Builds Etapas 4, 5 e 6 executados; manifestos SHA-256 e conteudo dos ZIPs
  conferidos. Repetir o build da Etapa 6 produz exatamente os mesmos bytes.
- Fontes HTML/CSS, mapa de paginas, template original, plugin e pacote da
  Etapa 5 comparados com HEAD: nenhuma alteracao.
- `git diff --check` sem erros na revisao local.

O harness do template usa hooks,
registro/consulta/resolucao e parser de blocos reais do core, com contexto,
tema sem arquivos e consulta de banco vazia simulados. A composicao dos 22
fragmentos e estrutural: nao executa `core/post-content` em um WordPress real.

## Revisao Git

Branch: `codex/lpv-language-seo`. Commit previsto apos revisao e verificacoes:
`Prepare LPV WordPress staging integration`. Conferir `git status`, `git diff`
e `git diff --check`, revisar o indice completo e enviar sem force push ou merge
na main. Hash e resultado efetivo do push sao informados no encerramento.

## Rollback

1. Interromper aplicacao, manter staging isolado e registrar a falha sem dados pessoais.
2. Desativar LPV Page Templates para voltar a hierarquia anterior. Sem painel,
   renomear somente sua pasta via acesso autorizado. Nao altera atribuicoes
   persistentes; se um operador salvou/atribuiu o modelo, restaurar esse item
   do backup tambem. Conferir homepage e uma interna apos limpar caches.
3. Se a falha for de idiomas, desativar LPV Language SEO separadamente e
   restaurar sua versao anterior. Nao reativar Yoast ou duplicar hreflang.
4. Restaurar HTML, CSS, status EN e configuracoes AIOSEO/Leitura alterados
   a partir do mesmo backup, somente nos itens envolvidos. Desativar plugin
   nao desfaz conteudo nem CSS. Usar restauracao integral somente se necessaria
   e controlada, sem sobrescrever dados recentes de producao.
5. Limpar LiteSpeed/CDN/navegador e repetir verificacao de estrutura/URLs.
   Documentar resultado antes de reabrir qualquer janela de aplicacao.

## Aceite manual e riscos restantes

- [ ] Backup restaurado em teste; IDs/caminhos e Leitura conferidos no banco/painel.
- [ ] Modelo efetivo correto nas 22 paginas, sem sobreposicao do Site Editor/tema.
- [ ] HTML bruto: 1 main, 1 H1, 1 header.topbar, 1 footer.lpv-site-footer; zero
  Post Title, Header/Footer e imagem destacada nativos duplicados. Confirmar
  ausencia no DOM mesmo com regras display:none desabilitadas no inspetor.
- [ ] Post Content e 22 fragmentos preservados; scripts/formularios nao sanitizados.
- [ ] Skip link aponta para o unico main; teclado/foco/Escape, 375 px, desktop,
  menu/rodape, imagens, overflow e zoom real 200% conferidos.
- [ ] Politica legivel e acessivel em todos os rodapes; seus templates e os de
  posts, busca, arquivo e 404 nao foram substituidos pelo plugin.
- [ ] lang correto; sete grupos reciprocos quando as condicoes de producao
  forem simuladas isoladamente; L&P somente PT/x-default, sem EN/ES artificial.
- [ ] AIOSEO real: um emissor por tipo, canonical correto, robots/sitemap/social
  e schema coerentes. Sem metadados concorrentes dos plugins LPV.
- [ ] LiteSpeed real/CDN sem HTML ou CSS antigos apos purge; rollback validado.
- [ ] FormSubmit e WhatsApp apenas inspecionados, sem envio. Teste real de entrega
  de FormSubmit exige outra autorizacao; GA DebugView igualmente pendente.
- [ ] Aprovacao tecnica registrada antes de aplicar em producao, sem merge/deploy automaticos.

Nao testados nesta entrega: WordPress real, AIOSEO real, LiteSpeed real,
Site Kit/GA DebugView, entrega FormSubmit e zoom 200%. Nao confundir os testes
offline, a previa estatica local ou o estado editorial aprovado com esse aceite.

## Fontes tecnicas

- [Twenty Twenty-Five: template page padrao](https://github.com/WordPress/twentytwentyfive/blob/trunk/templates/page.html).
- [Registro nativo de block templates, desde WP 6.7](https://developer.wordpress.org/reference/functions/register_block_template/).
- [Hierarquia especifica de Front Page](https://developer.wordpress.org/reference/functions/get_front_page_template/).
- [Consulta e precedencia de templates no core 6.7](https://github.com/WordPress/WordPress/blob/6.7/wp-includes/block-template-utils.php).
- [Canvas nativo e hooks preservados](https://github.com/WordPress/WordPress/blob/6.7/wp-includes/template-canvas.php).
- [LiteSpeed: Toolbox e Purge](https://docs.litespeedtech.com/lscache/lscwp/toolbox/).
