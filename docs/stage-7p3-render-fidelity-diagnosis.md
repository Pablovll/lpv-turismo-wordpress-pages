# Etapa 7P.3 - Diagnostico de fidelidade renderizada

Data: 24/09/2026. O terceiro deploy permaneceu revertido. Esta etapa nao
executou `--execute`, nao alterou o WordPress e nao enviou formularios.

## Evidencia preservada

Foram analisados `post-deploy.json`, o baseline, a timeline/journal da tentativa
`20260924T174738Z` e os relatorios posteriores ao rollback. O relatorio
pos-deploy reteve checks, IDs, URLs e contagens, mas nao reteve o HTML bruto,
os conjuntos de URLs observados nem os manifests que divergiram. Essa limitacao
e explicitada abaixo; nenhum valor ausente foi reconstruido como fato.

O helper de conteudo somente devolve `APROVADO` depois de validar o SHA-256 do
arquivo alvo, chamar `wp_update_post()`, limpar o cache do post, reler
`post_content` e validar novamente o mesmo SHA-256. A timeline preservada
registrou os 22 IDs como concluidos. Assim, A -> B foi exato na tentativa.

## As 32 falhas

| page_id | URL | check | expected | observed | difference_type |
| ---: | --- | --- | --- | --- | --- |
| 7 | `/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 17 | `/passeios/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 18 | `/outros-servicos/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 255 | `/lp-experiences/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop`, atributos de imagem e core |
| 19 | `/quero-montar-meu-roteiro/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 84 | `/passeios/mosaicos-do-rio/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 85 | `/passeios/imersao-floresta-da-tijuca/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 86 | `/passeios/rio-essencial/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 20 | `/es/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 237 | `/es/paseos/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 205 | `/es/servicios/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 203 | `/es/quiero-armar-mi-itinerario/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 160 | `/es/mosaicos-del-rio/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 194 | `/es/inmersion-floresta-da-tijuca/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 195 | `/es/rio-esencial/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 21 | `/en/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` mais tipografia equivalente |
| 239 | `/en/tours/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` mais tipografia equivalente |
| 217 | `/en/services/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` mais tipografia equivalente |
| 218 | `/en/plan-my-itinerary/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` e transformacoes core reproduzidas |
| 219 | `/en/mosaics-of-rio/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` mais tipografia equivalente |
| 220 | `/en/tijuca-forest-immersion/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` mais tipografia equivalente |
| 221 | `/en/rio-essential/` | `approved_content_preserved` | features/scripts/text iguais | tuple desigual; detalhe nao retido | `wpautop` mais tipografia equivalente |
| 255 | `/lp-experiences/` | `image_urls_preserved` | 8 URLs unicas | 9 tokens; valores nao retidos | lazy-load + parser de data URI |
| 84 | `/passeios/mosaicos-do-rio/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 85 | `/passeios/imersao-floresta-da-tijuca/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 86 | `/passeios/rio-essencial/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 160 | `/es/mosaicos-del-rio/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 194 | `/es/inmersion-floresta-da-tijuca/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 195 | `/es/rio-esencial/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 219 | `/en/mosaics-of-rio/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 220 | `/en/tijuca-forest-immersion/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |
| 221 | `/en/rio-essential/` | `image_urls_preserved` | 9 URLs unicas | 9 tokens; conjuntos diferentes | lazy-load + parser de data URI |

## Causa raiz de conteudo

O check antigo comparava um `Counter` de todas as tags e de todos os atributos,
o SHA-256 textual de cada script e o texto agregado. Qualquer atributo seguro,
tag inserida ou troca tipografica reprovava a pagina inteira.

A simulacao read-only no WordPress real reproduziu 22/22 falhas. `wpautop`
inseriu `<p>` e `<br>` e, de forma material, colocou `</p><p>` dentro dos blocos
`script` e `style`. Isso altera JavaScript e CSS, portanto nao era apenas falso
positivo. `wp_filter_content_tags` tambem acrescentou `decoding="async"` em tres
imagens da L&P, e `wptexturize` converteu apostrofos ingleses sem mudar o texto.

No mesmo processo em memoria, remover somente `wpautop` produziu 22/22 manifests
semanticos aprovados, scripts/estilos intactos e 22/22 inventarios primarios de
imagem aprovados. Nenhuma API de persistencia foi chamada.

## Causa raiz de imagens

As dez paginas sao exatamente as que possuem imagens editoriais sem
`skip-lazy`. GETs read-only mostram o LiteSpeed substituindo `img[src]` por um
SVG `data:` de dimensoes equivalentes, preservando a URL editorial em
`data-src` e adicionando `width`, `height` e `decoding`.

O extrator antigo ignorava `data-src` e dividia qualquer `src` por virgula. A
virgula obrigatoria de `data:image/svg+xml;base64,...` virava dois falsos tokens.
Isso explica as contagens e o padrao exato das dez paginas. Como o HTML bruto da
terceira tentativa nao foi preservado, os valores literais daquele response nao
podem ser certificados retroativamente; a origem foi reproduzida no mesmo
frontend/configuracao, mas essa parte permanece uma inferencia documentada.
Como controle adicional, o novo contrato comparou os 22 `post_content` atuais
do baseline restaurado com 22 GETs publicos: 22/22 URLs primarias e 22/22 URLs
derivadas passaram mesmo com o lazy-load ativo.

## Contrato de fidelidade

Layer A e o HTML aprovado em `pages/pt`, `pages/es` e `pages/en`. Layer B e
`post_content` lido por WP-CLI. A -> B exige igualdade byte a byte da string
UTF-8 e igualdade ordenada das URLs editoriais, incluindo `img[src]` e URLs em
CSS inline. Qualquer divergencia e bloqueador.

Layer C e o HTML HTTP final. B/A -> C usa manifests de texto significativo,
H1/H2/H3, links/hrefs, botoes/CTAs, IDs, classes LPV essenciais, atributos
ARIA/data aprovados, secoes, formularios/actions/campos/hidden/select/options,
scripts tokenizados, estilos tokenizados, imagens primarias e alt. Ordem de
atributos, whitespace, aspas, wrappers `div`, tipografia equivalente e atributos
seguros adicionais nao reprovam.

As cinco verificacoes novas sao:

- `stored_content_preserved`
- `rendered_content_preserved`
- `stored_image_urls_preserved`
- `rendered_primary_image_urls_preserved`
- `derived_image_urls_valid`

Para lazy-load, `data-src` e a URL primaria quando `src` e um placeholder
`data:`. O SVG e decodificado e rejeitado se contiver script, JavaScript ou
event handler. `srcset`/`data-srcset` e validado separadamente: HTTPS, mesmo host,
diretorio de uploads, mesma familia editorial e HTTP 200/206. Host, caminho ou
familia arbitrarios nao sao normalizados.

## Correcao de rendering

LPV Page Templates 1.0.1 remove `wpautop` no hook `wp` somente quando tema,
tipo, ID, permalink e configuracao de homepage correspondem ao mapa aprovado.
Paginas fora do mapa mantem o filtro. O pacote permite upgrade somente quando a
instalacao remota e byte-identica ao ZIP 1.0.0 anterior; arquivos desconhecidos
continuam bloqueando. AIOSEO nao foi alterado.

## Testes

Fixtures positivas cobrem HTML identico, whitespace, atributos reordenados,
entidades, aspas, `loading`, `decoding`, dimensoes e `srcset` derivado. Fixtures
negativas removem texto, CTA, imagem, script, classe e ID; alteram href, action,
field name e URL editorial; duplicam ID; e introduzem URL externa derivada.
Todas as perdas reais reprovam.

Suite Python: 71 passed, 5 skipped, 0 failed. Os cinco skips sao harnesses PHP
locais sem `PHP_BINARY`; nao foram contados como executados. Lint PHP read-only
no host: 3/3 arquivos aprovados. Harness em memoria no core real: mapa 22,
guard no priority 20, `wpautop` removido na pagina 17 e preservado na pagina de
politica. A simulacao de filtros obteve 0/22 antes e 22/22 depois da correcao.
O teste read-only do lazy-load obteve 22/22 inventarios primarios e derivados.

A correcao de rollback AIOSEO do commit `25c8198` permanece: confirmacao fresca
por WP-CLI apos o batch, journal vazio como `NOT REQUIRED` e excecao primaria
separada de excecoes de rollback. Os testes correspondentes continuam passando.

## Reclassificacao do terceiro deploy

`WOULD FAIL`. A camada armazenada e as URLs editoriais armazenadas foram
preservadas, mas o rendering antigo corrompia scripts e estilos por `wpautop`.
Logo, mesmo descontando o falso positivo de atributos/tipografia e tratando
lazy-load corretamente, havia perda semantica real. A exatidao das URLs de
imagem no response antigo e `INSUFFICIENT EVIDENCE`, pois os valores nao foram
retidos; isso nao muda a reprovacao causada pelos scripts/estilos.

## Novos gates read-only

- Preflight: `APROVADO`; pacote, remoto e scan sensivel aprovados; zero writes.
- Baseline GET: 22/22 paginas e politica HTTP 200; 307 achados preexistentes;
  zero formularios enviados.
- Backup: `20260924T220809Z`, privado/ignorado, 29 arquivos, manifesto validado.
- Dry-run: `APROVADO`, zero blockers; 22 conteudos, CSS e 22 AIOSEO previstos;
  zero status EN; template plugin como upgrade aprovado 1.0.0 -> 1.0.1;
  Language SEO como ativacao/reuso.
- Criterios do dry-run: os cinco checks novos aparecem explicitamente.
- Quarto deploy: NAO EXECUTADO.

## Riscos residuais

O HTML bruto do terceiro response nao existe, portanto sua lista literal de
URLs renderizadas nao pode ser reconstituida. O quarto deploy deve preservar o
novo relatorio por manifest e falhas compactas. Validacao visual/JavaScript real
continua sendo um checkpoint posterior ao deploy; nenhum formulario deve ser
enviado durante essa verificacao.
