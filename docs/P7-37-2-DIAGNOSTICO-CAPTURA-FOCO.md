# P7.37.2 — Guardar diagnóstico de perda de foco da captura

A [CI P7.37.1 #40107514539](https://github.com/nego001/ReaDroid-Native/actions/runs/40107514539) passou no Android10/API29 e falhou na API35 **antes das cinco sessões de teste**. `P7ExplorerPopulatedCaptureInstrumentedTest.captureRealActivityWithIndexedSyntheticApk` retornou `AssertionError` na linha 198: `Explorer Activity lost foreground window focus after bounded recovery; no unrelated overlay was dismissed`. O PNG foi corretamente recusado, e a auditoria cruzada foi bloqueada. O log não mostra qual janela detinha o foco nem comprova ANR no aplicativo.

## Diagnóstico sem retry ou redução do gate
- `tools/p7_capture_populated.sh` limita uma única instrumentação a 90 segundos e continua exigindo `OK (1 test)`. Código não zero, falha JUnit ou timeout retornam código 5, sem captura validada.
- Na falha, cria `p7-capture-diagnostics-android-<api>.txt` contendo SHA, código do comando e **apenas estado de boot, janela em foco e Activity retomada**. As consultas ADB diagnósticas são limitadas por timeout e não mudam o resultado.
- O workflow carrega esse arquivo junto das evidências com `if: always()`. Ele **não é substituto** de um PNG.
- Contrato Python simula falhas JUnit e de comando ADB, exige o diagnóstico, impede PNG no fracasso e impede gerar diagnóstico em caso de sucesso.
- A instrumentação Android continua exigindo foco real e verificação de pixels. Não há dispensa de janelas desconhecidas, overlay, falhas de app ou interferência externa.

**P7.37.2 não aprovada antes da nova matriz:** 1+1+1+35+116=154 testes por API, 14 capturas API29/API35 e cross-review 28/28, Source/OTA. P7.38 continua fora da PR até essa matriz passar. Visual 1:1, Galaxy A55/TalkBack pendentes. `main` intacta, sem APK/OTA publicada.
