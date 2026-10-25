# P7.25 — Design Studio: ícones vetoriais reais nos cartões de criadores

**Branch:** `feature/p7-negrecodroid-visual-foundation` · **PR:** #13 · **Base:** duas referências PNG oficiais, SHA-256 conferido na P7.20.

## Discrepância concreta

Na captura real `p7-design-android-35.png` da base anterior, os cartões `Criador de Ícones` e `Logo Studio` tinham símbolos genéricos **`◉` e `N`**. A arte oficial usa uma ferramenta gráfica e o monograma azul/ciano, não apenas caracteres tipográficos. Isso reduz fidelidade da composição e pode variar com a fonte do SO.

## Mudança aplicada

- Adicionado `app/src/main/res/drawable/ic_p7_icon_creator.xml`: novo **VectorDrawable 48×48dp** com borda azul, traços de ferramenta e pincel inclinado. Asset local, sem download nem execução externa.
- `P7DesignStudio.creatorRow` passa a declarar recursos de imagem reais: `ic_p7_icon_creator` para o primeiro criador, **`ic_negrecodroid_foreground`** (marca vetorial oficial já presente no projeto) para o segundo.
- `P7DesignStudio.creator` passou a usar `ImageView` de 42×42dp, `FIT_CENTER`, sem descrição acessível duplicada (o cartão de ação já expõe a descrição e o papel Button).
- Mantidos título, subtítulo, alinhamento, dimensões mínimas (88dp), dois cartões lado a lado em escala normal, empilhamento em larguras/fonte grandes, callbacks `-4/-5` para abrir ferramentas verdadeiras e exportação consentida via SAF.
- `P7NavigationInstrumentedTest.creatorCardsUseRealVectorArtworkInsteadOfTextSymbols`: abre a aba Design real, confere os **dois `ImageView` carregados**, recursos esperados, 42dp, semântica decorativa e cartões acionáveis.
- A mudança é **de desenho e regressão visual**, não ativa novas funcionalidades de edição ou altera os APKs do usuário.

## Verificações e limites

- [ ] Source checks + OTA na última revisão.
- [ ] Testes instrumentados Android 10/API29 e Android 15/API35 em **HEAD contendo a P7.25**.
- [ ] Captura nova de `p7-design-android-{29,35}.png` e comparação dos dois cartões com o recorte direito da arte oficial; não inferir resultado de capturas anteriores.
- [ ] Conferir nome completo, contraste no tema claro, 320dp/130%, fonte 200% e TalkBack manual.
- [ ] Homologação visual 1:1 e Galaxy A55 físico permanecem dependentes de revisão humana do proprietário.

**Não declarar** `visual_1to1=APPROVED` ou `physical=APPROVED` apenas por CI verde. Não fazer merge na `main`, não gerar instalador por mudança pequena, não modificar `versionCode` e não publicar OTA. O REA e a leitura cooperativa são backlog separado.
