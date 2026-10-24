# P7.19 — Controles do topo mais fiéis à Home de referência

**Base:** [CI P7.18 #40018084370](https://github.com/nego001/ReaDroid-Native/actions/runs/40018084370), 141 casos gerais + 1 captura isolada em Android 10 e 15, 28 PNGs e cross-API aprovados.

## Discrepância verificada

Na arte oficial `negrecodroid_controle_total_de_apks.png`, a Home exibe
ícones discretos de **menu e configurações**, sem grandes caixas ao redor.
A captura real `p7-brand-android-35.png` da P7.18 tinha dois botões
quadrados preenchidos, com bordas nítidas, ocupando visualmente todo o
alvo de 48dp. Isso competia com o logotipo, o mascote e a saudação.

## Ajuste

`P7HomeToolbar` agora conserva **exatamente o mesmo retângulo funcional
de 48×48dp** e os callbacks originais, mas exibe cada linha de ícone numa
área de **22dp** centrada (padding 13dp), sem contorno persistente. A
ação ganha resposta `RippleDrawable` durante o toque, tooltip
contextual e semântica de **botão** ao leitor de tela. Nenhuma mudança
na posição da navegação inferior, no tamanho da área clicável nem na
ação que abre Design Studio. O APK do usuário, SAF, edição,
reconstrução e dados estão fora do escopo.

O teste instrumentado já existente `homeHeaderOpensActualMenuAndDesignPreferences`
foi ampliado para checar que os dois controles mantêm 48dp,
padding simétrico 13dp, ripple e navegação funcional.

**P7.19 só recebe aprovação depois da CI integral e capturas de
API29/API35.** Referências binárias `BLOCKED` enquanto os
dois PNGs exatos ainda não estiverem no GitHub; visual 1:1
e inspeção física A55 continuam pendentes.
