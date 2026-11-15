# P7.26 — Indicadores de ação nos cartões do Design Studio

## Base efetivamente aprovada

A P7.25.1, commit `70c33680bd106e9cd9f6d87f8446446be5882c85`, concluiu [a matriz Android 10/API29 e 15/API35](https://github.com/nego001/ReaDroid-Native/actions/runs/40052588597) com **sucesso**. O Android 10 registrou **143/143 testes instrumentados**, o Android 15 também concluiu com sucesso, e a auditoria cruzada fechou verde. A referência P7 de dois PNGs permanece verificada; `visual_1to1=NOT_APPROVED` e `physical=NOT_APPROVED`.

A captura real atualizada `p7-design-android-35.png` confirmou que o novo ícone nativo do Criador de Ícones e o escudo do Logo Studio, introduzidos na P7.25, renderizam. Ao comparar a região dos criadores com o recorte direito da arte oficial, faltavam os **pequenos círculos azuis com seta na extremidade direita** de cada cartão.

## Correção P7.26

- Novo `app/src/main/res/drawable/ic_p7_creator_arrow.xml`: indicador circular azul com seta diagonal clara, em `VectorDrawable` nativo 24×24dp, escalado para 22×22dp.
- `P7DesignStudio.creator()`: o indicador fica depois do texto, alinhado à base do cartão, com pequena margem de 2dp.
- A seta é **exclusivamente decorativa** (`importantForAccessibility=NO`, `clickable=false`, `focusable=false`); o cartão inteiro continua sendo o **único botão**, com descrição completa, atalho de teclado e callbacks existentes para abrir os editores reais.
- Sem alterar parâmetros de exportação PNG/SVG, histórico, nomes, SAF, assinatura, APK original, seleção de temas, versão ou OTA.
- `P7NavigationInstrumentedTest.creatorCardsUseRealVectorArtworkInsteadOfTextSymbols` foi ampliado para verificar ambos os indicadores, recursos carregados, dimensões de 22dp, alinhamento inferior, foco não duplicado e ação preservada.

## Critérios de validação

- [ ] Source checks e validação OTA no HEAD que contém a P7.26.
- [ ] Instrumentação Android API29 e API35 verde no mesmo SHA, 14 capturas reais por API e painel cruzado 28/28.
- [ ] Inspeção de `p7-design-android-{29,35}.png`: as setas devem aparecer **nos dois cartões**, sem truncar nomes e descrições nem esmagar as miniaturas.
- [ ] Inspeção de 320dp/130% e 200%: manter cards alcançáveis e texto legível; não reduzir alvo mínimo dos botões.
- [ ] TalkBack físico no Galaxy A55 e revisão humana da arte aprovada antes de homologar fidelidade 1:1.

A PR #13 segue **draft**. Sem merge na main, APK de distribuição ou atualização OTA. A integração REA e leitura distribuída continua em issue separada para fase futura.
