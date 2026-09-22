# Etapa 3 - auditoria de qualidade e preparo para publicação

Data da revisão: 22 de setembro de 2026.

Este documento separa alterações locais, observações do WordPress público e decisões que ainda dependem do proprietário. Nenhuma página foi publicada e nenhum formulário real foi enviado durante a validação.

## Decisões atualizadas em 22/09/2026

- As sete páginas EN foram revisadas e autorizadas pelo proprietário para publicação. A aplicação no WordPress continua manual.
- Yoast foi removido pelo proprietário. AIOSEO é o único responsável por SEO (title, description, canonical, Open Graph e schema).
- A Política de Privacidade foi aprovada e publicada em https://lpvturismo.com/politica-de-privacidade/.
- Fonte editável informada: `LPV_Turismo_Politica_de_Privacidade_Site_2026.md`. Não localizada neste checkout, em Documentos ou Downloads; não foi recriada.
- O pacote e o checklist da Etapa 4 estão descritos em `docs/stage-4-wordpress-checklist.md`. As observações abaixo da Etapa 3 são históricas, não novas verificações.

## 1. Corrigido no projeto

- Cabeçalho, menu, seletor de idioma e rodapé foram uniformizados nos 22 fragmentos PT, ES e EN.
- O menu móvel agora tem botão próprio, `aria-controls`, `aria-expanded`, rótulo dinâmico, fechamento com Escape e devolução de foco.
- O idioma ativo usa `aria-current="page"` e um marcador visual, além da cor.
- Homepages e L&P Experiences deixaram de criar um segundo `<main>` dentro do `<main>` do WordPress.
- Os links de idioma mantêm passeio, serviço ou formulário equivalente. L&P usa fallback identificado em Serviços quando a tradução ainda não existe.
- Os três formulários aceitam apenas contextos conhecidos, mantêm o interesse editável e preservam o contexto ao trocar de idioma.
- Solicitações L&P e MIPIM exibem e exigem grupo, destino, objetivo e datas; esses controles ficam desabilitados nos pedidos comuns.
- Os formulários têm estados localizados de envio, sucesso e erro, `aria-live`, prevenção de duplo envio, `autocomplete` e `inputmode` adequados.
- A mensagem pública distingue solicitação de proposta de confirmação de reserva.
- Mensagens de WhatsApp são contextualizadas por página e idioma. O visitante ainda precisa revisar e enviar.
- Promessas amplas de segurança foram substituídas por cuidado e atenção à logística.
- As imagens das galerias receberam `loading="lazy"`; nenhuma URL de imagem foi alterada.
- Eventos seguros de Google Analytics foram adicionados e só executam quando `window.gtag` já existe.

## 2. Fontes e conteúdo dos passeios

A fonte de verdade disponível foi o próprio repositório: versões PT anteriores às melhorias, equivalências em `docs/page-map.json` e URLs de mídia já aprovadas. Não foram encontrados documentos comerciais externos com duração, capacidade, paradas obrigatórias, preços ou nível objetivo de esforço.

| Família | Páginas revisadas | O que está sustentado no repositório | O que não deve ser prometido sem confirmação |
| --- | --- | --- | --- |
| Mosaicos do Rio | PT, ES e EN | experiência urbana, privada ou pequeno grupo, PT/ES/EN, arte, arquitetura, fotografia e adaptações | duração fixa, bairros garantidos, capacidade máxima, acessibilidade total ou transporte incluído |
| Floresta da Tijuca | PT, ES e EN | natureza, paisagem, história ambiental, formato privado ou pequeno grupo e adaptação ao ritmo | trilha ou parada específica, duração, grau de dificuldade, acessibilidade integral ou transporte incluído |
| Rio Essencial | PT, ES e EN | ícones cariocas, paisagem, história, formato privado ou pequeno grupo e combinação definida antes da confirmação | atrações ou entradas garantidas, duração, capacidade, fila rápida ou transporte incluído |

### Imagens

- Mosaicos usa os mesmos três arquivos nas três línguas: `IMG_20251018_100412814_HDR_AE-scaled.jpg`, `IMG-20260426-WA0028-1-scaled.jpg` e `IMG_20250622_120651130_HDR-scaled.jpg`.
- Floresta usa os mesmos três arquivos nas três línguas: `IMG_20260517_094659964_HDR_AE-scaled.jpg`, `IMG_20250920_093610666_HDR_AE-scaled-e1780405744206.jpg` e `IMG_20251122_132250203_AE-scaled.jpg`.
- Rio Essencial usa os mesmos três arquivos nas três línguas: `IMG_20250627_082904606_HDR-scaled-e1780592537759.jpg`, `IMG_20260528_090415205_HDR_AE-scaled.jpg` e `IMG_20260521_152502255_HDR_AE-scaled.jpg`.
- As nove imagens carregam, têm texto alternativo localizado e são coerentes com as famílias dos passeios.
- Pendência editorial: a imagem principal de Mosaicos contém um resíduo visível no piso e a principal de Rio Essencial tem muito céu. A correção adequada é escolher arquivos ou recortes aprovados; não foi feita troca automática de URL.

### Materiais ausentes

- Não há conteúdo aprovado para um passeio Dois Irmãos. A página não foi criada.
- Não há avaliações verificáveis e autorizadas para publicação. Nenhum depoimento foi inventado.
- Preços, duração, capacidade, disponibilidade, acessibilidade detalhada e lista final de inclusões devem vir do proprietário antes de serem publicados como dados objetivos.

## 3. WordPress e SEO

### Observado no site público durante a Etapa 3

- PT, ES e EN retornaram `lang="pt-BR"` no HTML.
- AIOSEO 5.0.1.1 e Yoast estavam emitindo metadados, canonical e schema ao mesmo tempo, gerando duplicidade.
- Não foi encontrado `hreflang` nas páginas nem no sitemap.
- O sitemap público listava 22 URLs, incluindo as sete URLs EN.
- As sete URLs EN responderam HTTP 200, apesar de `docs/page-map.json` registrar a intenção de mantê-las em rascunho.
- O template nativo ainda entrega título, cabeçalho e rodapé no DOM; o CSS atual os oculta nas páginas personalizadas.
- Google Site Kit está ativo com a tag `GT-T56GNWWX`.

### Ações exatas no WordPress

1. Aplicar a autorização das sete páginas EN na publicação manual. A decisão editorial está resolvida; conferir o status efetivo no painel como verificação operacional.
2. Usar somente AIOSEO para title, description, canonical, Open Graph e schema. Yoast já foi removido; conferir a saída após limpar o cache, sem reativá-lo.
3. Configurar o idioma real de cada página no WordPress ou no plugin multilíngue: `pt-BR`, `es` e `en`.
4. Criar `hreflang` recíproco somente entre páginas publicadas e equivalentes. Usar PT como `x-default`. Não anunciar EN enquanto estiver em rascunho.
5. Remover do template de página os blocos nativos Post Title, Header e Footer nas páginas LPV personalizadas. O CSS continua protegendo a aparência, mas o template deve deixar de gerar conteúdo duplicado.
6. Definir imagem social por família no plugin SEO, usando apenas mídia aprovada e mantendo as URLs atuais até decisão editorial.

### Metadados finais para AIOSEO

Os valores abaixo são a fonte dos metadados finais do pacote da Etapa 4. Pertencem ao AIOSEO, não aos fragmentos HTML. O gerador conserva estes textos integralmente.

| URL | Title recomendado | Description recomendada |
| --- | --- | --- |
| `/` | LPV Turismo - Experiências guiadas no Rio | Descubra o Rio com roteiros culturais e naturais, curadoria local e atendimento em português, espanhol ou inglês. |
| `/passeios/` | Passeios no Rio de Janeiro - LPV Turismo | Compare experiências guiadas de cultura, natureza e paisagem e solicite uma proposta adequada ao seu grupo. |
| `/outros-servicos/` | Serviços turísticos no Rio - LPV Turismo | Transfers, apoio local, experiências privadas e soluções personalizadas para sua viagem ao Rio de Janeiro. |
| `/quero-montar-meu-roteiro/` | Solicite uma proposta - LPV Turismo | Conte sobre sua viagem, grupo e interesses para solicitar uma proposta personalizada. O envio não confirma reserva. |
| `/passeios/mosaicos-do-rio/` | Mosaicos do Rio - Experiência urbana guiada | Arte, arquitetura, fotografia e vida cotidiana em uma experiência urbana adaptável ao perfil do grupo. |
| `/passeios/imersao-floresta-da-tijuca/` | Imersão na Floresta da Tijuca - LPV Turismo | Natureza, paisagem e história ambiental em uma experiência guiada adaptada ao ritmo do grupo. |
| `/passeios/rio-essencial/` | Rio Essencial - Passeio guiado no Rio | Uma leitura guiada dos ícones, da paisagem e da história do Rio, com percurso definido antes da confirmação. |
| `/lp-experiences/` | L&P Experiences - Business trips e missões | Jornadas profissionais para grupos, combinando objetivos de negócio, cultura, conexões e curadoria no destino. |
| `/es/` | LPV Turismo - Experiencias guiadas en Río | Descubrí Río con recorridos culturales y naturales, curaduría local y atención en español, portugués o inglés. |
| `/es/paseos/` | Paseos en Río de Janeiro - LPV Turismo | Compará experiencias guiadas de cultura, naturaleza y paisaje y solicitá una propuesta para tu grupo. |
| `/es/servicios/` | Servicios turísticos en Río - LPV Turismo | Transfers, apoyo local, experiencias privadas y soluciones personalizadas para tu viaje a Río de Janeiro. |
| `/es/quiero-armar-mi-itinerario/` | Solicitá una propuesta - LPV Turismo | Contanos sobre tu viaje, grupo e intereses para solicitar una propuesta. El envío no confirma una reserva. |
| `/es/mosaicos-del-rio/` | Mosaicos de Río - Experiencia urbana guiada | Arte, arquitectura, fotografía y vida cotidiana en una experiencia urbana adaptable al perfil del grupo. |
| `/es/inmersion-floresta-da-tijuca/` | Inmersión en la Floresta da Tijuca - LPV | Naturaleza, paisaje e historia ambiental en una experiencia guiada adaptada al ritmo del grupo. |
| `/es/rio-esencial/` | Río Esencial - Paseo guiado en Río | Una lectura guiada de los íconos, el paisaje y la historia de Río, con recorrido definido antes de confirmar. |
| `/en/` | LPV Turismo - Guided experiences in Rio | Discover Rio through cultural and nature-focused itineraries with local curation in English, Portuguese or Spanish. |
| `/en/tours/` | Tours in Rio de Janeiro - LPV Turismo | Compare guided culture, nature and landscape experiences and request a proposal suited to your group. |
| `/en/services/` | Travel services in Rio - LPV Turismo | Transfers, local support, private experiences and tailored solutions for your trip to Rio de Janeiro. |
| `/en/plan-my-itinerary/` | Request a proposal - LPV Turismo | Tell us about your trip, group and interests to request a tailored proposal. Submission does not confirm a booking. |
| `/en/mosaics-of-rio/` | Mosaics of Rio - Guided urban experience | Art, architecture, photography and everyday life in an urban experience adapted to your group's profile. |
| `/en/tijuca-forest-immersion/` | Tijuca Forest Immersion - LPV Turismo | Nature, landscape and environmental history in a guided experience adapted to the group's pace. |
| `/en/rio-essential/` | Rio Essential - Guided tour in Rio | A guided reading of Rio's landmarks, landscape and history, with the route agreed before confirmation. |

Canonical recomendado: `https://lpvturismo.com` mais o caminho exato da página, sem parâmetros de contexto ou sucesso.

## 4. Acessibilidade e responsividade

- Foram verificadas as 22 páginas em 320, 375, 768, 1024 e 1440 px: 110 combinações sem overflow horizontal, títulos cortados, IDs duplicados ou ausência de landmarks principais.
- Em até 980 px, o menu inicia fechado e seus links não recebem foco. Acima desse breakpoint, o menu completo permanece visível.
- O menu abriu e fechou por botão, fechou com Escape e devolveu o foco ao controle.
- Cabeçalhos mantêm um único H1 por página; o preview completo mantém um único `main`.
- Imagens informativas têm `alt`; ícones decorativos usam `alt=""` e rótulo oculto no link.
- Contrastes calculados: verde/off-white 10,93:1; texto/off-white 8,22:1; branco/terracota 4,54:1; ivory/deep navy 15,62:1; sand/deep navy 10,03:1.
- Há foco visível de alto contraste e redução de movimento para `prefers-reduced-motion`.
- O navegador de teste não expôs controle confiável de zoom a 200%. O reflow em 320 px passou e não há tipografia dimensionada por viewport, mas a verificação manual em 200% continua pendente antes da publicação.

Capturas: `.audit-shots/stage3/home-desktop-1440.png`, `home-mobile-375.png`, `tour-desktop-1440.png`, `tour-mobile-375.png`, `form-mipim-1024.png`, `menu-mobile-375.png` e `lp-experiences-mobile-375.png`.

## 5. Formulários

- Foram verificados 24 cenários sem envio: acesso direto, sete contextos permitidos e um valor inválido em PT, ES e EN.
- Valores inválidos retornam ao contexto de roteiro personalizado; não geram assunto ou URL arbitrária.
- O idioma inicial é PT, ES ou EN conforme a página e continua editável.
- Nome e e-mail são obrigatórios; e-mail e telefone usam teclado e preenchimento adequados.
- Contextos L&P e MIPIM tornam obrigatórios datas, perfil do grupo, destino e objetivo.
- Estados de sucesso e erro foram renderizados por parâmetros locais controlados; o estado pendente foi validado por sintaxe e revisão de código.
- A entrega real pelo FormSubmit e o recebimento em `info@lpvturismo.com` não foram testados para evitar e-mail real.
- Limitação atual: o FormSubmit faz navegação direta. Um erro de rede do provedor não redireciona automaticamente para `?erro=1`; esse estado existe para integração futura ou tratamento manual.

## 6. Privacidade, analytics e desempenho

### Privacidade

Resolvido pelo proprietário em 22/09/2026: política aprovada e publicada em https://lpvturismo.com/politica-de-privacidade/. A Etapa 4 adiciona esse link aos 22 rodapés locais, com indicação de documento em português nos idiomas ES e EN. O conteúdo jurídico não foi alterado. A fonte editável informada é `LPV_Turismo_Politica_de_Privacidade_Site_2026.md`, ainda não localizada no repositório.

### Analytics

O código usa a instalação existente do Site Kit e não cria nova propriedade. Eventos adicionados:

- `lpv_tour_open`: `tour_id`, `page_path` e `page_language`.
- `lpv_whatsapp_click`: `page_path` e `page_language`.
- `lpv_proposal_request_submit`: contexto validado e idioma.

Não são enviados nome, e-mail, telefone, texto de WhatsApp, campos livres ou valor comercial. Os eventos não usam semântica de compra ou venda. A validação no GA DebugView depende da publicação e continua pendente.

### Desempenho local indicativo

| Página | Mediana antes | Mediana depois | Observação |
| --- | ---: | ---: | --- |
| Home PT | 2.022 ms | 200 ms | 6 imagens; cache local já aquecido no teste final |
| Mosaicos PT | 1.150 ms | 177 ms | 9 imagens; galeria agora usa lazy loading |

Esses números são de preview local sem throttling e não equivalem a Core Web Vitals. A diferença indica ausência de regressão óbvia, mas deve ser confirmada com PageSpeed Insights ou Lighthouse após publicação. O script comum acrescenta seis nós de menu e um script inline por página.

## 7. Pendências por responsável

### Implementado no repositório

- Navegação móvel acessível, equivalências de idioma, fallback L&P, formulários contextualizados, estados de interface, copy sem garantia absoluta, lazy loading, eventos analytics sem PII e documentação de publicação.

### Depende do WordPress/proprietário

- Aplicar manualmente a publicação EN já autorizada e conferir o status no painel.
- Configurar no AIOSEO os metadados, canonical, Open Graph e schema; a escolha do plugin já está resolvida.
- Corrigir `lang` e adicionar `hreflang` apenas entre páginas publicadas.
- Remover blocos nativos duplicados do template.
- Aplicar os rodapés atualizados no WordPress; a política e seu destino já estão aprovados.
- Autorizar substituição das duas imagens com enquadramento editorial fraco.
- Fornecer material aprovado para Dois Irmãos, avaliações, preços, duração, capacidade e acessibilidade detalhada.
- Validar FormSubmit com um envio real controlado e conferir os eventos no GA DebugView.

### Checklist antes de publicar

1. Fazer backup do WordPress e do CSS adicional atual.
2. Confirmar status e idioma de cada página no painel.
3. Aplicar os fragmentos e o CSS revisados em ambiente de staging.
4. Configurar AIOSEO com a tabela acima e a integração de idiomas conforme o checklist da Etapa 4.
5. Testar manualmente zoom a 200% e leitores de tela básicos. Não enviar formulários nesta etapa; entrega real exige autorização separada.
6. Verificar sitemap, canonical, `hreflang`, compartilhamento social e DebugView.
7. Repetir desktop e celular no domínio público ao aplicar a publicação EN já aprovada.
