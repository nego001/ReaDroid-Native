# P7.50 — Isolar a regressão completa da prévia de logotipo em 135%

## Evidência
A API35 perdeu o emulador duas vezes em execuções anteriores, com o último método nomeado `logoPreviewAnnouncesSavedNameAndSubtitleWithoutDuplicateNodes`, incluindo a P7.48.1 [workflow #40159722827](https://github.com/nego001/ReaDroid-Native/actions/runs/40159722827) tentativa 1. O log traz `device 'emulator-5554' not found`, portanto **não permite atribuir um defeito de produto a esse método**. A execução da API29/35 e auditoria devem aprovar integralmente a etapa anterior antes de esta ser integrada.

## Ajuste de estabilidade com cobertura intacta
O método **idêntico e completo** sai de `P7NavigationInstrumentedTest` para uma classe instrumentada separada `P7LogoIdentityLargeFontInstrumentedTest`. Toda asserção segue presente: Activity real, `display_name`, `display_subtitle`, fonte 135%, descrição acessível única sem botões duplicados, conteúdo exato do texto, altura natural, ausência de limite de linhas e restauração de preferências e tema no `finally`. Helpers antes privados (`describedView`/`clickableText`) passam a package-private **apenas no código de teste**, sem alterar os métodos.

A matriz passa a exigir **7 sessões de Gradle e 26 seletores únicos**. A contagem continua exatamente **166 testes/API** (`1+1+1+1+1+45+116`), preservando também o teste de Android Back das três confirmações e a guarda única de P7.49. Contratos Python verificam transferência única e todos os checks essenciais, sem marcar métodos como skipped ou adicionar retry automático. Permanecem todos os 14 PNG/API, cross 28, reboot, viewport, fontes, Source/OTA e gates fail-closed.

**Status:** preparado somente em branch staging, nenhum resultado de CI para esta alteração e nenhuma aprovação visual/física. PR #13 draft; `main` inalterada; sem distribuição APK/OTA.
