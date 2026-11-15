# P7.35.6 — Estabilidade do emulador com 3 GB e diagnóstico de memória

## Evidência

A [P7.35.5 CI #40071933606](https://github.com/nego001/ReaDroid-Native/actions/runs/40071933606) falhou no Android 15/API35. A primeira sessão `P7NavigationInstrumentedTest` iniciou 36 testes. A regressão `cancellingDifferentPresetRestoresCommittedAppearance` **não falhou**; a queda aconteceu mais tarde, em `bottomNavigationScalesWithoutClippingOrChangingLabels`, que lança `MainActivity` com fonte 135%. Após 31 testes completos, o emulador desapareceu de ADB e o runner encerrou a instrumentação. O logcat disponível termina com `MainActivity RESUMED` e não traz stack trace do aplicativo, OOM explícita ou causa raiz definitiva.

Na configuração existente: Pixel 3a Google APIs x86_64, `cores:2`, **`ram-size: 2048M`**, `disk-size:4096M`, GPU Swiftshader indireta. Para eliminar pressão por RAM como variável, a próxima tentativa usa `ram-size: 3072M` e registra memória disponível do host antes de iniciar os emuladores.

## Garantias

- Exatamente as mesmas 21 seleções de instrumentação e as duas sessões obrigatórias: classe inteira de navegação e outras 20 seleções; sem exclusão, retry de asserção, skip ou aprovar manualmente.
- Sem alterações em código de produção, layouts, assets, testes Java ou fluxo de `AlertDialog`; a regressão Back/Cancelar continua integral.
- Preservados Android 10/API29 e Android 15/API35, captura sintética isolada, 14 PNGs por API, inventário e cross-review 28/28.
- Teste `test_p7_capture_runner.py` protege orçamento de memória, log de recursos e contrato de suites.
- **Aumento de RAM é uma hipótese de estabilidade, não prova de causa raiz.** Falhas futuras continuarão sendo bloqueantes e registradas.

## Gates
- [ ] Conclusão da matriz P7.35.5 antes de avançar a branch, preservando resultados anteriores.
- [ ] Source checks e OTA da P7.35.6.
- [ ] API29/API35 completam 36/36 de navegação e segunda sessão de regressões.
- [ ] 14 PNGs por API e auditoria 28/28.
- [ ] Validação visual 1:1 e Galaxy A55/TalkBack continuam humanas e pendentes.

PR #13 draft; sem merge em main, APK de distribuição ou OTA publicada. `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
