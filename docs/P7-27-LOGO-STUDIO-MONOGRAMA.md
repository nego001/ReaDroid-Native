# P7.27 — Logo Studio: monograma vetorial próprio, sem alterar o ícone instalado

## Evidência e decisão

A P7.26 concluiu com **success** em [GitHub Actions #40053245551](https://github.com/nego001/ReaDroid-Native/actions/runs/40053245551): instrumentação Android 10/API29 e 15/API35, auditoria visual cruzada, Source checks e validação de OTA. A captura real `p7-design-android-35.png` confirmou os dois indicadores circulares azuis sem comprometer o funcionamento dos cartões.

Restava uma discrepância concreta com o recorte direito do PNG oficial `negrecodroid_controle_total_de_apks.png`: a peça gráfica do cartão **Logo Studio** é um **N solto azul/ciano, prata e violeta**, com fita angular e sombra. A P7.25 havia usado `ic_negrecodroid_foreground.xml`, que é o **escudo de lançamento** da marca. Esse escudo é adequado para o app, mas não reproduz a miniatura do cartão oficial.

## Alteração estritamente visual

- Novo `ic_p7_logo_studio_monogram.xml`: `VectorDrawable` nativo (48dp), com pernas diagonais independentes, camadas em azul/ciano, prata e violeta, sem fontes externas, imagens de rede ou bitmap carregado.
- `P7DesignStudio.creatorRow()` passa a usar **esse novo vetor apenas no cartão Logo Studio**, mantendo `ic_p7_icon_creator` para o Criador de Ícones e as setas vetoriais decorativas introduzidas na P7.26.
- **Não** altera `ic_negrecodroid_foreground.xml`, tema, marca instalada, logotipo salvo, exportação PNG/SVG, app icon do APK de terceiros, estado, SAF ou assinatura.
- O cartão continua sendo botão único com callback do editor real, descrição acessível e alvo de toque existente; o vetor continua decorativo, sem foco nem evento.
- O teste `P7NavigationInstrumentedTest.creatorCardsUseRealVectorArtworkInsteadOfTextSymbols` verifica o drawable separado do escudo do app e mantém os testes de setas, layout, tamanho, acessibilidade e clique.

## Verificação necessária

- [ ] Source checks e OTA manifest no HEAD da P7.27.
- [ ] Matriz Android API29/35 (instrumentação e novas capturas).
- [ ] Comparar `p7-design-android-29.png` / `-35.png` com o recorte oficial, verificando cor, proporção, contraste, posição do N e setas.
- [ ] 320dp/130% e fonte 200% continuam legíveis, com títulos completos e botões acessíveis.
- [ ] Homologação humana 1:1 e física Galaxy A55/TalkBack permanecem pendentes.

**Gates:** `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`. PR #13 continua `draft`. Não fazer merge na main, nova versão, APK distribuível nem OTA.
