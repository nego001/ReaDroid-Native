# P7.30 — Miniaturas de temas com aparência de aplicativo

## Base validada

A execução [P7.29.2 #40063237001](https://github.com/nego001/ReaDroid-Native/actions/runs/40063237001) encerrou com `success` em Source checks, OTA manifest, Android 10/API29, Android 15/API35 e revisão visual cruzada. As capturas de cada sistema geraram **14 PNGs reais** e a auditoria cruzada validou 28/28. A ordem agora é captura do Explorador sintético antes da suíte instrumentada, seguida da reinstalação do debug APK para os demais smokes.

O recorte `negrecodroid_controle_total_de_apks.png` mostra miniaturas visuais de temas com detalhes internos de uma tela de aplicativo, enquanto as `p7-design-android-29.png` / `-35.png` atuais usam blocos estilizados bastante esquemáticos. As miniaturas são **representações gráficas**, não screenshots de APKs do usuário.

## Alteração P7.30

- `P7ThemePreviewView.drawThemeChrome()` adiciona detalhes **vetoriais desenhados no Canvas Android**: barra superior, marca minimalista, ícones/status, traços de títulos e cartões, linhas de conteúdo e três marcadores de navegação inferior. Conserva os dois cartões e as linhas já existentes.
- Todos os elementos usam os tokens reais do preview (`background`, `surface`, `border`, `line`, `accent`). Os temas OLED, grafite e claro permanecem distintos, sem desenhar uma prévia escura indevida no tema claro.
- Reutiliza o `Paint` existente, sem alocações adicionais em cada `onDraw`, sem downloads, fontes externas, imagens com copyright ou dependência de rede.
- Os pequenos traços de texto e cartões são **ilustrativos**, sem simular número de arquivos, projeto importado, análise, segurança ou identidade real do usuário. O texto verdadeiro dos cartões, suas descrições para TalkBack e callbacks de escolha continuam intactos.
- `P7ThemeCatalogInstrumentedTest.miniatureThemeChromeUsesActualSurfacePalette` desenha as três variantes em bitmaps Android e exige cores de chrome e accent verificadas nos pixels, além de provar que as variantes não são idênticas.
- Testes de diferenciação `neon`/limpo, superfícies corretas e demais prévias de layout e presets permanecem ativos. Nenhum modo de layout (`mode=1`) nem preset (`mode=2`) foi alterado.

## Gates de verificação

- [ ] Source checks e OTA no HEAD P7.30.
- [ ] Android 10/API29 e Android 15/API35 com a nova instrumentação, a captura sintética isolada, demais smokes e 14 PNGs por API.
- [ ] Nova revisão visual cruzada 28/28 e comparação de `p7-design-android-29.png`/`-35.png` com o recorte de referência, conferindo miniaturas no tamanho real e sem artefatos gráficos.
- [ ] Confirmar que 320dp/130% e fonte 200% não perdem ações, seleção nem rótulos.
- [ ] Revisão visual humana e homologação física Galaxy A55 com TalkBack.

**Restrições:** PR #13 segue draft; `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`; sem merge em main, APK distribuído, assinatura nova, OTA, alteração de arquivos pessoais, REA ou leitura distribuída.
