# P7.49 v3 — Guarda única e cancelamento Android Back com a base P7.48.4

## Pré-requisitos
Base: commit `0d248e11` da PR #13. A matriz desse commit ainda falhou na primeira tentativa com `Tab 'Início' not found` no smoke de viewport compacto API35, após concluir **todos os 165 testes instrumentados Android 15**. A tentativa isolada da API35 foi solicitada e ainda não tinha resultado final ao preparar esta branch.

## Melhorias
1. O método de produção `P7DesignStudio.showCatalogDialog` usa a guarda já existente `appearanceDialogShowing()`, que contempla os quatro handles de diálogos (tema, layout, preset e chooser), em vez de duplicar três verificações. Não libera empilhamento.
2. Regressão instrumentada `androidBackRollsBackThemeLayoutAndPresetConfirmations`: abre a confirmação de opção ainda não aplicada em cada família via Activity real, envia KEYCODE_BACK, aguarda o fim de OnCancel/OnDismiss, exige fechamento de todas as janelas e restauração do estado sem alterações nas preferências; reabre e cancela para comprovar que não houve resíduo.
3. Contrato de código-fonte verifica a nova guarda e todas as asserções, mantendo o teste Android Back do seletor P7.48.1 e os isolamentos da prévia do logo e dos cartões de criador.

## Cobertura obrigatória
**166 testes/API** = cinco? `1+1+1+1+1+1+44+116` (6 classes isoladas com 1 teste + 44 de navegação + 116 restantes), **8 sessões instrumentadas**, **27 seletores distintos**, 14 capturas/API, cross 28, checagens Source/OTA, viewport 320dp/130%, fontes 200%, reboot API35. Não há skipped, retry silencioso nem tolerância para captura errada.

**Estado:** apenas staging, sem CI própria nem integração até a matriz anterior ser aprovada. PR #13 draft, main intacta, sem APK/OTA publicado; visual humano 1:1 e Galaxy A55/TalkBack físico não aprovados.
