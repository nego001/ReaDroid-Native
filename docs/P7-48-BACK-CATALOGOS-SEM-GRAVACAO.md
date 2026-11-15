# P7.48 — Botão Android Back fecha catálogos sem salvar

Esta etapa complementa a P7.47: os três seletores nativos `Ver todos` já são testados contra empilhamento e fechamento pelo botão `Fechar`. Falta exercitar o fechamento real por **Android Back**, que passa pelo cancelamento da janela e deve liberar a referência antes de reabri-la.

## Regressão Android
`androidBackClosesEveryCatalogWithoutCommittingAppearance` abre a `MainActivity` real e percorre os três catálogos de Tema, Layout e Preset. Para cada catálogo, exige dialog nativo `isShowing()` e `isAttachedToWindow()`, envia o evento `KEYCODE_BACK` pela instrumentação, aguarda `waitForIdleSync()`, verifica a janela fechada e todas as referências (chooser/confirmations) nulas, assegura `v3_personalizacao` idêntico, reabre aquele mesmo catálogo e fecha por `Fechar`. Aguarda novamente o término de `OnDismiss`, assegura nenhuma gravação, e limpa eventual janela em `finally`.

**Escopo:** apenas testes instrumentados e contrato Python (sem código de produção). Total de navegação sobe de 44 para 45, **165 instrumentados/API** (`1+1+1+1+45+116`). Mantidos 14 screenshots/API, 28 comparações, checks Source/OTA, fail-closed, reboot, viewport e fontes. Este staging não é considerado aprovado até CI Android29+Android35+cross. Nenhuma aprovação visual humana 1:1 ou teste físico Galaxy A55/TalkBack é inferida.
