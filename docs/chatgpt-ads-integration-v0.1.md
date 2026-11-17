# Integração de conversões do ChatGPT Ads — LPV Turismo

- Versão: 0.2
- Data: 17/11/2026
- Responsável: Pablo Vallasciani / LPV Turismo
- Status: código em revisão; implantação e validação externa pendentes.

## Resultado preparado

Plugin independente em wordpress/lpv-chatgpt-conversions para medir lead_created após aceitação confirmada pelo FormSubmit, com escolha opcional do visitante. Nenhuma mudança em páginas, preços, imagens, reservas ou campanhas de produção.

## Constatações de produção

- WordPress conectado via WPWriter.
- Plugins ativos incluem LPV Page Templates 1.1.0, LPV Language SEO 1.1.0, Site Kit, WPForms Lite e LiteSpeed Cache.
- Os formulários principais das páginas 19, 203 e 218 usam FormSubmit; a instalação do WPForms não significa que esse plugin processe esses três formulários.
- A página 19 possui tratamento visual de retorno por enviado=1 e evento Google disparado na tentativa de envio. Esses sinais, sozinhos, não comprovam recepção de um pedido.
- A política publicada foi atualizada em 22/09/2026 e não descreve esta integração com a OpenAI.
- O conteúdo publicado tem ajustes de novembro que não constam na main do repositório. O novo plugin não deve substituir esse HTML.

## Pendências e responsáveis

| Ação | Responsável | Status / dependência |
| --- | --- | --- |
| Código e testes isolados | Assistente | v0.1: CI aprovado (49 verificações PHP e 4 testes JavaScript). v0.2 adiciona painel e pacote; verificar novo CI |
| Acesso à conta publicitária | Pablo | Leitura da conta realizada pelo conector; acesso ao navegador não concluído |
| Pixel ID, chave CAPI e fonte correta | Pablo / conta de anúncios | Pixel ID localizado na fonte web campanha 1: RhD2bsVtU7zYjLxg3Z2KGq. Pablo informou ter criado a chave; inserir privadamente no painel do plugin |
| Instalação do plugin | Responsável pelo deploy LPV | ZIP v0.2 gerado pelo CI; instalar manualmente no WordPress. WPWriter não instala ZIP customizado |
| Atualização da política | Pablo | Minuta v0.1 preparada; não publicada |
| Validação externa sem registrar conversões | Assistente + conta/hospedagem | Depende das credenciais configuradas |
| QA dos três formulários | Responsável técnico | Somente com HTTP simulado até combinar teste real |
| Ativar medição e conectar evento à campanha | Pablo + responsável técnico | Após validação; sem alteração de orçamento ou veiculação |

## Escopo comercial

Esta etapa mede solicitação recebida pelo serviço de formulário. Venda efetiva, pagamento do sinal, Pix, fechamento por WhatsApp e realização do passeio permanecem eventos distintos e não são inferidos automaticamente.

## Próxima revisão

Após identificar a fonte de dados e concluir a validação externa. Registrar a versão implantada, resultado dos testes, consentimento, eventos recebidos, data e responsável antes de anunciar a integração como ativa.

## Atualização v0.2

Adicionado painel em Configurações -> LPV — ChatGPT Ads, Pixel ID preenchido, chave criptografada com campo de senha sem retorno do valor, e teste de conexão exclusivamente em modo validate_only. Salvar credenciais deixa a medição desligada. Incluído pacote ZIP instalável no CI. Nenhuma chave real foi recebida, gravada ou testada pelo assistente e nenhuma mudança foi aplicada ao site publicado.
