# P7.29.2 — Reinstalação do debug APK após instrumentação (sem atalhos)

## Falha real detectada

No commit P7.29.1 `4e07acbabdf40f92ebe94d8f8fcc067cee4584b7`, a [CI #40062234872](https://github.com/nego001/ReaDroid-Native/actions/runs/40062234872) terminou com falha nas APIs 29 e 35. Os logs mostram:

- `assembleDebug` / `assembleDebugAndroidTest`: **BUILD SUCCESSFUL**.
- Captura isolada `p7_capture_populated.sh` no início da sessão: concluída; a suíte geral foi executada depois.
- `connectedDebugAndroidTest`: **145/145 testes executados sem falhas** e **BUILD SUCCESSFUL** em ambos os Androids.
- Ao iniciar o screenshot da Home: `adb shell am start -W -n com.readroid.app/.MainActivity` retornou **Error type 3: Activity class does not exist**.
- Na API29, `pidof com.readroid.app` também falhou. Em ambas, o inventário visual não foi emitido e `cross-api-visual-review` foi **skipped**.

**Causa operacional:** a suíte Gradle encerrou desinstalando o APK alvo de instrumentação. Como a captura do Explorador sintético foi movida para **antes** dessa suíte na P7.29.1, era necessário restaurar o APK de debug compilado antes dos demais smokes, que abrem a `MainActivity`. O erro **não é evidência** de defeito no vetor das abas, no Design Studio ou nos 145 testes funcionais.

## Correção aplicada

- Depois do `connectedDebugAndroidTest`, o workflow executa `adb install -r app/build/outputs/apk/debug/app-debug.apk` para reinstalar somente o artefato debug **compilado no mesmo job e mesmo commit**.
- Requer `adb shell pm path com.readroid.app | grep -Fq 'package:'` antes de abrir `MainActivity`. Qualquer erro de instalação, falta do pacote ou falha de lançamento interrompe o job; não há fallback silencioso nem uso de APK release.
- Mantida a ordem comprovável: `assembleDebug + assembleDebugAndroidTest → captura Explorer sintético no emulador inicial → connectedDebugAndroidTest → reinstalação → pm path → MainActivity → todos os smokes e 14 PNGs`.
- `tests/test_p7_capture_runner.py` exige essa ordenação, a presença do comando de reinstalação e da verificação explícita de pacote instalado. Não foi excluído teste Android, alterado timeout, aceito screenshot inválida nem removido guard de foco/ANR.
- Sem alteração de código de produção, banco, APKs pessoais, SAF, versão, identidade instalada, assinatura ou OTA.

## Gate de comprovação no HEAD P7.29.2

- [ ] Source checks e OTA passam no SHA final.
- [ ] Android 10/API29 e Android 15/API35: captura isolada limpa, 145 testes gerais e reinstalação demonstrada pelos logs.
- [ ] Todos os smokes e inventários individuais geram **14 PNGs por API** com os dois hashes das referências oficiais.
- [ ] `cross-api-visual-review` aceita **28/28** imagens sem duplicações indevidas nem aprovação de fidelidade inventada.
- [ ] Rever as capturas P7.29 com ícones das quatro abas em layout normal, sem ícones em 320dp/130% e em 200% fonte; verificar texto, foco e scroll.
- [ ] Homologação humana 1:1 e Galaxy A55 físico/TalkBack ainda são indispensáveis.

**Estado:** PR #13 continua draft, `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`, sem merge para main, APK distribuível nem OTA publicada.
