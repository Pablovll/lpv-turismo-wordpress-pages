# Etapa 7 - Aplicacao controlada e validacao em staging

Versao 1.0.0. Referencia: 22/09/2026. Responsavel pela aplicacao: operador
WordPress designado pelo proprietario. Responsavel pelo aceite: proprietario
com evidencias tecnicas. Esta entrega prepara ferramentas; nao aplica o pacote.

## Estado desta entrega

| Item | Estado | Evidencia / acao necessaria |
| --- | --- | --- |
| Git inicial | APROVADO | Branch codex/lpv-language-seo limpa, base 12932b6 |
| Pacote Etapa 6 | APROVADO | 36 arquivos no manifesto, 37 entradas no ZIP, 22 HTMLs, dois plugins e hashes conferidos |
| Busca textual de segredos e backups | APROVADO | Sem indicadores apos revisao de falsos positivos; limites descritos abaixo |
| PII em capturas/binarios | NAO TESTADO | Busca textual nao substitui revisao visual |
| URL e acesso ao staging | BLOQUEADOR | Ambiente ainda nao informado/confirmado nesta entrega |
| Backup restauravel e isolamento | PENDENTE | Operador deve apresentar evidencia, sem versionar backup |
| Aplicacao manual do pacote | NAO TESTADO | Nenhuma instalacao/ativacao/aplicacao foi executada |
| Auditoria GET de staging real | NAO TESTADO | Depende do ambiente; fixtures locais nao sao staging |
| Interface e acessibilidade reais | NAO TESTADO | Desktop, 375 px, teclado, menu, rodape e zoom 200% pendentes |
| AIOSEO/LiteSpeed/Site Kit reais | NAO TESTADO | Conferir no ambiente apos aplicacao |
| FormSubmit e GA DebugView | NAO TESTADO | Testes separados, nao autorizados para execucao nesta tarefa |
| Aceite do staging | PENDENTE | Nenhuma autorizacao de producao pode ser inferida |
| Runbook da janela de producao | PENDENTE | Criar SOMENTE apos aprovacao do staging, conforme condicao da Etapa 7 |

APROVADO significa que uma verificacao especifica tem evidencia. PENDENTE
significa atividade ainda necessaria. BLOQUEADOR impede aplicar/avancar.
NAO TESTADO significa ausencia de execucao; nunca equivale a aprovacao.
As ferramentas usam essas mesmas quatro categorias nos relatorios JSON.

## Escopo preservado

22 paginas editorialmente autorizadas: PT 8, ES 7, EN 7. Autorizacao editorial
EN nao comprova publish no banco. Twenty Twenty-Five permanece ativo. AIOSEO
e o unico emissor de canonical/title/description/OG/Twitter/schema; Yoast
permanece removido. LPV Language SEO 1.0.0 cuida apenas de lang/hreflang; LPV
Page Templates 1.0.0 apenas do template das paginas mapeadas. Nenhum plugin,
HTML, CSS, mapa, texto comercial ou URL de imagem foi alterado nesta etapa.
Politica publicada em `/politica-de-privacidade/`, fora dos 22 fragmentos.

## Preflight executavel

Na raiz do projeto, antes de qualquer aplicacao:

```powershell
git status
python scripts/preflight_staging.py --output .staging-evidence/preflight.json
```

O comando nao usa rede. Confere todos os hashes e os bytes do ZIP da Etapa 6,
inventario obrigatorio e 22 fragmentos. Examina arquivos rastreados/novos nao
ignorados, ZIPs internos e blobs do historico local alcancavel por refs Git.
Sinaliza nomes de backups/configuracoes, chaves privadas, alguns formatos de
tokens, atribuicoes de credenciais e e-mails que exigem revisao. Valores e
linhas encontradas nao sao copiados ao relatorio. Codigo de saida 0: verificacoes
automatizadas locais passaram; 2: indicador bloqueador. Erro do comando tambem
interrompe o preflight, nunca implica sucesso.

Contato empresarial publico `info@lpvturismo.com`, placeholders ficticios PT/ES
e dominios de exemplo sao excecoes explicitas. Telefone comercial, CNPJ e
Cadastur do rodape sao dados institucionais publicados, nao segredos. A busca
e heuristica: nao certifica ausencia universal de PII, nao faz OCR de imagens,
nao inspeciona refs remotas nao disponiveis, reflogs ou backups externos.
As capturas de tela antigas exigem revisao visual antes de uma declaracao
abrangente sobre dados pessoais. Nao apagar historico nem fazer force push.
Se houver segredo real, interromper envio/aplicacao, avisar o proprietario
sem reproduzir o valor e solicitar revogacao/rotacao por canal seguro.

`.staging-evidence/`, `.env.*`, backups e dumps ficam ignorados pelo Git.
Isso nao remove arquivos ja rastreados: o scanner verifica esses arquivos.
Guardar evidencias sem formularios preenchidos, cookies, cabecalhos Authorization,
emails pessoais ou dumps. Backup real deve ficar em armazenamento protegido
fora do repositorio, com restauracao ensaiada.

SHA-256 do ZIP de entrada da Etapa 6:
`92ef5deda7c5b87807779e8168433ee738ba5534ecce855c8ada936e29d07ec2`.
Manifesto: `publication/stage-6/manifest.json`. Nao reconstruir/alterar esse
pacote durante uma aplicacao sem nova revisao e conferencia dos hashes.

## Checklist operacional do WordPress

Preencher em evidencia privada: origem HTTPS do staging, operador, data/hora,
versoes WordPress/PHP, ID do backup, resultado do ensaio de restauracao e
referencia do commit/pacote. Manter staging protegido por acesso e noindex.
Impedir FormSubmit no navegador e coleta de GA real; bloquear apenas e-mail
do servidor nao bloqueia FormSubmit. Confirmar que o ambiente e um clone
isolado, nao um alias que sirva a instalacao de producao. O auditor verifica
nomes conhecidos de producao, mas nao pode provar isolamento da hospedagem.

Executar exatamente nesta ordem. Nao avancar quando um passo tiver bloqueador:

1. **Backup completo.** Banco, arquivos, CSS adicional, Leitura, templates e
   personalizacoes do Site Editor, AIOSEO e lista de plugins/versoes. Guardar
   restauracao anterior por componente; ensaiar e registrar o tempo real.
2. **Conferir ambiente/mapa.** Twenty Twenty-Five ativo, WP 6.7+/PHP 7.4+,
   `show_on_front=page`, `page_on_front=7`. Comparar os 22 IDs, slugs, hierarquia
   e caminhos com `publication/stage-6/url-map.json`. Nao recriar paginas.
3. **Procurar conflito `lpv-content-only`.** Inspecionar modelos salvos no
   Site Editor e arquivos do tema/tema filho. Se houver personalizacao ou
   slug concorrente, REGISTRAR E PARAR antes de aplicar. Nao apagar nada,
   nem mesmo a copia conflitante, automaticamente. A instrucao anterior da
   Etapa 6 sobre limpar personalizacao nao autoriza essa acao nesta etapa.
4. **Instalar/ativar LPV Page Templates.** Usar somente
   `plugins/lpv-page-templates-1.0.0.zip`. Nao enviar o ZIP completo da Etapa 6
   como plugin. Nao trocar tema nem editar/salvar o modelo no Site Editor.
5. **Instalar/ativar LPV Language SEO.** Usar
   `plugins/lpv-language-seo-1.0.0.zip`, sem ampliar responsabilidades.
6. **Conferir emissores concorrentes de hreflang.** Revisar plugins, snippets,
   tema e HEAD. Em caso de duplicacao, registrar a origem e parar para corrigir
   deliberadamente. Nao desativar AIOSEO ou remover hooks indiscriminadamente.
7. **Substituir CSS vigente.** Guardar versao anterior e aplicar o CSS final
   no local atual. Nao concatenar copias. Registrar onde ficou armazenado.
8. **Aplicar os 22 HTMLs.** Usar inventario para selecionar o ID correto e
   substituir somente seu conteudo. Preservar slugs, imagens e textos. O
   template fornece main e Post Content; nao envolver o fragmento em outro main.
9. **Conferir sanitizacao.** Reabrir o conteudo salvo e comparar scripts,
   forms, atributos aria, classes, IDs e links com o arquivo aprovado. Guardar
   exportacao de post_content fora do Git para comparacao. Nao aceitar scripts
   removidos ou links reescritos apenas porque a pagina parece correta.
10. **Aplicar os 22 pares title/description no AIOSEO.** Usar a tabela JSON/CSV
    do pacote. O CSV e referencia manual, nao importador nativo garantido.
11. **Conferir SEO completo.** Canonical unico e self, OG, Twitter Cards,
    schema, robots e sitemap. Conferir autoria AIOSEO e ausencia de Yoast,
    tags duplicadas e URLs de formulario com parametros. Documentar se os
    canonicals de staging usam seu dominio ou conservam os finais de producao.
    Nao remover noindex/protecao para testar SEO; nao alterar o mapa aprovado.
12. **Conferir EN.** Os sete IDs devem estar publish no clone e acessiveis no
    frontend protegido. HTTP 200 isolado nao comprova esse estado no banco.
13. **Limpar caches.** LiteSpeed > Toolbox/Ferramentas > Purge > Purge All.
    Se aplicavel, limpar CSS/JS otimizado, Critical CSS, Unique CSS e CDN/proxy;
    aguardar regeneracao antes de avaliar. Registrar horario e evidencias do
    HTML/cache recebido. Nao resetar configuracoes, banco ou OPcache.

Depois desses 13 passos, executar auditoria e verificacoes manuais abaixo.
Nao restaurar dados de staging sobre producao automaticamente.

## Auditoria GET pos-aplicacao

```powershell
$staging = Read-Host 'Origem HTTPS confirmada do staging, sem caminho'
python scripts/audit_staging.py --base-url $staging --output .staging-evidence/staging-get.json
```

Sem URL explicitamente fornecida, o comando nao roda. Recusa o dominio oficial,
www, URLs com credenciais, parametros, fragmentos e subdiretorios. HTTP so e
permitido em loopback para fixtures. Nao segue redirecionamentos, proxies de
ambiente, links, scripts, imagens ou outros subrecursos. Usa GET nas 22 paginas
e na politica; nao abre navegador, envia formulario ou dispara JavaScript/GA.
Nao executar `scripts/audit_wordpress_public.py` nesta fase: esse comando antigo
aponta diretamente para producao e nao possui a restricao de staging.

Se o acesso usar HTTP Basic, fornecer usuario e senha apenas em variaveis de
ambiente temporarias `LPV_STAGING_HTTP_USER` e `LPV_STAGING_HTTP_PASSWORD`, por
gerenciador seguro/prompt protegido. Nao sao credenciais WordPress. HTTPS e
obrigatorio com autenticacao. Remover as variaveis apos uso. Nao colocar
segredos em argumentos, Git ou URL. Protecao por SSO/cookie nao e automatizada;
401/403/redirecionamento de login bloqueia a auditoria, nao aprova a pagina.

O modo padrao `--canonical-mode staging` exige o canonical do proprio staging
e caminho aprovado. Se deliberadamente preservados os canonicals finais,
usar `--canonical-mode approved` e registrar a decisao com noindex/acesso
protegido. Esse modo nao e permissao para indexar o clone.

O padrao `--hreflang-mode suppressed` espera ausencia de alternates: comportamento
de seguranca do plugin em outro dominio ou `blog_public=0`. Marca reciprocidade
publicada como NAO TESTADO, nao como falha. Se aparecerem tags nesse modo,
investigar cache ou emissor concorrente. `--hreflang-mode published` exige os
conjuntos exatos aprovados em todos os membros: sete trios reciprocos, self,
x-default PT e L&P somente PT/x-default. Usar apenas em simulacao isolada que
realmente possa emitir esses conjuntos, nunca liberando indexacao do staging
ou acessando producao para forcar esse teste.

O relatorio verifica HTTP/URL, documento, main/H1/header/footer, blocos nativos
ausentes, lang, canonical/title/description unicos e corretos, link juridico,
features do fragmento e scripts/texto aprovados. Tags SEO em HTTP Link exigem
revisao e bloqueiam o aceite automatico dessas verificacoes. Nao persiste HTML recebido,
valores de campos ou headers de autenticacao. Comparacao de features detecta
sanitizacao, mas nao substitui comparar o conteudo salvo nem a cascata CSS.
Minificacao/reorganizacao deve ser investigada; nunca aprovada automaticamente.

CSS inline e reconhecido apenas quando um bloco style corresponde integralmente
ao CSS aprovado, normalizando finais de linha e espacos externos. Para CSS em
arquivo conhecido do mesmo staging, adicionar `--css-path /wp-content/.../arquivo.css`.
Nao usar esse texto com reticencias literalmente; informar o caminho confirmado.
CSS servido por CDN externa/minificado ou dividido exige comparacao manual.
Falta de evidencia CSS fica NAO TESTADO, nao APROVADO. O auditor nao confirma
cascata, imagens carregadas, escala, overflow, cache renovado ou configuracao
AIOSEO de OG/Twitter/schema/robots/sitemap: esses itens continuam manuais.

Saida 2 indica bloqueador GET. Saida 0 significa apenas verificacoes GET sem
falha bloqueadora; o relatorio continua PENDENTE e `staging_approved=false`.
Um relatorio automatico nunca aprova sozinho o staging.

## Checklist manual obrigatorio

Preencher para todas as paginas; registrar navegador, viewport, data e
evidencia sem PII. Nao limitar a avaliacao a uma homepage.

- [ ] Desktop: largura, imagens/escala, cards, header/footer e ausencia de overflow.
- [ ] 375 px: menu fechado/aberto, quebra de texto, botoes e rodape centralizado.
- [ ] Teclado: ordem Tab/Shift+Tab, foco visivel, Enter/Space e ausencia de armadilha.
- [ ] Escape fecha menu aberto e devolve foco; links nao ficam ocultos/inacessiveis.
- [ ] Skip link visivel ao foco e destino no unico main, sem salto para elemento oculto.
- [ ] Formulario visual PT/ES/EN: labels, campos preservados, idioma inicial,
  contexto passeio/servico/MIPIM editavel e acesso direto; nao clicar Enviar.
- [ ] Rodape e politica: links, logos, legibilidade, documento juridico realmente
  esperado, nao tela de login com HTTP 200. Templates fora das 22 preservados.
- [ ] Imagens img, srcset e backgrounds carregadas e sem corte/escala indevidos.
  Conferir naturalWidth quando aplicavel e inspecionar backgrounds separadamente.
- [ ] Overflow: comparar scrollWidth/clientWidth e inspecionar visualmente;
  essa medicao isolada nao comprova usabilidade.
- [ ] Zoom REAL do navegador a 200%: menu, foco, leitura e ausencia de sobreposicao.
  Nao substituir por deviceScaleFactor, screenshot redimensionado ou teste GET.
- [ ] CSS e HTML servidos correspondem aos aprovados; cache/CDN renovados.
- [ ] AIOSEO: OG/Twitter/schema sem duplicacao de emissores, robots/sitemap
  coerentes com staging protegido. Sete EN publish confirmados no painel.

## Testes posteriores separados

### FormSubmit - nao executar nesta tarefa

Somente apos autorizacao explicita para envio e destinatario. Usar dados
sinteticos identificados como teste, sem dados reais de clientes. Conferir
formulario/contexto/idioma, acionar uma vez e observar a requisicao. Responsavel
pela caixa `info@lpvturismo.com` confirma recebimento, campos e contexto; registrar
apenas resultado, sem copiar mensagem/dados pessoais ao repositorio. Conferir
redirect de sucesso para o ambiente autorizado: verificar `_next` e fluxo antes
do teste para nao navegar involuntariamente a producao. Em teste de duplo clique,
validar bloqueio de segunda requisicao antes de liberar rede; testar entrega
duplicada real so com autorizacao especifica. Mensagem de sucesso no navegador
nao comprova recebimento. Conferir tambem falha/timeout e reabilitacao do botao.

### GA DebugView - nao validado

Usar propriedade/stream de teste e isolamento que impeca coleta de producao.
Somente apos autorizacao, conferir cada evento no DebugView com timestamp e
uma unica ocorrencia por acao. Nao ativar analytics de producao para facilitar QA.

| Evento | Acao controlada posterior | Payload a conferir |
| --- | --- | --- |
| lpv_tour_open | Clicar em link interno de um passeio no ambiente isolado | tour_id conhecido, page_path sem query, page_language |
| lpv_whatsapp_click | Acionar link com navegacao externa bloqueada, sem enviar mensagem | page_path sem query, page_language |
| lpv_proposal_request_submit | Evento de submit em teste autorizado; requisicao FormSubmit bloqueada salvo autorizacao separada | request_context validado, page_language |

Conferir ausencia de nome, email, telefone, texto livre, valores de formulario,
cookies/IDs pessoais em parametros customizados. Conferir tambem page_location,
page_referrer e parametros automaticos, pois ausencia de PII nos parametros
customizados nao garante ausencia no restante da requisicao. Verificar duplicacao
por Site Kit/GTM/gtag e documentar consentimento/configuracao sem inventar resultado.

## Aceite e condicao para producao

Staging so pode mudar para APROVADO apos evidencias de DOM correto, CSS/HTML
aprovados, idiomas corretos, AIOSEO sem duplicacao, EN acessivel/publish, politica
acessivel, cache renovado e todas as verificacoes manuais principais aprovadas.
Ausencia justificada de hreflang no clone protegido nao bloqueia por si so;
exige registrar a restricao e planejar conferencia imediata na futura janela.
FormSubmit/DebugView continuam separados e nao devem ser marcados aprovados
por inferencia; o proprietario deve decidir explicitamente sobre qualquer
risco residual antes de autorizar producao.

Como staging nao foi aprovado, NAO foi criado um runbook executavel de producao.
Apos o aceite, esse documento devera conter ordem por componente, backup
verificado, tempo operacional de rollback MEDIDO no ensaio (nao estimado),
responsavel pela janela, verificacoes imediatas e condicoes objetivas de abortar:
HTTP/URL incorretos, duplicacao de landmarks/SEO, sanitizacao, CSS divergente,
idiomas errados, EN indisponivel, falha de politica ou cache antigo persistente.
O rollback deve distinguir template, idioma, CSS, HTML, AIOSEO e status; nao
exige reativar Yoast e nao deve sobrescrever dados recentes de producao. Nenhum
deploy ou merge automatico fica autorizado por este documento.

## Verificacoes locais e Git

Arquivos novos: `scripts/preflight_staging.py`, `scripts/audit_staging.py`,
`tests/test_stage7_staging.py` e este documento. `.gitignore` protege evidencias
e backups. Pacotes Etapas 4/5/6, plugins e fontes permanecem sem alteracoes.

```powershell
$env:PHP_BINARY = 'C:/caminho/php.exe'
$env:WP_CORE_DIR = 'C:/caminho/wordpress-6.2'
$env:WP_TEMPLATE_CORE_DIR = 'C:/caminho/wordpress-6.7'
python -m unittest discover -s tests -p 'test_*.py' -v
git status
git diff
git diff --check
```

Resultados desta execucao:

- 44 testes passaram sem skips: 11 Etapa 4, 9 Etapa 5, 9 Etapa 6 e 15 Etapa 7.
- PHP lint dos dois plugins e harnesses passou. Os harnesses existentes
  executaram 1.368 assercoes de idiomas e 185 de templates.
- Etapa 7: integridade e adulteracao de pacote, varredura redigida, ZIP interno,
  bloqueio de producao/credenciais na URL/traversal/redirect, 22 documentos,
  idioma/SEO/landmarks, sanitizacao, CSS sem evidencia e ausencia de dados
  privados em relatorios. Nenhum resultado GET promove staging a APROVADO.
- Preflight offline passou: 187 arquivos de trabalho e 135 blobs no historico
  alcancavel na rodada anterior ao commit; nenhum indicador remanescente apos
  revisar placeholders ficticios e um decorator Python em diff como falsos positivos.
  Capturas/binarios nao foram certificados por essa varredura textual.
- SHA-256 e bytes de todo o pacote da Etapa 6 conferidos. O teste de reproducao
  reexecutou seu build, sem modificar o ZIP aprovado ou qualquer outro artefato.
- Fontes, plugins, CSS, mapas e pacotes comparados com HEAD: nenhuma alteracao.
- `git diff --check` passou. Evidencias operacionais ficam fora do commit.

Ambiente: PHP 8.3.35, core offline WP 6.2 para idiomas e 6.7 para templates.
Os testes da Etapa 7 usam fixtures sinteticas e um servidor loopback que verifica
bloqueio de redirect; nao representam CMS, AIOSEO ou staging real. Nenhum
formulario/evento GA real, nem requisicao ao site de producao, foi executado.
Commit solicitado, condicionado aos testes: `Prepare LPV staging validation and production runbook`.
O nome solicitado do commit nao altera a condicao que impede preparar/liberar
a janela de producao antes do aceite. Enviar na branch atual, sem force push,
sem merge main. Informar hash e resultado do push ao finalizar.
