# P7.50.3 — selo de aparência aplicada usa a cor realmente salva (staging)

## Diferença de identidade observada no código

O Design Studio apresenta a cor selecionada em bordas, cartões e prévias, mas o selo circular "✓" dos **temas, layouts e presets aplicados** utilizava exclusivamente `#1688ff` com glifo branco, mesmo com destaque salvo verde, laranja, roxo ou customizado. Isso diverge do estado visual real quando o usuário muda a paleta. O azul padrão da arte de referência continua sendo o padrão original, mas não deve virar um indicador de outra escolha.

## Mudança nativa e segurança

- O selo de **opção efetivamente aplicada** passa a usar `NegrescoTheme.ACCENT`, carregado das preferências `v3_personalizacao` pelo mecanismo existente; a cor do "✓" usa `NegrescoTheme.ON_ACCENT`, calculada para contraste claro/escuro.
- Não muda quais opções recebem o selo. Escolha pendente permanece com rótulo acessível "prévia escolhida, ainda não aplicada" e **sem** o selo de aplicado. Os estados reais de tema, layout e preset continuam sendo consultados em `P7ThemeCatalog` e `P7VisualCatalog`.
- A borda dos cartões, o resto da prévia, os cinco botões inferiores e o funcionamento de Aplicar/Cancelar/Voltar permanecem inalterados; preferências, arquivos e APK nunca são gravados por visualizar o Design.
- Novo teste Android `appliedDesignBadgeRespectsSavedAccentAndReadableCheck` abre a **Activity real**, percorre combinações OLED/graphite/light com azul/verde/laranja/roxo e custom claro/escuro, inspeciona o `GradientDrawable` real do selo, verifica foreground, contraste ≥4.5:1, e restaura as preferências até após falhas. Sem screenshots falsos ou aplicação de tema durante os testes.

**Status:** staging sobre P7.50.2, **não integrado**, aguardando resultado da CI da [P7.50.2 #40175035213](https://github.com/nego001/ReaDroid-Native/actions/runs/40175035213). Quando integrado, a meta sobe de 167 para **168 testes por Android** (6 sessões isoladas + 45 de navegação + 117 restantes), mantendo 8 sessões obrigatórias, 14 PNG por API, cross 28, Android10/15, fontes e viewport compactos, Source/OTA. A revisão humana visual 1:1 e o ensaio Galaxy A55/TalkBack permanecem pendentes. PR #13 draft; `main` inalterada, sem distribuição de APK/OTA.
