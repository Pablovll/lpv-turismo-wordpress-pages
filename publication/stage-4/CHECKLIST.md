# Etapa 4 - integração e pré-publicação WordPress

Decisões do proprietário: 22/09/2026. Pacote local para revisão; não é publicação automática.

Atualização da Etapa 5: a integração mínima de idiomas está versionada em `wordpress/plugins/lpv-language-seo/`. Consulte `docs/stage-5-language-seo.md` e o README do plugin para testes, instalação manual e rollback. Ela não foi instalada no WordPress.

Atualização da Etapa 6: usar `docs/stage-6-wordpress-integration.md` como procedimento atual de staging. O plugin separado LPV Page Templates aplica o modelo versionado às 22 páginas e trata Front Page explicitamente. O procedimento manual de criação/atribuição de templates abaixo permanece como referência histórica, não deve ser executado junto com o plugin. Nenhuma aplicação no WordPress foi realizada.

## Escopo e decisões resolvidas

- Sete páginas EN revisadas e autorizadas para publicação. `status: publish` no mapa representa o estado desejado, não uma alteração remota executada.
- Yoast removido; somente AIOSEO administra title, description, canonical, Open Graph e schema.
- Política aprovada e publicada: https://lpvturismo.com/politica-de-privacidade/.
- Fonte jurídica informada: `LPV_Turismo_Politica_de_Privacidade_Site_2026.md`. Não encontrada neste checkout, em Documentos ou Downloads. Não recriar nem substituir a política publicada.
- Nenhum texto comercial, endereço de imagem ou integração de formulário foi alterado nesta etapa. Os HTMLs receberam apenas o link jurídico no rodapé.
- O CSS acrescenta somente quebra de linha, alinhamento e apresentação acessível desse link. A organização do rodapé permanece.

## Inventário e equivalências

`docs/page-map.json` é a fonte dos IDs, caminhos, arquivos, famílias, idiomas e estados desejados. O inventário gerado contém as 22 páginas: oito PT, sete ES e sete EN.

Existem sete famílias completas: homepage, passeios, serviços, formulário, Mosaicos, Tijuca e Rio Essencial. Cada uma tem três equivalentes reais e recebe o mesmo conjunto recíproco de quatro alternates: `pt-BR`, `es`, `en` e `x-default` (PT).

L&P Experiences (ID 255) tem somente PT. Seu canonical, `pt-BR` e `x-default` apontam para `/lp-experiences/`; `es` e `en` são omitidos. Os destinos `/es/servicios/#lp-experiences` e `/en/services/#lp-experiences` são alternativas de navegação, nunca traduções da página L&P nem alternates SEO.

A política é um documento adicional, fora dos 22 fragmentos. Não há traduções jurídicas fornecidas. Todos os rodapés apontam para o mesmo documento PT; ES e EN identificam seu idioma no texto do link e com `hreflang="pt-BR"`.

## Conteúdo do pacote

Gerar novamente após qualquer revisão:

```powershell
python scripts/build_wordpress_package.py
python -m unittest discover -s tests -p "test_stage4*.py"
```

Saída: `publication/stage-4/` e `publication/lpv-wordpress-stage-4.zip`.

- `html/pt`, `html/es`, `html/en`: os 22 fragmentos, idênticos byte a byte às fontes. Aplicar apenas no conteúdo da página correspondente, preservando scripts e estilos inline existentes.
- `css/lpv-style.css`: CSS completo; idêntico a `css/lpv-style.css` e `docs/lpv-css-para-wordpress.css`.
- `url-map.json`: IDs WordPress, arquivos e URLs. Não criar novos slugs, redirecionamentos ou páginas duplicadas.
- `language-map.json`: idioma do documento, canonical, alternates, equivalentes ausentes e distinção entre fallback de navegação e tradução.
- `aioseo-metadata.json` e `aioseo-metadata.csv`: title, description e canonical finais, extraídos sem alteração da tabela da Etapa 3. CSV é uma planilha de aplicação/conferência manual, NÃO um importador nativo garantido do AIOSEO.
- `hreflang/{id}.html`: referências das tags com todos os equivalentes publicados. Não inserir no conteúdo e não colar junto com o plugin da Etapa 5, que calcula os equivalentes públicos dinamicamente.
- `wordpress/lpv-content-only.html`: modelo de template de blocos, não conteúdo da página nem arquivo para substituir o tema inteiro.
- `CHECKLIST.md`, `REVIEW-REPORT.md`, `PAGE-INVENTORY.md`, `PUBLIC-OBSERVATION.json`, `VALIDATION.json` e `manifest.json`: instruções, evidências e hashes SHA-256 para conferência.

## Aplicação manual no WordPress

### 1. Backup e staging

- [ ] Exportar conteúdo, banco, templates personalizados, configurações AIOSEO e CSS adicional. Preservar um backup anterior por item alterado.
- [ ] Aplicar primeiro em staging. Não rodar `export_public_pages.py` sobre fontes revisadas como substituição do pacote.
- [ ] Conferir os 22 IDs e URLs no painel. As sete EN têm publicação autorizada; não pedir nova decisão editorial. Não alterar a página jurídica.

### 2. Template: retirar a causa da duplicidade

O código do template salvo no banco não está versionado neste repositório. O DOM público permite identificar os elementos, mas não confirmar o nome do template escolhido no painel. Conferir a atribuição antes de editar.

1. Em **Aparência > Editor > Design > Modelos/Templates**, criar um template próprio chamado **LPV - Conteúdo completo**, usando o modelo do pacote. Atribuí-lo SOMENTE às 22 páginas do inventário. Não editar globalmente os templates de posts, política, busca, arquivo ou erro 404.
2. Na visualização em lista, remover as referências a **Header/Cabeçalho** e **Footer/Rodapé** (`core/template-part`, normalmente `slug: header` e `slug: footer`). Remover a referência no template, não apagar a parte compartilhada da biblioteca.
3. Remover **Post Title/Título do post** (`core/post-title`), responsável por `.wp-block-post-title`. Não apagar o H1 existente dentro do HTML LPV.
4. Retirar blocos **Spacer/Espaçador** e grupos vazios que serviam apenas aos três blocos removidos. No grupo principal, definir margem, padding e espaçamento entre blocos como zero, largura completa e sem largura restrita herdada.
5. Manter exatamente um **Post Content/Conteúdo do post** (`core/post-content`), que renderiza o HTML salvo. Não copiar o HTML comercial para dentro do template.
6. Manter um único `main` no template. Os fragmentos LPV já não contêm outro `main`. Preservar `header.topbar` e `footer.lpv-site-footer` internos ao conteúdo. Verificar o destino do skip link gerado pelo WordPress.
7. Na homepage PT, verificar **Front Page/Página inicial**: quando existe, esse template tem precedência. Aplicar nele a mesma estrutura somente de conteúdo. Conferir também templates específicos por página; uma atribuição genérica pode não prevalecer.
8. Publicar o template apenas na janela de publicação aprovada, limpar LiteSpeed e inspecionar o código-fonte sem depender do CSS. Resultado esperado em cada página: zero `.wp-block-post-title`, zero `header.wp-block-template-part`, zero `footer.wp-block-template-part`, um H1 e um main.

O CSS defensivo existente foi preservado para não quebrar o site antes dessa aplicação. Ele não substitui a remoção dos blocos. Há regras antigas amplas em `body.wp-singular`; verificar separadamente a página jurídica, que não faz parte do pacote, antes de remover ou restringir essas regras em outra revisão.

### 3. AIOSEO e idiomas

- [ ] Confirmar AIOSEO ativo e Yoast ausente; limpar cache antigo. Não instalar outro plugin SEO.
- [ ] Para cada ID, aplicar title e description literais da tabela final no painel AIOSEO. Evitar smart tags que acrescentem novamente o nome do site. Configurar canonical absoluto, sem parâmetros como `?experience=` ou `?success=`.
- [ ] Conferir um único title, description e canonical no HEAD. Não inserir essas tags no conteúdo HTML. O canonical de cada tradução aponta para ela mesma, não para PT.
- [ ] Preservar as imagens Open Graph e o schema aprovado do AIOSEO. Este pacote não inventa avaliações, preços, datas de eventos, dados estruturados de produtos nem troca imagens sociais. Conferir a prévia de compartilhamento com as mídias existentes.
- [ ] Verificar qual integração multilíngue está instalada. AIOSEO **não emite hreflang**. Essa função e o `lang` ficam na camada de idiomas do WordPress, sem transferir a ela title, description, canonical ou schema.
- [ ] Se essa integração já suporta as páginas existentes, vincular os sete trios pelos IDs do mapa e configurar `pt-BR`, `es`, `en` e `x-default` PT. Não recriar traduções com novos slugs.
- [ ] Se não existe integração concorrente, aplicar manualmente o plugin **LPV Language SEO** da Etapa 5. Ele usa `language_attributes` e `wp_head`, confere status/permalink real e não emite metadados do AIOSEO. Não exige colar tags estáticas nem alterar `document.documentElement.lang` por JavaScript. Instalação e ativação permanecem manuais.
- [ ] Usar UMA única origem de hreflang (plugin de idiomas OU integração de HEAD), nunca ambas. Emitir somente equivalentes publicados, indexáveis e com canonical coerente; se algum não estiver publicado, retirar esse idioma de TODO o trio até liberá-lo.
- [ ] Conferir reciprocidade e self-reference no HTML recebido pelo navegador sem executar JavaScript. L&P não pode listar ES/EN como equivalentes.
- [ ] Não mudar o idioma global do WordPress para tentar corrigir apenas ES/EN. Homepages e páginas internas precisam receber seu próprio `html lang`.

### 4. Conteúdo, CSS e publicação

- [ ] Aplicar os fragmentos pelo mapa, manter os mesmos IDs/URLs e não alterar imagens nem textos comerciais.
- [ ] Aplicar o CSS final no local atual de CSS adicional, mantendo backup para reversão. Evitar duplicar sucessivas cópias completas.
- [ ] Conferir os 22 links de política. Não sobrescrever o conteúdo jurídico com o template ou HTML LPV.
- [ ] Conferir que as sete EN estão publicadas, indexáveis e na navegação/sitemap de acordo com a autorização.
- [ ] Limpar caches e rever sitemap AIOSEO, canonical, idiomas, robots e previews sociais. A política pode aumentar o total de páginas do sitemap; não exigir exatamente 22 URLs no sitemap inteiro.

### 5. Aceite final sem envio real

- [ ] Desktop e celular, inclusive 375 px, sem overflow; cabeçalho, menu e rodapé centralizado preservados.
- [ ] Navegação por teclado, foco visível no link de privacidade, Escape no menu e zoom real de navegador a 200%.
- [ ] Mudança de idioma mantém equivalência e contexto permitido de formulário.
- [ ] Formulários mantêm endpoint FormSubmit e campos; não clicar Enviar nesta etapa.
- [ ] WhatsApp abre mensagem revisável no idioma/contexto correto; não enviar mensagem.
- [ ] Uma única origem de SEO; DOM sem duplicação nativa; lang correto; hreflang recíproco; política responde e é legível.
- [ ] GA DebugView e entrega real do FormSubmit ficam para verificação separada autorizada. Não confundir validação local com confirmação de entrega.

## Fontes técnicas

- [AIOSEO: responsabilidade por hreflang](https://aioseo.com/docs/does-all-in-one-seo-output-hreflang-tags/).
- [WordPress: edição, atribuição e precedência de templates](https://wordpress.org/documentation/article/template-editor/).
- [WordPress: language_attributes](https://developer.wordpress.org/reference/hooks/language_attributes/) e [wp_head](https://developer.wordpress.org/reference/hooks/wp_head/).

## Limites da entrega

Nenhuma alteração no WordPress, publicação, envio de formulário, mensagem de WhatsApp ou alteração de credenciais é executada pelo gerador. A configuração de templates/AIOSEO/idiomas e a conferência após limpar cache dependem do painel e do ambiente WordPress. As pendências editoriais não relacionadas registradas na Etapa 3 continuam separadas desta entrega.
