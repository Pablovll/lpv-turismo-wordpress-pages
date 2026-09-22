# LPV Page Templates 1.0.0

Etapa 6, 22/09/2026. Preparado localmente; nao instalado no WordPress.
Requer WordPress 6.7+, PHP 7.4+ e Twenty Twenty-Five ativo (ou tema filho dele).

## Escopo

Registra `lpv-page-templates//lpv-content-only` com `register_block_template`.
Os filtros nativos `page_template_hierarchy` e `frontpage_template_hierarchy`
priorizam `lpv-content-only.php` (slug de resolucao, nao um arquivo PHP) somente
para os 22 IDs e caminhos aprovados. O core resolve o bloco HTML e usa seu
proprio canvas, preservando `language_attributes`, `wp_head`, `wp_body_open`
e `wp_footer`. Nao ha renderer HTML alternativo.

O template tem um grupo `main` sem espacamento extra e um `core/post-content`.
Nao inclui `core/template-part` header/footer, `core/post-title` nem imagem
destacada. Cada fragmento aprovado ja fornece um H1, header LPV e footer LPV.
Nao editar o tema pai, nao trocar tema e nao apagar as partes compartilhadas:
elas continuam disponiveis para politica, posts, busca, 404 e outras paginas.

A selecao exige ID E caminho. Aceita outro dominio de staging com a mesma
estrutura na raiz, mas nao IDs novos, caminhos alterados ou instalacao em
subdiretorio. Falhas de correspondencia deixam o template anterior atuar;
devem bloquear a liberacao ate revisao, nao justificar mudar URLs aprovadas.

## Homepage

Em Configuracoes > Leitura, a homepage deve ser uma pagina estatica de ID 7:
`show_on_front=page`, `page_on_front=7`. O filtro `frontpage_template_hierarchy`
e necessario porque Front Page precede o template individual da pagina.
ES (20) e EN (21) usam `page_template_hierarchy`. Nao trata indice de posts
nem muda configuracoes de Leitura. Preview de pagina mapeada pode usar o
layout; feed/embed/painel e paginas fora do mapa nao sao selecionados.

## Instalacao em staging

1. Fazer backup restauravel de banco, uploads, temas, plugins, CSS adicional,
   estilos globais, templates salvos, configuracoes de Leitura e AIOSEO.
2. Clonar com os mesmos IDs/caminhos e manter staging protegido e nao indexavel.
   Bloquear envio de e-mails/formularios e coleta real de analytics na camada
   de staging. Nao alterar as URLs de imagens ou os fragmentos aprovados.
3. Conferir os 22 IDs/URLs no mapa e os requisitos de versao/tema.
4. Antes de ativar, procurar `lpv-content-only` nos templates do tema/tema filho
   e em Aparencia > Editor > Design > Modelos. Uma copia salva no banco ou
   arquivo do tema com esse slug tem precedencia sobre o registro do plugin.
   Exportar essa copia; limpar SOMENTE essa personalizacao se confirmado que
   deve ser substituida. Nao apagar todos os templates ou partes do tema.
5. Instalar `lpv-page-templates-1.0.0.zip` em Plugins > Adicionar plugin e ativar.
   Nao atribuir manualmente este modelo a paginas fora do mapa, nem editar o
   modelo no Site Editor: isso cria uma sobreposicao persistente no banco.
6. Seguir o runbook da Etapa 6: idioma, CSS, HTML, AIOSEO, status EN e cache.
   O plugin nao escreve opcoes, metadados, templates ou conteudo no banco.

## Conflitos

- Twenty Twenty-Five: personalizacao do mesmo slug ou filtros tardios podem
  substituir a selecao. Conferir o modelo efetivamente resolvido e o HTML bruto.
  Nao remove CSS defensivo existente; a ausencia de duplicacao deve ser
  demonstrada no DOM, mesmo com as regras de ocultacao desabilitadas.
- AIOSEO: continua dono exclusivo de SEO. Nenhuma tag de SEO e produzida aqui.
- LPV Language SEO: independente; permanece 1.0.0, somente lang/hreflang.
  Em staging de outro dominio/noindex global, nao emitir hreflang e esperado.
- Site Kit: hooks nativos preservados. Nao adicionar segundo snippet de GA;
  proteger staging de envio de eventos reais. Validar manualmente depois.
- LiteSpeed/CDN: caches antigos podem continuar servindo o template anterior.
  Limpar apos a aplicacao e apos rollback. Nao usar minificacao como correcao
  de markup nem alterar opcoes de otimizacao sem comparacao controlada.

## Rollback

Desativar somente LPV Page Templates e limpar caches. Sem acesso ao painel,
renomear sua pasta via SFTP/gerenciador autorizado. Como o plugin nao grava
atribuicoes, os templates anteriores voltam a ser resolvidos. Se um operador
salvou ou atribuiu manualmente este modelo, restaurar tambem a personalizacao
e a atribuicao exportadas. A desativacao nao desfaz HTML/CSS editados: restaurar
essas partes e as configuracoes a partir do backup correspondente. Nao
reativar Yoast nem apagar AIOSEO/LPV Language SEO como parte deste rollback.

## Checklist de aceite

- [ ] As 22 paginas usam o modelo LPV; homepage estatica ID 7 incluida.
- [ ] HTML bruto tem um main, um H1, um header.topbar e um footer.lpv-site-footer.
- [ ] Nao ha Header/Footer nativos, Post Title ou featured image duplicados.
- [ ] Post Content permanece e nenhum fragmento aprovado foi truncado/sanitizado.
- [ ] Politica, posts, busca e 404 continuam usando seus templates anteriores.
- [ ] Conferir desktop, 375 px, teclado e zoom 200%; nao enviar formularios reais.
- [ ] AIOSEO, idiomas e Site Kit conferidos sem duplicar tags.
- [ ] Cache e rollback verificados em staging antes de qualquer producao.

## Testes locais

`python -m unittest discover -s tests -p 'test_*.py' -v`.
Definir `PHP_BINARY`, `WP_CORE_DIR` (6.2+ para Etapa 5) e
`WP_TEMPLATE_CORE_DIR` (6.7+ para Etapa 6). O harness usa hooks, registro,
consulta/resolucao de templates e parser de blocos do core real, com fixtures
de contexto, tema e banco vazio. Nao inicializa WordPress nem testa AIOSEO,
LiteSpeed, Site Kit, banco real ou renderizacao completa dos blocos.

Fonte do template: `wordpress/templates/lpv-content-only.html`; a copia neste
plugin deve ser byte-identica. Build e testes rejeitam divergencia.
