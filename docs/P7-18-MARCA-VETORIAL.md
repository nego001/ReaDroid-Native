# P7.18 — Refinamento do símbolo N e da marca vetorial

## Referências verificadas

As duas artes originais (`negrecodroid_controle_total_de_apks.png` e
`identidade_negrecodroid_em_neon_azul.png`) foram verificadas na auditoria
local pelos hashes SHA-256 oficiais da issue #11. **Continuam fora da árvore do
GitHub**: `references=BLOCKED` na CI até os binários exatos serem incorporados.

## Diferença e correção

Na prancha aprovada o monograma N combina **arestas ciano, fita diagonal azul,
remates metálicos prateados e trilhas eletrônicas**, com subtítulo **DESIGN
STUDIO**. O SVG preliminar exibia incorretamente **NATIVE STUDIO** e o ícone
Android tinha menos facetas metálicas. Nesta etapa:

- `design/brand/negrecodroid-mark-master.svg`: o texto agora é **DESIGN
  STUDIO**, e as novas facetas azul/prata foram aplicadas ao mesmo escudo;
- `ic_negrecodroid_foreground.xml`: faceta metálica no topo, laterais
  azul/ciano, fita de N em dois planos e remate prateado; permanece
  `VectorDrawable` real, independente do mockup publicitário;
- `test_p7_brand_identity_contract.py`: protege o texto, geometria da
  marca, três nós de circuito, versões normal/monocromática e vetores
  editáveis; roda em **Source checks**.

O app conserva `applicationId`, assinatura, XML de ícone adaptativo,
configuração monocromática e dados reais. **Não gera novo APK de distribuição,
nem afirma fidelidade visual pixel-a-pixel.** A comparação manual no viewport
canônico, incorporação das duas referências exatas e teste físico Galaxy A55
permanecem pendentes.

Linha base: [CI P7.17 #40015157037](https://github.com/nego001/ReaDroid-Native/actions/runs/40015157037)
verde em API29 e API35 (141 instrumentados + 1 captura isolada por API,
14 screenshots por API, cross-API). Novo commit exige nova CI completa.
