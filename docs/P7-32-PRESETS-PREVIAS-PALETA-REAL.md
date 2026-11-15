# P7.32 — Prévia dos presets com paleta e acabamento realmente aplicados

## Base e evidência

No commit `7d94537ae3a32c96bdebf3bfed168bc6d65186bf`, a P7.31 concluiu [CI #40064570113](https://github.com/nego001/ReaDroid-Native/actions/runs/40064570113) com **success** em Android 10/API29, Android 15/API35, auditoria cruzada de 28 capturas, Source checks e OTA. A captura real do Design Studio confirmou que Padrão, Compacto e Moderno agora têm miniaturas distintas, sem falsificar a organização [3,3] dos comandos.

Entretanto, os cinco presets de `P7DesignStudio` tinham um vetor de cores **puramente decorativo** e independente da persistência real: Retro aparecia rosa embora salvasse `accent=orange`; Glass aparecia ciano embora salvasse `accent=blue`; Minimal usava uma mistura azul/cinza mas salva `theme=light`. Sua prévia não comunicava corretamente a opção que será aplicada.

## Correção P7.32

- `P7VisualCatalog` expõe métodos **somente de leitura, internos ao pacote** para consultar `presetAccentColor`, `presetBackgroundColor`, `presetCardColor`, `presetCornerRadius` e `presetGlow` a partir dos mesmos arrays privados usados por `persistPreset`, com índice inválido rejeitado. Nenhuma mudança na persistência.
- `P7DesignStudio` elimina as cores e nomes duplicados dos cinco presets. Utiliza `P7VisualCatalog.PRESET_NAMES[i]`, a cor persistida, o índice do preset e a flag de glow para construir o tile e a miniatura.
- `P7ThemePreviewView` mantém o `LinearGradient` **cacheado por instância** (sem recriar shaders no `onDraw`), agora calculado com fundo, acento e superfície verdadeiros. A miniatura desenha fundo/área interna e linhas ilustrativas usando OLED, grafite ou tema claro, raio do preset e stroke de glow somente quando definido. Não anuncia nem inventa conteúdo real de APKs, projetos ou verificações.
- Configurações efetivas (somente exibição): Dark OLED = OLED/azul/sem glow/raio 18; Cyber Neon = OLED/roxo/glow/raio 26; Minimal = claro/azul/sem glow/raio 12; Glass = grafite/azul/glow/raio 26; Retro = OLED/laranja/sem glow/raio 12.
- `P7VisualCatalogInstrumentedTest.presetThumbnailsMatchPersistedThemeAndAccentTokens` verifica as cinco combinações, desenha cada preview no Canvas Android, exige pixels de fundo correspondentes e diferenciação visível entre as famílias. Preserva testes existentes de shader, catálogos, persistência, paletas e demais telas.

## Gates da etapa

- [ ] Source e OTA no HEAD P7.32.
- [ ] Instrumentação Android 10/API29 e 15/API35, incluindo novo teste e captura isolada do Explorador, seguida de reinstalação do mesmo APK debug para smokes.
- [ ] Capturas reais **14 por API** e auditoria cruzada **28/28**; revisar `p7-design-android-{29,35}.png` para confirmar Minimal claro, Glass grafite/azul e Retro laranja.
- [ ] Conferir 320dp/130%, fonte 200%, nomes completos, seleção e foco de TalkBack.
- [ ] Homologação humana de fidelidade visual 1:1 e validação no Galaxy A55 continuam pendentes.

**Escopo estrito:** não alterar semântica de presets, editores, build APK, assinatura, SAF, projetos, versão, main, publicação OTA ou integração REA. PR #13 draft. `visual_1to1=NOT_APPROVED`; `physical=NOT_APPROVED`.
