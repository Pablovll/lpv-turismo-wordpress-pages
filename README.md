# LPV Turismo — WordPress Pages

Repositório para versionar HTML e CSS do site LPV Turismo antes de aplicar no WordPress.

## Fluxo

1. Copie o CSS atual do WordPress para `css/lpv-style.css`.
2. Rode `python scripts/export_public_pages.py` para baixar páginas públicas em `pages/raw/`.
3. Organize os HTMLs em `pages/pt`, `pages/es` e `pages/en`.
4. Abra o repositório no Codex.
5. Use os prompts em `codex_prompts/`.
6. Depois de revisar, cole o HTML/CSS aprovado no WordPress.
7. Limpe LiteSpeed Cache e teste em aba anônima.

## Importante

WordPress continua sendo o CMS final. O GitHub serve para versionar, revisar e evitar perda de controle.
