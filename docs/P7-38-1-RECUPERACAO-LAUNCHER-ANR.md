# P7.38.1 — Reconhecimento seguro de ANR do Pixel Launcher por processo

A matriz [P7.38 #40109486801](https://github.com/nego001/ReaDroid-Native/actions/runs/40109486801) teve API29 verde; API35 falhou inicialmente ao instalar o emulador porque o SDK apresentou `Error on ZipFile unknown archive`. A repetição da execução instalou o emulador, mas falhou na captura populada anterior aos testes, por falta de foco real na Activity. O artefato de diagnóstico real `p7-capture-diagnostics-android-35.txt` revelou:

```
mCurrentFocus=Window{... Application Not Responding: com.google.android.apps.nexuslauncher}
mFocusedApp=ActivityRecord{... com.google.android.apps.nexuslauncher/.NexusLauncherActivity ...}
```

Trata-se de ANR do **Pixel Launcher do emulador**, não de um crash comprovado do NegrecoDroid. O comportamento fail-closed estava correto.

## Alteração limitada
Em `P7ExplorerPopulatedCaptureInstrumentedTest`, se a janela Accessibility não apresentar o texto literal `Pixel Launcher isn't responding`, a verificação passa a consultar o `dumpsys window` via `UiAutomation`. **Exige simultaneamente**: `mCurrentFocus` nomeando o ANR do pacote exato `com.google.android.apps.nexuslauncher`, e `mFocusedApp` pertencente à Activity `NexusLauncherActivity` daquele pacote. O resultado é limitado a 4 KiB e qualquer erro na leitura impede a recuperação.

**Ainda é obrigatório**: o node Accessibility não pode indicar ANR do próprio aplicativo; deve haver **exatamente um botão do Android** com id `android:id/aerr_close` e clicável. Só esse controle pode ser pressionado uma vez. Depois disso, o código continua exigindo **foco real, janela pertencente ao app, pixels sem overlay, screenshot íntegro e 14 capturas por API**. Não há retry de instrumentação, nem `am force-stop` ou fechamento de outros aplicativos.

A regressão Android original (incluída nos 154 testes/API) ganhou asserts com o diagnóstico real e casos negativos de ANR do próprio app, modal desconhecido, app focado errado e foco sem evidência. O contrato Python passa a exigir esse fallback estritamente limitado.

**Estado:** código preparado para validação na PR; não equivale a sucesso da API35 até nova matriz completa (154 testes/API, 14 PNGs/API e cross 28/28). Não autoriza merge, OTA, APK ou aceite 1:1/telefone físico.
