# P7.35.5 — Inspecionar diálogo nativo pelo Studio sem depender do UiAutomation

## Evidência
A [CI P7.35.4 #40071164210](https://github.com/nego001/ReaDroid-Native/actions/runs/40071164210) registrou no Android 15 falha antes de KEYCODE_BACK: `UiAutomation.getRootInActiveWindow()` não retornou um nó, gerando `Native confirmation must own active window before Back: Aplicar Retro?`. Isso **não comprova** que o AlertDialog não existia. A classe de navegação continuou e posteriormente registrou falha em outro teste, podendo haver interferência do diálogo que o teste anterior deixou aberto. Outras causas da instabilidade API35 permanecem possíveis.

## Mudança testável
- `P7DesignStudio` mantém referência **por instância** ao AlertDialog de preset (sem singleton, sem chave persistida, sem arquivo) e a limpa em `setOnDismissListener`. Impede múltiplas confirmações empilhadas enquanto a primeira está visível.
- O teste usa reflexão somente em `MainActivity.designStudio`, dentro do mesmo APK de instrumentação, e obtém `studio.activePresetConfirmation()`. Exige diálogo nativo visível e botão **Cancelar** real, sem depender de árvore de acessibilidade nula no CI.
- A tecla Back continua sendo enviada pela `Instrumentation` (não substituída por `dialog.cancel()`). Após o evento e `waitForIdleSync()`, exige que o diálogo esteja **realmente fechado**, que o cartão volte a `selecionar prévia` e que o mapa completo de `SharedPreferences` seja idêntico ao original.
- A instrumentação limpa o diálogo no `finally` **somente se uma falha deixou a janela aberta**, para que outras verificações não sejam contaminadas. Essa limpeza não permite aprovar as asserções falhas.
- O app continua chamando `P7VisualCatalog.applyPreset` somente ao clicar **Aplicar**. O novo campo não muda o conteúdo persistido e serve também para prevenir confirmação duplicada.

## Gates
- [ ] Source checks e OTA no novo commit.
- [ ] Navegação API29/35 completa com teste Back e comparação integral das preferências.
- [ ] Segunda sessão obrigatória (20 seleções), 14 PNG por API e cross-review 28/28.
- [ ] Revisão do comportamento real TalkBack/Galaxy A55 e fidelidade visual 1:1.

Não concluir que a ausência de nó `UiAutomation` seja bug do app. PR #13 segue draft, sem merge, APK distribuído ou OTA publicada; `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
