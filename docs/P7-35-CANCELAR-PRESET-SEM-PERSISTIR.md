# P7.35 — Cancelar um preset não salva preferências nem mantém destaque pendente

## Base
P7.34 implementou diferença entre preset efetivamente aplicado e seleção temporária, e manteve os callbacks nativos do diálogo `Aplicar/Cancelar`. A P7.34 precisa concluir a matriz antes de integrar esta regressão.

## Teste Android real
`P7NavigationInstrumentedTest.cancellingDifferentPresetRestoresCommittedAppearance` abre o Design Studio na `MainActivity`, captura o mapa completo de preferências `v3_personalizacao`, escolhe uma das opções diferente do preset aplicado, verifica que a nova descrição anuncia **prévia escolhida, ainda não aplicada** e que a miniatura não ganha ✓, e garante que nenhum campo foi persistido durante a prévia. Envia o botão Android Back para cancelar o diálogo; exige que o cartão volte a **selecionar prévia** e compara novamente todo o mapa salvo com a cópia anterior.

Não usa APK real do usuário, não chama Aplicar, não grava fixtures persistentes e não altera o fluxo de produção. A instrumentação cobre um caminho real de `performClick`, diálogo e Back.

## Condições de saída
- [ ] A matriz da P7.34 precisa terminar, antes de integrar a P7.35.
- [ ] Source e OTA aprovados no novo commit.
- [ ] Matriz Android 10/15, capturas 14/API, revisão cruzada 28/28.
- [ ] Verificação humana do diálogo com TalkBack no Galaxy A55.
- [ ] Visual 1:1 e homologação física permanecem pendentes; sem merge nem publicação de APK/OTA.
