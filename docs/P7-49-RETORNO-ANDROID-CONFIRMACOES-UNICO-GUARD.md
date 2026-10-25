# P7.49 — Proteção única de diálogo e botão Android Voltar

Esta branch herda a **P7.48.4** (incluindo as classes isoladas da prévia de logotipo e dos cartões criadores a 135%), sem tocar nos seus métodos, nas exigências de capturas ou nos critérios de aprovação.

## Produção
O seletor nativo `showCatalogDialog` utiliza a proteção comum já existente `appearanceDialogShowing()` em vez de duplicar inspeções de handles de tema, layout e preset. Ela considera as quatro famílias: `catalogChooser`, `themeConfirmation`, `layoutConfirmation` e `presetConfirmation`. Reentradas permanecem bloqueadas enquanto algum diálogo estiver visível. Nenhuma funcionalidade foi removida ou publicada.

## Teste Android
O novo teste `androidBackRollsBackThemeLayoutAndPresetConfirmations` usa a MainActivity real, seleciona uma alternativa para cada família Tema/Layout/Preset, abre a confirmação nativa Aplicar e envia `KEYCODE_BACK`. Exige fechamento, `OnDismiss` concluído, todos os handles nulos, rótulo da prévia de volta ao estado não aplicado e preferências `v3_personalizacao` idênticas. Reabre a confirmação e testa `Cancelar` com a mesma preservação do estado.

O contrato Python confirma as verificações de Back e a proteção única, e mantém as regressões anteriores. Total previsto **166 instrumentados/API** distribuídos em **8 sessões obrigatórias**, `1+1+1+1+1+1+44+116`, **27 seletores únicos**, 14 screenshots/API e 28 cross. Testes compactos 320dp/130%, fontes 200%, reboot API35, Source/OTA e captura fail-closed permanecem obrigatórios.

**Situação:** commit preparado somente em staging. A integração na PR #13 depende da P7.48.4 ficar integralmente verde e a própria P7.49 exigirá sua nova matriz. `main` intacta, PR draft, sem APK/OTA distribuído; visual 1:1 e Galaxy A55/TalkBack físico pendentes.
