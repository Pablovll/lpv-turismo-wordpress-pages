# Etapa 5 - integração mínima de idioma e hreflang

Revisão local de 22/09/2026. Plugin 1.0.0 implementado e testado; não instalado, ativado ou publicado no WordPress.

## Resultado

`wordpress/plugins/lpv-language-seo/lpv-language-seo.php` registra somente dois hooks nativos: filtro `language_attributes` e ação `wp_head`. O mapa local contém as 22 páginas aprovadas da Etapa 4, sem consulta externa ou dependência dos arquivos de documentação durante a execução.

As responsabilidades do AIOSEO continuam exclusivas: canonical, title, meta description, Open Graph, Twitter Cards e schema. O plugin não interfere nesses hooks, nos atributos existentes do tema, nas configurações, nos textos ou no banco.

## Regras efetivas

- Lang por ID: oito páginas pt-BR, sete es e sete en. Nenhuma escolha vem de parâmetros de URL.
- Sete trios recíprocos, incluindo referência à própria página. O status desejado do JSON não substitui o status real: somente páginas publish, públicas, sem senha e com permalink aprovado entram no grupo.
- Sem PT disponível, não há pt-BR nem x-default; ES/EN disponíveis continuam recíprocos. Não se usa a homepage nem outra página como substituta artificial.
- L&P (255): somente pt-BR e x-default. Serviços ES/EN não são traduções de L&P.
- Sem alternates em admin, feeds, embeds, previews, páginas fora do mapa, paginação ou site globalmente noindex. Idioma da prévia mapeada pode ser corrigido sem anunciar a prévia ao buscador.
- URLs alteradas, página excluída, senha, agendamento, privado e rascunho removem o respectivo equivalente. Cache antigo exige limpeza de todas as traduções do grupo.
- WP_HTML_Tag_Processor preserva outros atributos e escapa lang/xml:lang; esc_attr e esc_url protegem as tags de saída.

## Arquivos desta etapa

| Arquivo | Finalidade |
| --- | --- |
| `wordpress/plugins/lpv-language-seo/lpv-language-seo.php` | Plugin autossuficiente, sem instalação automática |
| `wordpress/plugins/lpv-language-seo/README.md` | Instalação, conflitos, rollback e checklist manual |
| `tests/php/test_lpv_language_seo.php` | Testes offline com core HTML API/escape/hooks reais e fixtures de requisição/publicação |
| `tests/test_stage5_plugin.py` | Paridade dos mapas, responsabilidades exclusivas, lint, acesso direto e pacote |
| `scripts/build_language_plugin_package.py` | Gera o ZIP instalável e os hashes sem conexão WordPress |
| `.gitattributes` | LF nos fontes e bytes preservados nos pacotes para conferir hashes também em checkouts Windows |
| `docs/stage-4-wordpress-checklist.md` | Referência à implementação da Etapa 5; proibição de duplicar tags estáticas |
| `docs/stage-5-language-seo.md` | Este registro de escopo, testes e pendências |
| `publication/stage-5/` | ZIP do plugin, manifesto e diff textual para revisão |

O pacote da Etapa 4 foi regenerado para incorporar o checklist atualizado e normalizar LF nos HTMLs/CSS antes de gerar os hashes. Essa normalização de finais de linha não altera textos, URLs, imagens, estilos ou scripts; permite conferir os mesmos bytes depois de um checkout Windows. Mapas e metadados aprovados permanecem iguais. Alterações anteriores que já estavam no workspace serão preservadas no commit conjunto solicitado com `git add .`; não são atribuídas a este plugin.

## Testes executados

- **PHP lint:** plugin e harness sem erros de sintaxe; acesso direto ao PHP termina sem saída.
- **PHP comportamental:** 1.368 asserções passaram, cobrindo os 22 IDs, todas as combinações de publicação dos grupos, reciprocidade, x-default, exclusões, preservação de atributos e escape nativo.
- **Suite Python:** 20 testes passaram, sem skips: 11 da Etapa 4 e 9 da Etapa 5, incluindo execução do harness PHP.
- **Checkout do índice Git:** os mesmos 20 testes passaram em uma cópia isolada criada com `git checkout-index`; conferência byte a byte válida também com os atributos de finais de linha aplicados. `git diff --cached --check` passou.
- **Paridade:** mapa PHP igual a `docs/stage-4-language-map.json`, `docs/page-map.json` e ao mapa do pacote da Etapa 4. Nenhum fallback virou tradução.
- **Pacote:** ZIP instalável contém apenas a pasta do plugin com PHP e README; arquivos e hashes verificados. Nenhuma credencial, runtime PHP ou core WordPress faz parte do ZIP.

Ambiente efetivamente testado: PHP CLI 8.3.35 e HTML API/hooks/escape do WordPress 6.2, versão mínima declarada. PHP portátil obtido do distribuidor oficial, com SHA-256 conferido antes da execução; core obtido de wordpress.org. Ambos permanecem no diretório temporário do sistema, fora do repositório. Não foi feita uma instalação completa do CMS, nem teste com AIOSEO/tema/cache em produção.

Para repetir, com PHP e core WordPress já disponíveis localmente:

```powershell
$env:PHP_BINARY = 'C:/caminho/php.exe'
$env:WP_CORE_DIR = 'C:/caminho/wordpress'
python scripts/build_language_plugin_package.py
python -m unittest discover -s tests -p "test_*.py" -v
```

Sem PHP/core, os testes Python estáticos continuam disponíveis e os testes de runtime são marcados como skipped, não como executados. Para validar só o PHP:

```powershell
php -l wordpress/plugins/lpv-language-seo/lpv-language-seo.php
php tests/php/test_lpv_language_seo.php --wordpress-core=C:/caminho/wordpress
```

## Revisão e GitHub

Branch de trabalho: `codex/lpv-language-seo`, criada a partir da main local com as alterações anteriores preservadas. Commit solicitado: `Add LPV multilingual lang and hreflang integration`. Sem force push, merge automático, integração contínua de publicação ou acesso ao WordPress. O hash definitivo e o resultado do push são informados no encerramento da tarefa.

O diff textual completo desta etapa fica em `publication/stage-5/integration.diff`. A revisão Git do commit também inclui os arquivos das etapas anteriores solicitados em `git add .`; binários são apresentados como arquivos completos nos pacotes, não como trechos legíveis de texto.

## Aceite pendente no WordPress

1. Fazer backup e conferir versão, IDs, URLs e a inexistência de outro emissor de hreflang, inclusive snippets estáticos da Etapa 4.
2. Instalar/ativar manualmente conforme README. AIOSEO permanece ativo; não reativar Yoast.
3. Conferir HTML bruto, noindex individual/canonical no AIOSEO, reciprocidade, lang e x-default após limpar caches. O plugin não lê noindex individual do AIOSEO.
4. Em staging com domínio diferente ou indexação bloqueada, hreflang fica vazio por segurança. Não expor staging para forçar teste; usar o harness offline ou cópia isolada com URLs oficiais simuladas.
5. Validar o Twenty Twenty-Five no CMS real. Este plugin não remove Header/Footer/Post Title nativos; a correção do template da Etapa 4 continua necessária.
6. Não enviar formulários. A instalação do plugin não valida FormSubmit, analytics, conteúdo comercial, imagens ou entrega de e-mail.

Rollback: desativar o plugin (ou renomear somente sua pasta em caso de falha no painel), limpar cache e, se necessário, restaurar o ZIP anterior. Nenhum dado precisa de migração ou reversão no banco.
