# Etapa 7P.4 - diagnostico final de fidelidade renderizada

Data da analise: 2026-09-25.

Esta etapa nao executa deploy, nao altera WordPress e nao envia formularios. As
evidencias historicas consideradas foram:

- `.production-evidence/deploy-attempt-20260924T221554Z.json`;
- `.production-evidence/post-deploy.json`;
- `.production-evidence/rollback.json`;
- `.production-evidence/current-litespeed-image-contract-7p3.json`.

Os JSONs do quarto deploy nao preservaram o HTML renderizado, os hashes de texto
ou script nem a URL do probe falho. Portanto, eles permitem confirmar os checks
que falharam, mas nao provar a equivalencia integral daquela resposta antiga.

## Algoritmo de texto

**TEXT EXPECTED REPRESENTATION:** texto de todos os nos visiveis do fragmento
HTML aprovado, excluindo descendentes de `script`, `style`, `template` e
`noscript`. Comentarios, declaracoes, doctype e processing instructions tambem
sao excluidos. Entidades HTML sao decodificadas, Unicode e normalizado em NFC,
NBSP vira espaco, aspas tipograficas, travessoes e reticencias sao reduzidos aos
equivalentes definidos e todo whitespace e colapsado.

**TEXT OBSERVED REPRESENTATION:** exatamente a mesma representacao, aplicada ao
unico `.wp-block-post-content` da resposta publica.

**TEXT COMPARISON:** igualdade integral das strings normalizadas. Em falha, o
relatorio registra SHA-256, comprimento, quantidade de tokens, primeira posicao
divergente, tipo da divergencia e no maximo dois pequenos contextos. O contexto
observado so reutiliza tokens existentes no texto estatico aprovado; qualquer
token novo, email ou sequencia numerica longa e substituido por `[REDACTED]`.
Valores de campos, cookies, credenciais e conteudo completo nao sao registrados.

O algoritmo anterior incluia objetos `Comment` retornados pelo BeautifulSoup em
`find_all(string=True)`. Todos os 22 HTMLs aprovados possuem comentarios
editoriais, enquanto a otimizacao publica remove comentarios. Isso gerava
`text = FAIL` sem perda de texto visivel. Com a exclusao correta, uma comparacao
read-only do conteudo armazenado restaurado contra o HTML publico atual passou
em 22/22 paginas.

## Algoritmo de scripts

**SCRIPT EXPECTED REPRESENTATION:** lista ordenada de scripts do fragmento
aprovado. Cada item preserva presenca, indice, `src` logico, tipo canonico,
atributos de execucao relevantes e uma sequencia lexical do JavaScript. Espacos,
comentarios e minificacao cosmetica nao alteram a sequencia; strings, nomes,
operadores, handlers e endpoints permanecem significativos.

**SCRIPT OBSERVED REPRESENTATION:** a mesma lista para o conteudo publico. A
transformacao comprovada do LiteSpeed e normalizada: tipos vazio,
`text/javascript`, `application/javascript` e `litespeed/javascript` representam
script classico; quando o LiteSpeed move `src` para `data-src`, esse e o `src`
logico. `module`, JSON-LD e outros tipos nao sao equiparados a script classico.

**SCRIPT COMPARISON:** igualdade de ordem, presenca, `src` logico, tipo canonico,
`async`, `defer`, `nomodule`, `integrity`, `crossorigin`, `referrerpolicy` e tokens
de codigo. Em falha, o relatorio registra somente tamanho, quantidade de tokens,
SHA-256 normalizado, atributos e as categorias divergentes; nunca o script
completo. Remover uma funcao, handler ou script, ou alterar endpoint, evento ou
logica continua bloqueando.

Uma fixture reproduz `expected scripts = 1` e `observed scripts = 1` com falha:
trocar `button.dataset.clicked = 'yes'` por `'no'` mantem a contagem, mas muda os
tokens e o hash. O mesmo ocorre com texto ao trocar uma frase por outra sem
mudar o numero de elementos HTML. Contagens iguais medem estrutura, nao
equivalencia semantica.

O ambiente publico atual comprova que o LiteSpeed usa
`type="litespeed/javascript"`, `data-src` e minificacao. Essa transformacao agora
passa apenas quando todos os componentes semanticos permanecem iguais. Como o
quarto deploy nao guardou hashes ou HTML dos scripts LPV, nao e possivel provar
retrospectivamente que os tokens daquela resposta eram equivalentes.

## Interacao entre texto e script

`visible_text()` exclui descendentes de `script` e `style`. Assim, a mesma
transformacao de JavaScript nao causou simultaneamente os checks `text` e
`scripts`. O falso positivo de texto vinha dos comentarios HTML; scripts eram
avaliados por outra representacao.

## Algoritmo de image probe

**IMAGE PROBE ALGORITHM:** o contrato separa URL editorial primaria, placeholder
LiteSpeed, candidatos `srcset` e URLs de imagem em CSS. Um recurso CSS so e
classificado como imagem quando esta em `/wp-content/uploads/` ou possui extensao
de imagem conhecida. Endpoints de stylesheet e arquivos de fonte nao sao probes
de imagem. Variantes derivadas devem usar HTTPS, host e familia editorial
aprovados. Cada URL unica recebe GET com `Range: bytes=0-0`, redirects desativados
e timeout de 20 segundos. Sucesso exige HTTP 200/206 e `Content-Type: image/*`.

Qualquer falha futura registra `page_id`, classe `primary`, `srcset`, `CSS`,
`LiteSpeed` ou `other`, URL publica sem query, status, Content-Type, redirect,
erro de timeout/rede/politica, origem no HTML/CSS e presenca no conteudo
armazenado.

A reproducao read-only atual da pagina 255 identificou o mecanismo anterior:
`https://fonts.googleapis.com/css2` era contado como imagem e rejeitado pela
politica de host. Depois da classificacao correta ha 9 probes de imagem, zero
falhas, `primary_preserved=true` e `derived_valid=true`. A tentativa antiga tinha
10 probes e uma falha, mas nao preservou a URL; por exigencia de evidencia, a
causa historica exata permanece `INSUFFICIENT EVIDENCE`.

## Testes negativos e positivos

Os testes bloqueiam:

- palavra removida, frase alterada e CTA alterado/removido;
- script removido, logica alterada, endpoint alterado e handler removido;
- URL primaria alterada ou imagem removida;
- derivada externa/nao relacionada, HTTP 404, HTTP 500 e timeout;
- host inesperado sem realizar chamada de rede.

Os testes aceitam:

- whitespace, ordem de atributos, entidades e tipografia equivalente;
- remocao de comentarios HTML nao visiveis;
- minificacao e tipo classico adiado pelo LiteSpeed com tokens identicos;
- placeholder SVG seguro e `srcset` WordPress da mesma familia;
- ponto e virgula CSS final opcional e aspas equivalentes em `url(...)`.

## Reclassificacao do quarto deploy

- **TEXT FAILURES:** `FALSE POSITIVE` para o defeito sistemico reproduzido de
  comentarios tratados como texto. O JSON historico nao contem o diff por pagina.
- **SCRIPT FAILURES:** `INSUFFICIENT EVIDENCE`. A transformacao LiteSpeed e a
  explicacao provavel, mas os hashes/tokens historicos nao foram preservados.
- **L&P DERIVED IMAGE FAILURE:** `INSUFFICIENT EVIDENCE`. O falso probe de Google
  Fonts foi reproduzido com a mesma forma 10/1, mas a URL antiga nao foi salva.
- **FOURTH DEPLOY:** `INSUFFICIENT EVIDENCE`. Nao pode ser reclassificado como
  `WOULD PASS`; os artefatos antigos nao provam equivalencia dos scripts.
- **SAME SYSTEMIC CAUSE:** `NO`. Texto, scripts e probe CSS usam mecanismos
  diferentes.

O proximo deploy, se autorizado em gate humano separado, produzira diagnosticos
suficientes para distinguir transformacao equivalente de perda real. Esta etapa
nao autoriza nem executa esse deploy.

## Novo gate read-only

- backup privado novo: `20260925T125806Z`, 29 arquivos, manifesto `APROVADO`;
- preflight: `APROVADO`, 22 checks remotos, zero falhas e zero network writes;
- baseline publico: `BLOQUEADOR`, 306 diferencas contra o pacote-alvo e zero
  formularios enviados;
- dry-run: `APROVADO`, zero blockers, zero network writes, sem deploy shield
  residual;
- plano do dry-run: 22 conteudos, 22 registros AIOSEO, CSS final, upgrade
  aprovado de `lpv-page-templates`, reutilizacao/ativacao de `lpv-language-seo`
  e zero mudancas de status EN.

O baseline nao representa uma regressao causada por esta etapa. Ele audita o
WordPress restaurado, anterior ao pacote, contra o estado final pretendido; por
isso ainda lista header/footer nativos, metadados, hreflang e conteudo-alvo como
pendentes. O preflight e o dry-run aceitam o novo fingerprint. Como o requisito
literal da etapa esperava zero blockers tambem no baseline, esse ponto deve ser
mantido visivel no proximo gate humano, sem converter o baseline artificialmente
em aprovado.
