# P7.21 — Explorador: linhas contínuas com divisórias finas

## Evidência concreta examinada

A base anterior à alteração foi o commit `21af94019ba4ea5750dfd1a157a0dcc7022fab1b`: workflows [P7 Android 10/15](https://github.com/nego001/ReaDroid-Native/actions/runs/40043124053), Source e OTA com conclusão **success**. O artefato Android 15 continha **141 testes gerais, 0 falhas**, além da captura isolada executada pelo workflow. Os artefatos da matriz continham 14 imagens por API e o painel cruzado, com `official_references=VERIFIED` e **nenhum aceite 1:1**.

A imagem real `p7-explorer-populated-android-35.png` do mesmo workflow (APK **sintético** de QA) mostra `assets/`, `lib/`, `res/`, `AndroidManifest.xml` e `classes.dex` em **retângulos fechados individualmente**. Na referência exata `negrecodroid_controle_total_de_apks.png`, o telefone central usa **lista contínua de itens separados por divisórias horizontais discretas**. Não é uma questão de conteúdo real ou de índice: trata-se de desenho da linha nativa.

## Mudança implementada na branch P7

- `P7ExplorerEntryRow`: troca cada `GradientDrawable` com contorno inteiro e raio 4dp por `LayerDrawable` com cor de fundo existente e um separador de **1dp somente na borda inferior**.
- Remove apenas a margem inferior de **2dp** entre linhas, preservando o layout horizontal, glyphs reais, nome/descrição, largura e barra de opções separada.
- Mantém a altura mínima de **58dp** e o alvo de toque do botão de opções em **48×48dp**, descrição de acessibilidade, callback de abrir, menu, seleção e informações reais.
- `P7ExplorerEntryRowInstrumentedTest`: estende o teste real de linhas para garantir composição em duas camadas, cor do separador, alinhamento inferior, espessura, ausência de lacuna entre itens e alvos de toque.
- Não altera `ApkDiskIndex`, busca, filtros, paginação, SAF, reconstrução, recuperação ou dados do APK.

## Critérios de validação pendentes

- [ ] Compilar e passar Source checks, OTA e testes Android 10/API29 e Android 15/API35 **no HEAD que contém esta mudança**.
- [ ] Verificar novamente `p7-explorer-populated-android-29.png` e `-35.png`: linhas contínuas, divisórias só na base, sem perda de nomes ou botões.
- [ ] Comparar com o recorte do Explorador na arte oficial, documentando diferenças de altura, cor, iconografia, busca e densidade.
- [ ] Conferir o Explorador vazio, 320dp/130% e 200% de fonte, além de testar TalkBack manualmente.
- [ ] Homologar no Galaxy A55 e receber aceite explícito do proprietário antes de declarar 1:1.

**Não aprovado automaticamente:** screenshots antigos não comprovam a mudança; CI verde tampouco prova fidelidade ao mockup. `visual_1to1=NOT_APPROVED` e `physical=NOT_APPROVED`. PR #13 continua **draft**, sem merge na `main`, APK de distribuição, incremento de versão ou OTA.
