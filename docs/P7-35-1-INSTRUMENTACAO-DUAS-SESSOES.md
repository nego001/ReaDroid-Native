# P7.35.1 — Duas sessões completas de instrumentação Android, sem perder testes

## Evidência do problema
- [P7.35, execução #40068224483](https://github.com/nego001/ReaDroid-Native/actions/runs/40068224483): Source checks e OTA verde; Android 10/API29 `success`; Android 15/API35 `failure`; cross-review `skipped`.
- A API35 iniciou **152 testes**, concluiu apenas 24 e permaneceu cerca de 35 segundos no `P7NavigationInstrumentedTest.layoutCardsKeepCompleteNamesAndNativeButtonRoleAtLargeFont`. O XML de resultado apontou falha sem stack de asserção, com `device 'emulator-5554' not found`. Os demais 128 testes não foram executados. Reproduziu o padrão intermitente da primeira tentativa na P7.34; uma segunda tentativa na P7.34 havia passado no mesmo SHA.
- **Causa raiz não provada** (emulador/ADB, memória da VM ou atividade sob teste); nenhum defeito da aplicação pode ser inferido sem evidência adicional.

## Correção operacional
- O workflow preserva todas as **21 seleções distintas** de teste, incluindo as 20 classes completas e uma seleção de método de proteção contra overlay sintético.
- A classe inteira `P7NavigationInstrumentedTest`, incluindo o teste de fontes ampliadas e o teste P7.35 de Back/Cancelar, roda **primeiro** numa sessão Gradle independente, em emulador recém-inicializado após a captura isolada do Explorador.
- As outras **20 seleções** (classes/método) executam em segunda sessão `:app:connectedDebugAndroidTest`. Nenhuma seleção é removida, excluída, ignorada, reduzida ou convertida em sucesso artificial. `set -eu` interrompe se **qualquer** das duas sessões falhar; nada de screenshots ou aprovação cruzada sem passar.
- O APK de debug compilado no job continua reinstalado depois das duas sessões; todas as capturas 14/API e inventário 28/28 permanecem obrigatórios.
- O teste de contrato `tests/test_p7_capture_runner.py` exige duas invocações, a classe de navegação primeiro, 21 seleções únicas, 20 posteriores e métodos sensíveis preservados.

## Gates
- [ ] Source checks e OTA do SHA P7.35.1.
- [ ] Ambas sessões Gradle finalizadas no Android 10/API29 e 15/API35.
- [ ] Teste de cancelamento P7.35 executado e aprovado nas duas APIs.
- [ ] 14 PNG reais por API; auditoria cruzada 28/28.
- [ ] Teste humano Galaxy A55/TalkBack e aceite visual 1:1 separados.

PR #13 permanece draft e `main` intacta; sem APK de distribuição ou OTA publicada. `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
