# P7.29 — Ícones nativos nas quatro abas do Design Studio

## Base aprovada

[P7.28.1 CI #40060976452](https://github.com/nego001/ReaDroid-Native/actions/runs/40060976452) concluiu com **success** em Android 10/API29, Android 15/API35, auditoria visual cruzada, Source checks e OTA no SHA `3d6e76a0`. As capturas reais `p7-design-android-{29,35}.png` mostram a barra segmentada única, o destaque azul e os criadores com vetores. Em `p7-compact-design-android-29.png` os quatro rótulos permanecem visíveis na faixa estreita de 320dp/130%.

A referência original `negrecodroid_controle_total_de_apks.png` inclui pequenos símbolos à esquerda dos quatro títulos `Temas`, `Layout`, `Ícones`, `Logotipo`. A UI P7.28.1 ainda tinha apenas palavras.

## Mudança implementada

- Quatro recursos `VectorDrawable` nativos de **16dp**: `ic_p7_tab_temas.xml` (paleta), `ic_p7_tab_layout.xml` (grade 2×2), `ic_p7_tab_icones.xml` (ícone/estrela) e `ic_p7_tab_logotipo.xml` (N angular).
- `P7DesignStudio` mantém os quatro `TextView` como **únicos botões**, exibindo os símbolos como `compoundDrawableStart` decorativos nos layouts normais. Sem controles adicionais, texto duplicado, ações aninhadas ou acesso à rede.
- Seleção e mudança de tema atualizam o `ColorStateList` do drawable **com a mesma cor do texto**; acessibilidade continua anunciando os rótulos completos `<nome>, aba selecionada` ou `<nome>, selecionar aba`.
- `showTabGlyphs(widthDp, systemFont, appFont)` limita a exibição a **width >= 360dp e escala efetiva <= 1,20**, sem reduzir o tamanho das labels quando a tela tem 320dp/130%, a fonte está em 200% ou a ampliação do aplicativo está elevada. Nessas situações, os quatro botões e o controle de paginação continuam funcionando como antes.
- A barra segmentada P7.28, navegação com retorno exato a scrollX=0 da P7.28.1, contraste em tema claro, mínimo de 48dp por botão e responsividade existente permanecem.
- `P7NavigationInstrumentedTest` ganhou regressão para os limiares de largura/escala e expandiu `designTabsShareOneRailWithoutGapsOrLostActions` para conferir os símbolos, o rótulo único, a presença do drawable e a cor do ícone selecionado no componente Android real.

## Gates obrigatórios após esta alteração

- [ ] Source checks e OTA manifest no HEAD da P7.29.
- [ ] Android 10/API29 e Android 15/API35, com a nova suíte, screenshot inventory e comparativo cruzado de **28/28**.
- [ ] Inspecionar `p7-design-android-{29,35}.png`: símbolos aparecem nas quatro abas e o último botão não é cortado.
- [ ] Inspecionar `p7-compact-design-android-{29,35}.png` e `p7-large-text-design-android-{29,35}.png`: quatro rótulos legíveis, nenhum símbolo roubando espaço necessário, paginação e foco preservados.
- [ ] Testar TalkBack no Galaxy A55 real antes de aceitar conformidade física.

**Escopo:** P7 visual, sem alteração de APK, arquivo pessoal, SAF, builds, chaves, assinatura, versão, OTA, `main`, REA ou arquitetura de leitura distribuída. PR #13 permanece draft. `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`; CI verde não substitui homologação humana.
