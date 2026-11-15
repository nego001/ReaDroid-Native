# P7.34 — Seleção de preset não significa que ele foi aplicado

## Evidência e problema real

A P7.33 está aprovada em [GitHub Actions #40065954124](https://github.com/nego001/ReaDroid-Native/actions/runs/40065954124): Android 10/API29, Android 15/API35, revisão cruzada, Source e OTA. O cartão de preset já anuncia opções concretas e a confirmação `Aplicar?` explica os valores que serão persistidos.

Ao tocar em um preset **diferente do salvo**, porém, `P7DesignStudio.tile()` desenhava imediatamente o símbolo `✓` em sua miniatura porque usava `selectedPreset == i`, antes de qualquer confirmação. Isso podia sugerir que a mudança já havia sido gravada. `Cancelar` e Android Back restauram o estado, mas o indicador provisório era enganoso.

## Mudança P7.34

- `P7DesignStudio` separa `selected` (destaque transitório antes de confirmar) de `appliedPreset`, obtido por `P7VisualCatalog.currentPreset(activity)`, que já valida **todos** os valores realmente persistidos, incluindo tema, acento, glow, raio, layout e densidade.
- A marca `✓` de um cartão **preset** representa exclusivamente o preset efetivamente aplicado. O cartão pendente mantém seleção/realce de navegação, mas **não ganha a marca de aplicado**.
- O TalkBack diferencia estados: `preset aplicado`, `prévia escolhida, ainda não aplicada` e `selecionar prévia`, incluindo o resumo verdadeiro da P7.33. Temas e layouts preservam a semântica anterior.
- `P7NavigationInstrumentedTest.presetAppliedIndicatorTracksCommittedValuesOnly` verifica os três estados, consulta os cinco cartões nativos da Home/Design Studio, confirma que apenas o preset realmente persistido mostra a marca e exige o papel de botão com o resumo.
- Continua obrigatório confirmar para chamar `P7VisualCatalog.applyPreset`; `Cancelar`, Back, persistência, APKs, SAF, assinatura e versão **não foram modificados**.

## Gates

- [ ] Source checks e OTA no HEAD P7.34.
- [ ] Android 10/API29 e 15/API35 com toda a instrumentação, captura isolada do Explorador antes da suíte e reinstalação debug para os smokes.
- [ ] Evidências **14 PNGs por API** e auditoria cruzada **28/28**; inspecionar Miniaturas/Temas e fonte ampliada.
- [ ] Testar manualmente escolher, cancelar e aplicar um preset com TalkBack no Galaxy A55.
- [ ] Inspeção/aceite visual 1:1 humano permanecem separados da CI.

**Não fazer merge na main ou publicar APK/OTA antes de homologar.** PR #13 permanece draft com `visual_1to1=NOT_APPROVED` e `physical=NOT_APPROVED`.
