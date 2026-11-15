# P7.31 — Padrão, Compacto e Moderno: miniaturas fiéis à densidade real

## Base revisada

A [P7.30 / CI #40063949424](https://github.com/nego001/ReaDroid-Native/actions/runs/40063949424) passou em Android 10/API29, Android 15/API35, auditoria cruzada, Source checks e OTA. As capturas reais mostraram as miniaturas de Temas enriquecidas com chrome de aplicativo, sem quebrar as quatro abas, as áreas de toque ou a versão compacta.

Na mesma captura de Design Studio, as miniaturas **Padrão / Compacto / Moderno** continuavam muito parecidas, embora o catálogo real aplique:
- `P7VisualCatalog.quickActionRowSizes(0/1/2) = [3,3]`: os seis comandos permanecem na mesma ordem e geometria 3×2;
- `persistLayout(..., 1)` define `compact=true`, `card_radius=12`;
- `persistLayout(..., 2)` define `compact=false`, `card_radius=26`;
- `persistLayout(..., 0)` define `compact=false`, `card_radius=18`.

Por isso, **não** desenhar três organizações de botões inexistentes. As diferenças devem comunicar densidade/respiração e arredondamento.

## Alteração aplicada

- `P7ThemePreviewView.drawPrimaryLayout()` desenha um mesmo painel de aplicativo nativo para os layouts `0`, `1` e `2`, buscando a distribuição real em `P7VisualCatalog.quickActionRowSizes(themeSurface)`.
- **Padrão:** duas linhas de três cartões com raio e espaçamento intermediários; uma linha ilustrativa inferior.
- **Compacto:** raio menor, lacunas menores, cartões um pouco mais baixos e mais duas linhas ilustrativas dentro do mesmo viewport.
- **Moderno:** raio maior e espaço entre cartões, com menos densidade no mesmo viewport.
- Acento usa a cor real recebida pelo preview. Todos os elementos são desenhados com `Canvas/Paint` local, sem imagem externa, novos dados do usuário nem downloads. Miniaturas de layouts `3..11` e os dois outros modos (Temas e Presets) não são alterados.
- `P7VisualCatalogInstrumentedTest.primaryLayoutMiniaturesReflectRealDensityAndRadius`: valida as **três distribuições [3,3]**, a distinção pixel a pixel entre as imagens e a posição antecipada do primeiro cartão no modo Compacto, sem exigir um layout fictício.

## Gates pendentes na P7.31

- [ ] Source checks / OTA no HEAD desta mudança.
- [ ] Android 10/API29 e Android 15/API35, com novo teste e toda a suíte anterior.
- [ ] Captura sintética, restauração de debug APK e inventário **14 PNGs/API**, auditoria cruzada **28/28**.
- [ ] Verificar `p7-design-android-{29,35}.png`: três miniaturas distintas, sem cortes, etiquetas intactas, prévias ilustrativas sem valores de dados falsos.
- [ ] Conferir 320dp/130%, fonte 200% e TalkBack no Galaxy A55 físico.

A PR #13 continua **draft**, sem merge em main, APK de distribuição nem OTA. `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
