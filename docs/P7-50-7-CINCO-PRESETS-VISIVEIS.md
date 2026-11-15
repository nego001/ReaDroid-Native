# P7.50.7 — cinco presets nativos na primeira faixa do Design Studio

## Desvio medido

Na imagem oficial `design/reference/p7/negrecodroid_controle_total_de_apks.png`, a faixa `Presets de Aparência` exibe cinco opções, **Dark OLED, Cyber Neon, Minimal, Glass, Retro**, lado a lado. Na screenshot Android real `p7-design-android-29.png` da P7.50.6, quatro opções aparecem e a quinta fica cortada à direita. A implementação anterior fixa cada preset a **71dp + 6dp** de espaçamento, ocupando 385dp para cinco itens, mais margens do conteúdo.

## Correção planejada e reversível

- `P7DesignStudio.presetCardWidthDp` usa **63dp** apenas no telefone de **390 a 599dp** em fonte efetiva até **115%**. Com cinco cartões, o total horizontal passa a 345dp (5 × 63dp + 5 × 6dp), comportando-se dentro da área útil do telefone referência.
- As miniaturas continuam sendo nativas (`P7ThemePreviewView`), com o estado aplicado consultado em `P7VisualCatalog`. Nomes podem ocupar até **duas linhas**, sem reticências para esta largura, mantendo os nomes do catálogo exatamente como salvos.
- Celulares abaixo de 390dp, tablets de 600dp+ e escalas acima de 115% continuam com **71dp ou 120dp** para preservar tamanho, legibilidade e rolagem horizontal.
- O tamanho mínimo do cartão continua acima de 48dp; nenhuma ação, preferência, cálculo de preset, tema, assinatura, arquivo APK ou SAF é modificado.

## Verificação obrigatória

`tools/p7_design_smoke.py` agora verifica **cinco itens reais** na árvore Android para o viewport de referência, todos com `content-desc` específico e `clickable=true`, largura mínima 48dp e retângulos não cortados/sem sobreposição, imprimindo `P7_FIVE_PRESETS_PASS` apenas em caso de êxito. `tests/test_p7_design_smoke.py` rejeita casos de card ausente, duplicado, cortado, estreito, fora de linha ou não acionável. O teste Java existente de política responsiva foi ampliado, sem acrescentar `@Test`.

A **meta total permanece em 170 testes instrumentados por API** (6 isolados + 47 de navegação + 117 restantes), Android 10 e 15, 14 screenshots/API, 28 no cruzamento, 320dp/130%, 200% de fonte e reboot API35.

**Status:** apenas staging, baseada na P7.50.6 `aabf5843`. Não integrar nem declarar aprovação antes de ter a P7.50.6 integralmente verde. Requer também Source, OTA e matriz própria verde depois da integração. PR #13 draft, `main` intacta; não publicar APK/OTA. Comparação visual 1:1 humana e ensaio Galaxy A55/TalkBack físico pendentes.
