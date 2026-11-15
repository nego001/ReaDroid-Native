# P7.28 — Design Studio: navegação superior em barra contínua

## Evidência utilizada

A matriz [P7.27.1 #40058495411](https://github.com/nego001/ReaDroid-Native/actions/runs/40058495411) concluiu com sucesso nos jobs Android 10/API29, Android 15/API35 e auditoria visual cruzada; Source checks e OTA também aprovaram o commit `478475ec44d71d0c7b118648ba616d4b7d50ba24`.

Foi inspecionada a captura **real** `p7-design-android-35.png` da P7.27.1 e comparada ao recorte da referência oficial `negrecodroid_controle_total_de_apks.png`. O Design Studio já exibe o monograma N e as duas setas circulares nativas corretamente, mas as quatro abas **Temas / Layout / Ícones / Logotipo** apareciam como quatro cartões grandes e separados. A referência tem uma faixa contínua segmentada, com divisões discretas e destaque azul da aba ativa.

## Alteração visual isolada

- `P7DesignStudio`: o `LinearLayout` horizontal das abas agora tem **um fundo compartilhado**, com borda e cantos arredondados, sem margem direita entre botões. A aba selecionada mantém seu fundo e contorno azuis; as demais usam preenchimento transparente sobre a mesma faixa.
- As quatro abas continuam sendo `TextView` clicáveis individuais, com os **mesmos rótulos completos**, `contentDescription`, `AccessibilityNodeInfo` com papel `Button`, mínimo de **48dp** e `activeTab` restaurado na rotação.
- Permanece o `HorizontalScrollView`, o controle de paginação quando necessário, o ajuste compacto de 320dp/130% e a opção para fonte 200%. Nenhum callback ou editor foi modificado.
- `P7NavigationInstrumentedTest.designTabsShareOneRailWithoutGapsOrLostActions`: abre Design real, exige o contêiner único com quatro botões, margem zero entre eles, preenchimento transparente nas abas inativas, superfície compartilhada, alvo mínimo 48dp e alternância Temas→Layout→Ícones→Logotipo→Temas com seleção nativa e nome acessível corretos.

## Verificação pendente no novo HEAD

- [ ] Source checks e OTA manifest aprovados no HEAD P7.28.
- [ ] Android 10/API29 e Android 15/API35 aprovados, com regressões e **14 capturas por API**.
- [ ] Comparação das capturas reais `p7-design-android-{29,35}.png` à referência, sobretudo largura e alinhamento da faixa superior.
- [ ] Revisão nas capturas `p7-compact-design-android-{29,35}.png` e `p7-large-text-design-android-{29,35}.png` para impedir nomes cortados, seleção inacessível ou paginação quebrada.
- [ ] Teste físico Galaxy A55/TalkBack e aceite humano antes de `visual_1to1=APPROVED`.

**Fronteira de escopo:** P7 visual apenas. Não modifica arquivos de APK, índice, SAF, plano de edição, publicação, launcher, exportadores, versão, assinatura ou OTA. REA/leitores cooperativos seguem backlog. PR #13 permanece rascunho; `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
