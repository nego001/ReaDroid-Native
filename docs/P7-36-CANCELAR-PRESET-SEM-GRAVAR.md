# P7.36 — Teste nativo do botão Cancelar, independente de Voltar

## Base aprovada

A [matriz P7.35.6 #40072530524](https://github.com/nego001/ReaDroid-Native/actions/runs/40072530524) terminou `success` em Android 10/API29 e Android 15/API35, incluindo duas sessões obrigatórias de instrumentação, 14 capturas PNG por API, cross-api review e Source/OTA. A suíte de navegação executou 36 testes em cada API; o relatório da segunda sessão registra 116 testes por API, sem falhas. Isso representa **152 testes por API** e **28 capturas reais**. A AVD foi configurada com 3 GB de RAM na tentativa bem-sucedida. Não é prova causal de que RAM foi a única razão das quedas anteriores.

## Lacuna

P7.35.5 comprovou o comportamento do botão **Voltar**, mas os usuários também podem clicar o **Cancelar** nativo do AlertDialog. É um callback diferente (`setNegativeButton`, em vez de `setOnCancelListener`) e a regressão precisa garantir que nenhum desses caminhos grava preferências.

## Novo teste

`P7NavigationInstrumentedTest.negativePresetButtonRestoresPreferencesAndReleasesDialog`:
1. Abre `MainActivity` e a seção Design real; copia **todas** as entradas de `v3_personalizacao`.
2. Escolhe um preset diferente do aplicado e verifica que a prévia anuncia `ainda não aplicada` e que nenhuma preferência mudou.
3. Inspeciona o AlertDialog nativo através do Studio, exige `dialog.isShowing()` e o botão real `Cancelar`, depois invoca `performClick()` no botão negativo (não simula a ação como sucesso).
4. Aguarda a UI ficar ociosa e exige que o diálogo tenha fechado, que `P7DesignStudio.activePresetConfirmation()` tenha sido limpo e que o cartão retorne a `selecionar prévia`.
5. Compara novamente **todo o mapa das preferências**, não apenas tema ou layout. Falhas são bloqueantes. `finally` cancela apenas uma janela ainda aberta para não interferir na próxima instrumentação.

## Critérios de saída
- [ ] Source checks, OTA e nova matriz Android API29/API35 aprovados no HEAD P7.36.
- [ ] Navegação completa com **37/37 testes** por API e segunda sessão com **116/116** por API, sem falhas/skip.
- [ ] 14 PNG por API e cross-review 28/28.
- [ ] Teste manual do botão Cancelar, botão Voltar e TalkBack no Galaxy A55; aceite visual 1:1 humano separado.

**Escopo restrito:** teste Android + documentação, sem mudanças na implementação de aparência, APK, SAF, assinatura, distribuição ou OTA. PR #13 draft, `main` intacta, `visual_1to1=NOT_APPROVED` e `physical=NOT_APPROVED`.
