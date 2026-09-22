# LPV Language SEO

Integração local da Etapa 5. WordPress 6.2+ e PHP 7.4+. Não foi instalada no site oficial.

## Escopo

- `language_attributes`: define `lang` como pt-BR, es ou en apenas nas 22 páginas mapeadas. Preserva `dir`, `prefix` e os demais atributos; mantém `xml:lang` consistente quando existente ou em XHTML, usando a HTML API nativa e seu escape de atributos.
- `wp_head`: escreve somente `<link rel="alternate" hreflang="...">`, com `esc_attr` e `esc_url`.
- As sete famílias multilíngues usam os IDs e URLs aprovados na Etapa 4. L&P (ID 255) recebe apenas pt-BR e x-default, quando pública.
- Confere o estado real no banco em cada requisição: página existente, tipo page, publish, pública, sem senha e permalink igual ao aprovado. Uma tradução indisponível sai do conjunto de todos os equivalentes; quando PT sai, x-default também sai. Os restantes continuam recíprocos, incluindo self-reference.
- Não emite alternates em previews, embeds, feeds, admin, páginas não mapeadas, paginação ou site com indexação global desativada. `lang` pode ser corrigido na prévia de uma página mapeada, mas ela não recebe alternates.
- Não usa URLs de parâmetros, fallback de navegação, chamadas HTTP, cron, cookies, sessões, tabelas próprias ou escrita no banco.

Canonical, title, description, Open Graph, Twitter Cards e schema ficam exclusivamente no AIOSEO. O plugin não lê nem altera configurações do AIOSEO e não modifica o locale global do WordPress.

## Instalação manual

1. Fazer backup dos plugins, banco e configurações. Usar primeiro uma cópia de homologação; não instalar automaticamente a partir do GitHub.
2. Conferir a versão de WordPress/PHP e os IDs/permalinks em `docs/stage-4-language-map.json`. Não editar esses IDs para outra instalação sem revisão do mapa e testes.
3. Procurar outros emissores de hreflang: plugin multilíngue, snippets, tema filho e tags estáticas da Etapa 4. Escolher esta integração como única origem e desativar somente a saída concorrente, sem desativar AIOSEO. Não colar os arquivos `hreflang/{id}.html` no HEAD junto com este plugin.
4. Copiar a pasta `lpv-language-seo` para `wp-content/plugins/`. Alternativamente, instalar o ZIP gerado por `python scripts/build_language_plugin_package.py`, em Plugins > Adicionar plugin > Enviar plugin.
5. Ativar **LPV Language SEO** apenas durante a aplicação manual autorizada. Não há configurações nem migrações de banco.
6. Limpar o LiteSpeed Cache e caches de CDN/navegador. Repetir a limpeza de TODO o grupo de traduções após publicar, despublicar, proteger ou mudar uma URL, pois um cache de página pode manter alternates antigos.
7. Conferir o HTML bruto e o checklist abaixo, sem enviar formulários. Salvar a versão anterior do ZIP para rollback.

### Homologação e indexação

Em staging com outro domínio/permalinks ou `blog_public=0`, a ausência de hreflang é intencional. O plugin não anuncia o domínio oficial a partir de IDs não confirmados. Não tornar um staging público/indexável para testar: usar os testes locais ou uma cópia isolada que simule as URLs oficiais. Na aplicação final, conferir as URLs reais.

Noindex individual no AIOSEO e canonical alterado manualmente não são lidos por este plugin; verificar essas configurações antes da liberação. AIOSEO continua sendo o responsável por elas. Este plugin não deve ser usado para autorizar a indexação de conteúdo.

## Conflitos conhecidos

- AIOSEO não gera hreflang por si só. Uma integração multilíngue associada pode gerar: não manter duas origens.
- Outro filtro tardio em `language_attributes` pode sobrescrever o lang. Não se resolve isso removendo filtros de terceiros indiscriminadamente: identificar e configurar a origem concorrente.
- Twenty Twenty-Five usa os hooks nativos do documento; nenhuma edição de tema é necessária para este plugin. Os Header/Footer/Post Title duplicados são uma tarefa independente do template da Etapa 4.
- Alterar prefixos Open Graph, locale do painel, menus ou textos não faz parte desta integração. A política, sem ID incluído nos 22, conserva o idioma definido pelo WordPress.

## Rollback

1. Em Plugins, desativar **LPV Language SEO**. Em falha de acesso ao painel, renomear somente `wp-content/plugins/lpv-language-seo` via gerenciador de arquivos/SFTP.
2. Limpar LiteSpeed/CDN e conferir o HTML: os alternates deste plugin deixam de aparecer; o atributo lang volta ao comportamento anterior do WordPress.
3. Para reverter uma atualização, restaurar a pasta/ZIP da versão anterior e testar antes de reativar. Não é necessário restaurar banco: o plugin não escreve opções nem conteúdo.
4. Não reativar Yoast. AIOSEO e suas configurações permanecem intactos. Uma integração de idiomas anterior só deve voltar se sua reativação for deliberada, sem duplicar emissores.

## Checklist no WordPress

- [ ] Todos os 22 IDs correspondem às páginas e URLs aprovadas; PT/es/en do mapa refletem o idioma real.
- [ ] As sete famílias completas têm quatro alternates cada, com URLs idênticas entre membros e self-reference.
- [ ] L&P tem somente pt-BR e x-default. Nada para `/es/servicios/#lp-experiences` ou EN.
- [ ] Remover EN de publicação na cópia de teste retira EN de todo o trio; recolocar publish restaura EN. Não fazer esse experimento no site oficial.
- [ ] PT indisponível elimina pt-BR e x-default, sem apontar para rascunho. Senha, privado, agendamento, lixeira, página ausente e permalink diferente também excluem o equivalente.
- [ ] Preview não recebe alternates. Busca, posts, política e 404 não ganham mapeamentos inventados.
- [ ] Um único `lang`, preservando `dir`/`prefix`; atributos corretos já no HTML bruto, sem depender de JavaScript.
- [ ] Sem canonical/title/description/OG/Twitter/schema adicionais; AIOSEO continua como único emissor desses elementos.
- [ ] Conferir noindex/canonical individual no AIOSEO; limpar caches de todo o grupo após mudanças de disponibilidade.
- [ ] Header, rodapé, imagens e formulários não mudaram. Não enviar formulários reais.

## Testes locais

```powershell
php -l wordpress/plugins/lpv-language-seo/lpv-language-seo.php
php tests/php/test_lpv_language_seo.php --wordpress-core=C:/caminho/wordpress
python -m unittest discover -s tests -p "test_*.py"
python scripts/build_language_plugin_package.py
```

O harness usa a HTML API e funções de escape reais do core fornecido localmente. Consulta de páginas, opções e contexto de requisição são substituídos por fixtures em memória; não inicia o WordPress, não usa banco, rede ou credenciais. Os testes Python verificam paridade entre o PHP, os mapas e o pacote da Etapa 4. Não substituem o aceite em WordPress/AIOSEO real.

Fontes: [WordPress language_attributes](https://developer.wordpress.org/reference/hooks/language_attributes/), [HTML API](https://developer.wordpress.org/reference/classes/wp_html_tag_processor/), [visibilidade pública](https://developer.wordpress.org/reference/functions/is_post_publicly_viewable/) e [AIOSEO e hreflang](https://aioseo.com/docs/does-all-in-one-seo-output-hreflang-tags/).
