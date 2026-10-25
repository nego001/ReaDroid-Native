# P7.50.4 — hierarquia visual do título “Ações rápidas” na Home

## Diferença comprovada (25/10/2026)

Comparação da **referência oficial aprovada** `design/reference/p7/negrecodroid_controle_total_de_apks.png` com a captura real `p7-brand-android-35.png` extraída do artefato de [P7.50.3.1, CI #40176254848](https://github.com/nego001/ReaDroid-Native/actions/runs/40176254848): a seção **Ações rápidas** aparece em branco, com hierarquia de seção, na prancha; no app ela aparece **azul e pequena**. A causa no código era `MainActivity.shortcutsTitle` inicializado com `NegrescoTheme.ACCENT` e 12sp; `StudioDashboard` corrigia texto e negrito, mas preservava aquelas duas propriedades.

## Ajuste nativo

- O cabeçalho mantém o texto **“Ações rápidas”**, com `AccessibilityHeading` e sem ação falsa.
- O título passa a usar `NegrescoTheme.TEXT` (branco no tema OLED, foreground adequado em graphite e light) e **15sp escalonado pela opção de tamanho de texto**. O azul continua em ícones, ações, estados ativos e detalhes de destaque. Nada é pintado com bitmap/screenshot ou escondido.
- Os seis botões existentes mantêm as mesmas ações, rótulos TalkBack, ordem, dados reais e alvos de toque. Sem mudanças de SAF, SQLite, segurança, planos de edição, compilação, assinatura ou publicações.

## Regressão obrigatória

O novo teste Android `homeQuickActionsHeadingUsesReferenceTextColorAcrossThemes` abre o `MainActivity` real nos temas OLED, graphite e light; localiza o heading acessível, exige a cor dinâmica de texto (não cor de acento), contraste texto/fundo ≥4,5:1 e tamanho compatível com o título de 15sp. Restaura as preferências mesmo diante de erro. O contrato Python exige exatamente **46** métodos `@Test` na navegação e a presença da regressão.

**Meta de CI desta mudança:** **169 testes instrumentados por API** = seis sessões isoladas + 46 da navegação + 117 do bloco restante. Android 10/15, 14 PNG/API, 320dp/130%, fonte 200%, reboot da API 35, cross 28, Source e OTA continuam obrigatórios. **Este documento não aprova a alteração antes da CI.**

**Estado:** staging sobre P7.50.3.1 aprovada; PR #13 em draft, `main` intacta; nenhuma publicação APK/OTA. A revisão humana 1:1 e o ensaio Galaxy A55 com TalkBack continuam pendentes.
