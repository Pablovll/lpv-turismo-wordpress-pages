# Etapa 4 - resultado da preparação local

Data: 22/09/2026. Nada publicado no WordPress; nenhum formulário enviado.

## Entrega

- Decisões de EN, Yoast/AIOSEO e política registradas no mapa e na auditoria da Etapa 3. Aprovações editoriais não são tratadas como pendências.
- 22 fragmentos preparados: oito PT, sete ES e sete EN, com link de privacidade em todos os rodapés.
- Sete trios completos de equivalentes. L&P Experiences permanece PT; os atalhos ES/EN para Serviços não entram em hreflang.
- Canonical próprio, idioma do documento, alternates recíprocos e x-default PT preparados por página.
- 22 pares de title/description extraídos integralmente da tabela da Etapa 3 para AIOSEO.
- Pacote ZIP com HTML, CSS, mapas, metadados JSON/CSV, tags hreflang por ID, template mínimo, checklist e hashes.

## Verificações desta etapa

| Verificação | Resultado | Limite |
| --- | --- | --- |
| 22 páginas públicas + política | 23 respostas HTTP 200, sem troca de host | GET público; não autentica nem confirma status no banco |
| SEO público | AIOSEO presente nas 23; sem marcador Yoast; um canonical por URL; sem hreflang | Marcadores no HTML, não inventário administrativo de plugins |
| Idioma público | As 23 retornam pt-BR | ES/EN ainda precisam da integração WordPress |
| Duplicação no DOM público | Um Header, Post Title e Footer nativos em cada uma das 22 páginas LPV | Não removidos remotamente |
| H1/main público | As 22 LPV têm dois H1; quatro páginas do conjunto público têm dois main | O pacote local tem um H1 e deixa main ao template |
| HTML local | 22 fragmentos com tags balanceadas, IDs únicos, um H1, um header e um footer próprios | Parser estrutural e BeautifulSoup, não certificação W3C |
| Formulários locais | Endpoint FormSubmit preservado | Sem envio, sem teste de entrega |
| Mapa SEO | 22 canonicals únicos, self-reference, reciprocidade e x-default PT corretos | Aplicação real de tags ainda depende do WordPress |
| Testes automatizados | 11 testes passaram | Rodar novamente após qualquer alteração |
| Pacote | Fontes HTML/CSS e ZIP conferidos byte a byte, hashes verificados | Não é importador nem prova de publicação |
| Preservação | Comparação com o início da Etapa 4: apenas um link jurídico acrescentado em cada HTML | Quebras de linha normalizadas para essa comparação; conteúdo, imagens e scripts intactos |
| Responsividade no navegador | 22 páginas x 375/1440 px = 44 combinações sem overflow horizontal; links jurídicos dentro da largura; um main e H1 renderizados | Preview local, não runtime do WordPress |
| Inspeção visual | Rodapés home PT/ES/EN e L&P em desktop/celular; capturas EN e L&P analisadas nos dois tamanhos, PT no celular | Não é nova auditoria visual integral de todas as seções |
| Teclado | Link jurídico alcançável por Tab nas três homes e L&P; foco visível de 2 px | Teste focado no elemento adicionado |

Evidência pública detalhada: `docs/stage-4-public-observation.json`. O coletor usa somente GET, sem credenciais e com validação TLS. A primeira tentativa com o bundle de certificados do Python requests não reconheceu a cadeia local; a coleta foi repetida com urllib e a confiança padrão do sistema, sem desativar a validação TLS.

## Arquivos afetados nesta etapa

- Os 22 arquivos de `pages/pt/`, `pages/es/` e `pages/en/`, listados individualmente em `docs/stage-4-page-inventory.md`: somente inclusão do link jurídico no rodapé.
- `css/lpv-style.css` e `docs/lpv-css-para-wordpress.css`: regras específicas do rodapé para quebra de linha, cor e foco do link.
- `docs/page-map.json`: origem canonical confirmada sem www, fontes, famílias, lang e decisão de publicação EN.
- `docs/stage-3-quality-audit.md`: atualização de decisões, mantendo a distinção entre observações históricas e pendências operacionais.
- Novos documentos: checklist, inventário, mapa de idiomas, metadados AIOSEO, observação pública e este relatório, todos com prefixo `docs/stage-4-`.
- Novos utilitários: `scripts/build_wordpress_package.py`, `scripts/audit_wordpress_public.py`, `scripts/preview_wordpress_package.py` e `tests/test_stage4_package.py`.
- `wordpress/templates/lpv-content-only.html`: referência local para remover a duplicação na origem.
- `publication/stage-4/` e `publication/lpv-wordpress-stage-4.zip`: artefatos gerados para revisão.

`AGENTS.md` não foi alterado nesta etapa. As alterações anteriores, inclusive as que já estavam sem commit, foram preservadas. Não houve commit, push ou uso de credenciais WordPress.

## Ações ainda necessárias no WordPress

1. Aplicar o pacote e a publicação EN já autorizada em uma janela manual de publicação, após staging/backup.
2. Configurar AIOSEO com os metadados e conferir que o cache não contém saída antiga do Yoast.
3. Aplicar idioma real e hreflang por uma única integração server-side. O AIOSEO não gera essas tags.
4. Remover as referências aos blocos nativos no template próprio, mantendo Post Content; verificar a precedência de Front Page na homepage. Instruções exatas no checklist.
5. Conferir política, sitemap, HTML público, telas móveis, zoom real a 200%, compartilhamento social e analytics após aplicação. Não foi feito teste de zoom a 200% nesta etapa.

A fonte jurídica Markdown informada não foi localizada em Documentos/Downloads ou no checkout; não bloqueia o link à política já publicada, mas deve ser incorporada ao versionamento quando estiver disponível. Entrega real de FormSubmit e GA DebugView continuam sem validação nesta etapa e não foram simuladas como testes concluídos.
