# P7.36.1 | Regressão de barra inferior 135% em sessão isolada

## Evidência da falha

[P7.36 CI #40074203901](https://github.com/nego001/ReaDroid-Native/actions/runs/40074203901): Android 10/API29, Source e OTA **success**; Android 15/API35 **failure**; cross-review **skipped**. API35 iniciou 37 testes, recebeu 32 resultados e perdeu o emulador durante `bottomNavigationScalesWithoutClippingOrChangingLabels`. O XML marcou `<failure></failure>` depois de **42,124 segundos**, sem stack de asserção; ADB reportou `device emulator-5554 not found`. Em `meminfo`, havia aproximadamente **1,5 GB MemAvailable** na AVD de 3 GB, sem OOM explícita ou crash demonstrado da aplicação. A hipótese de RAM como causa única não é sustentada pelos logs.

## Alteração limitada à instrumentação

- O método exato `bottomNavigationScalesWithoutClippingOrChangingLabels` foi movido integralmente de `P7NavigationInstrumentedTest` para a classe `P7BottomNavigationLargeFontInstrumentedTest` e recebe o mesmo helper de busca de abas. Nenhum assert foi alterado: seis políticas `navTabHeightDp`, cinco abas, altura, foco, clique e nomes acessíveis, fonte `135%`, `nav_labels` e rollback das preferências.
- Primeiro `:app:connectedDebugAndroidTest`: **um teste**, isolado após a captura sintética prévia do Explorador, num emulador recém-inicializado.
- Segundo: **36 testes** restantes da navegação, incluindo Cancelar e Back dos presets.
- Terceiro: mesmas **20 seleções** de outras classes/método antioverlay, totalizando os **116 testes** anteriores.
- Total esperado permanece **153 por API (1+36+116)**, sem excluir/duplicar qualquer método. `set -eu` bloqueia o job se qualquer sessão falhar. Mesma RAM 3GB, mesmos smokes e 14 PNG/API, revisão cruzada 28/28.
- `tests/test_p7_capture_runner.py` exige 3 sessões, 22 seleções distintas, teste isolado presente apenas uma vez, 36 testes restantes e as asserções essenciais. Nenhum código de produção, APK real do usuário ou distribuição alterados.

## Critérios de aprovação
- [ ] Source/OTA e compilação Java no novo SHA.
- [ ] API29/API35: todas as sessões 1/1, 36/36, 116/116 verdes.
- [ ] Capturas 14/API e cross-review 28/28.
- [ ] Inspeção humana do Galaxy A55/TalkBack e aceite visual 1:1 continuam pendentes.

PR #13 draft; `main` intacta; sem merge, APK distribuído ou OTA. `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
