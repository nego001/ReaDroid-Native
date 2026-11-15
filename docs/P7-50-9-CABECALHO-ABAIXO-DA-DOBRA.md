# P7.50.9 — título de personalização legado sem recorte na primeira dobra

## Referência e evidência (25/10/2026)

A captura Android 15 genuína `p7-design-android-35.png` do [run P7.50.8.1 #40217797249](https://github.com/nego001/ReaDroid-Native/actions/runs/40217797249), artefato `p7-brand-android-35` ID `12608980144`, mostra **Dark OLED, Cyber Neon, Minimal, Glass e Retro** completamente acima da barra inferior, satisfazendo `P7_PRESET_LABELS_VISIBLE_PASS`. Contudo, o heading **“Personalização existente”** começa a aparecer cortado atrás da barra de navegação no primeiro viewport. A referência oficial `design/reference/p7/negrecodroid_controle_total_de_apks.png` termina esse painel nos cinco presets. Isso é diferença visual genuína, não erro do gate de legendas.

## Ajuste mínimo e seguro

- Somente no **primeiro tab Temas** e no viewport **390–419dp com fonte efetiva <=115%**, insere **26dp de respiro vertical nativo** *após os presets* e *antes* de “Personalização existente”. Assim o título não aparece parcialmente por trás da barra no primeiro viewport.
- A seção **continua verdadeira, rolável e acessível**. As três ações existentes `Cores e tons`, `Exportar aparência` e `Importar aparência` conservam callbacks e preferências; nenhum `View.GONE`, clip artificial, screenshot sobreposto ou ícone fake é usado.
- Nas outras três abas, Android compacto 320dp, texto 130% e 200%, tablets e outras proporções, a separação continua 0dp, para não alterar o design acessível já aprovado.
- O spacer é `View` não-focável, oculto apenas da acessibilidade como decoração. Não interfere em tema, APK, planos de edição, assinatura, SAF ou Keystore.

## Gate de falha real

`tools/p7_design_smoke.py` acrescenta `require_unclipped_followup_heading(nodes, current)` no viewport normal: obtém da árvore Android o retângulo do heading `Personalização existente` quando visível e o limite da barra inferior `Seção Design, selecionada`; falha se parte do título cruzar a borda da navegação. Ausência do texto apenas **na primeira dobra** é permitida, pois a seção fica abaixo e acessível por scroll. Unit tests negativos verificam heading parcialmente exposto, duplicado, bounds malformados e nav sem bounds. Outro contrato exige que o código Java continue contendo o heading e seus três cartões reais.

Teste Android já existente `catalogHeadingLayoutPolicyHandlesNarrowAndLargeText` passa a verificar a política dos 26dp com regressões 320dp, fonte ampliada, tablet e outras abas. **Nenhum novo `@Test` é criado**, mantendo o total de **170 por API** (6 isolados +47 navegação +117 restantes). Meta permanece API29/35, 14 PNG/API e cross 28/28; compact 320dp/130%, texto 200%, reboot API35 e Source/OTA sem falhas.

**Estado inicial:** staging sobre P7.50.8.1 integralmente verde no commit `c73cae4c`. Só aprovar P7.50.9 após evidências reais nos dois emuladores e auditoria cruzada no SHA exato. Revisão visual humana 1:1 e Galaxy A55 físico/TalkBack ainda são pendentes. PR #13 em rascunho, main intacta, sem publicar APK/OTA.
