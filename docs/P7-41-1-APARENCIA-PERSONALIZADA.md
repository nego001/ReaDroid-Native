# P7.41.1 — Tema personalizado não pode derrubar o Design Studio

## Falha real identificada após P7.41
O método `P7ThemeCatalog.currentTheme(Context)` devolve **-1** quando a aparência é personalizada, sem equivalência em nenhuma das 24 opções oficiais. A P7.41 acrescentou `P7ThemeCatalog.nameAt(currentTheme(a))` na renderização do selo ✓ para qualquer cartão de tema. Com `currentTheme(a) = -1`, o método `nameAt` chama `check(-1)` e lança `IllegalArgumentException`, impedindo a abertura do Design Studio, um caso já suportado pelo catálogo.

## Correção
- Ler `committedTheme` uma vez por cartão de tema e exigir `committedTheme >= 0` **antes** de usar `nameAt`.
- Nenhum dos 24 cartões deve se anunciar como "tema aplicado" ou receber selo ✓ se o visual salvo for personalizado; todos são opções a escolher.
- Preservar os selos baseados no valor salvo para layout e preset, os diálogos nativos, os controles TalkBack e as preferências.
- Regressão instrumentada `customThemeOpensDesignWithoutFakeAppliedBadge` salva temporariamente `accent=custom`, abre a Activity e a aba Design reais, percorre 24 cartões, exige nenhum selo aplicado e nenhuma alteração de preferência, e restaura a configuração anterior em `finally`.

A contagem exigida sobe de 157 para **158 instrumentados por API** (1+1+1+39+116), além de 14 screenshots/API e auditoria cruzada 28/28. **Não há publicação ou alteração na main**, e aceites visual 1:1 e físico continuam separados.
