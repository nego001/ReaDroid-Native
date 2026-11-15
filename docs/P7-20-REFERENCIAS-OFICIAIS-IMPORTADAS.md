# P7.20 — Referências oficiais incorporadas sem alteração dos bytes

## Resultado

Foram incorporados à branch `feature/p7-negrecodroid-visual-foundation`
exatamente os **dois PNGs aprovados pelo proprietário** na issue #11,
sem recompressão ou alteração. Os objetos Git criados a partir do
conteúdo recebido coincidiram com `git hash-object` dos arquivos originais,
antes de o commit alterar a árvore.

| Arquivo | SHA-256 oficial | Hash do objeto Git |
| --- | --- | --- |
| `design/reference/p7/negrecodroid_controle_total_de_apks.png` | `d0232e8a93d793c5cde3d564f90c8c5ecdd870bee497558db0442bf98326461b` | `fc849a4574821827328d0335d226fdc305106b63` |
| `design/reference/p7/identidade_negrecodroid_em_neon_azul.png` | `25f93465b1ad0da45398201d9718cc070f3ba7fce11f84bf81e973c0b06d2765` | `5b0aaef38c81fd333a504d32e2c16f3f4f7e508b` |

Dimensões originais: **1448×1086** cada uma.

## Critérios automáticos

`tools/p7_reference_assets.py` verifica no CI da PR P7 a presença
dos dois arquivos, dimensões, CRC dos chunks PNG, fechamento e SHA-256.
Não altera o hash esperado nem aceita thumbnails, vetores recriados,
capturas de teste ou arquivos ausentes.

O inventário de capturas da matriz Android agora pode reportar
`official_references=VERIFIED` após a execução da CI. O painel offline
pode mostrar as artes oficiais reais, separadas das 28 capturas do
emulador.

## O que **não** foi aprovado

A importação não transforma o design em 1:1:
**`visual_1to1=NOT_APPROVED`** até comparação/revisão visual humana,
alinhamento de elementos e aceite do proprietário. O teste físico e
TalkBack no Galaxy A55 continuam **`physical=NOT_APPROVED`**.
Não houve merge em `main`, publicação de APK de distribuição ou OTA.
