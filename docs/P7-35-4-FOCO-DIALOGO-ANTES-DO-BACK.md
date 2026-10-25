# P7.35.4 — Verificar foco da confirmação antes de enviar Back na instrumentação

## Evidência anterior
A [CI P7.35.3 #40070700645](https://github.com/nego001/ReaDroid-Native/actions/runs/40070700645) terminou com **falha em Android 10 e 15**, ambas na nova regressão `cancellingDifferentPresetRestoresCommittedAppearance`, depois da entrega de KEYCODE_BACK e `waitForIdleSync()`. O Android 10 revelou o texto da asserção: `Retro, prévia escolhida, ainda não aplicada`. Nenhuma alteração do estado persistido foi demonstrada na etapa de seleção, mas a comparação final de preferências não foi alcançada. As duas sessões completas e cross-review continuam bloqueadas por `set -eu`.

## Hipótese mais restrita e teste
O método anterior chamava `pending.performClick()`, que abre `AlertDialog.show()` dentro de `scenario.onActivity`, e enviava Back imediatamente após retornar da chamada. Isso **não provava** que a janela do diálogo já estivesse focada e pronta para receber a tecla. Esperar apenas **depois** de Back não resolve um evento enviado para a janela errada.

A regressão agora:
- Espera o looper principal ficar ocioso **antes** de enviar Back;
- Usa `UiAutomation.getRootInActiveWindow()` para verificar que a janela ativa exibe exatamente o título `Aplicar <nome do preset>?`. Se não estiver focada, falha explicitamente; não considera a ação cancelada;
- Envia KEYCODE_BACK somente com a confirmação nativa visível no foco; espera ficar ocioso após;
- Exige `selecionar prévia` restaurado e comparação integral do mapa `v3_personalizacao`, incluindo inexistência de gravação durante a escolha. Nada é removido ou relaxado.
- Recicla o nó de acessibilidade. Nenhum campo APK/planos/assinatura é manipulado.

**Não afirmar causa raiz resolvida sem passagem do teste nos dois Androids.** Se a janela estava focada e ainda assim Back não restaurar, a investigação passa para o próprio listener nativo e seu dismiss/cancel, em vez de adicionar esperas arbitrárias.

## Gates
- [ ] Source/OTA e ambas sessões API29/35.
- [ ] Teste de cancelamento executa até verificar integralmente SharedPreferences.
- [ ] Inventário 14 capturas por API e cross-review 28/28.
- [ ] Atestado visual 1:1 e Galaxy A55/TalkBack fora do alcance da CI.

PR #13 draft; sem merge main, APK/OTA publicada ou aprovação física. `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
