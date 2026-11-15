# P7.29.1 — Captura sintética isolada antes da suíte longa

## Evidência concreta

No commit da P7.29 `380153474a3ca323025d31998e207e63c97e8d34`, a [CI #40061592004](https://github.com/nego001/ReaDroid-Native/actions/runs/40061592004) concluiu:
- **Android 10/API29: success**, incluindo as capturas do Design Studio normal e compacto. Conferência visual direta: os quatro vetores `Temas / Layout / Ícones / Logotipo` estão visíveis no viewport normal, enquanto na versão 320dp/130% aparecem apenas os quatro rótulos completos. 
- **Android 15/API35: failure**, **depois de 145 testes instrumentados passarem sem falha**. O método isolado `P7ExplorerPopulatedCaptureInstrumentedTest#captureRealActivityWithIndexedSyntheticApk` foi executado após toda a suíte Gradle e falhou em `assertExplorerWindowInForeground` porque a Activity não recuperou foco. Não houve aprovação automática de PNG nem foi removida qualquer proteção de modal. A auditoria cruzada ficou `skipped`.
- Source checks e OTA passaram; isso não substitui Android 15 nem aprovação visual 1:1.

O problema é **a posição da captura no workflow e uma disputa de foco após a longa suíte**; o log isolado não demonstra qual aplicativo segurava o foco. A tentativa anterior de recuperação só fecha um diálogo identificado com exatidão como ANR do Pixel Launcher, sem presumir que qualquer perda de foco seja ANR. As verificações continuam válidas.

## Reordenação fail-closed

Em `.github/workflows/p7-brand-validation.yml`, a execução por emulador passa a:
1. Inicializar o emulador e compilar os dois APKs de debug com `gradle --no-daemon :app:assembleDebug :app:assembleDebugAndroidTest`.
2. Executar **uma única vez** `bash tools/p7_capture_populated.sh <api>` com o Android recém-iniciado: reinstala os dois APKs, roda o método isolado com ZIP sintético e requer sucesso, foco real, ausência de modal indevido, PNG íntegro e hash; exporta o arquivo PNG para o filesystem do runner.
3. Executar os testes gerais `gradle --no-daemon :app:connectedDebugAndroidTest` mantendo o filtro que inclui a regressão de modal mas não repete o método exportador.
4. Só após ambas as etapas aprovadas, executar os smokes reais, screenshot inventory, comparativo por API e relatório cruzado. A reinstalação pelo Gradle não altera a captura já copiada para o runner.

`tests/test_p7_capture_runner.py` garante programaticamente a ordem **compile → capture → general instrumentation** e que o método de exportação seja chamado uma vez pelo shell. Outros contratos de captura existentes continuam exercitados.

## Validação exigida

- [ ] Source checks e OTA no HEAD P7.29.1.
- [ ] API29 + API35 com a captura sintética **aprovada antes** dos testes gerais e a suíte instrumentada completa, sem diminuir nenhum assert.
- [ ] Inventário de 14 PNGs por API e auditoria cruzada 28/28.
- [ ] Conferir os vetores das abas nas novas capturas reais e o comportamento 320dp/130% e fonte 200%.
- [ ] Revisão humana de fidelidade visual e ensaio físico Galaxy A55/TalkBack.

Esta alteração **não modifica** UI de produção, SAF, projetos, APK original, assinatura, versão, publicação ou OTA. Não homologar nem fazer merge na `main` com base em CI parcial. PR #13 permanece draft e os gates `visual_1to1=NOT_APPROVED` / `physical=NOT_APPROVED` continuam ativos.
