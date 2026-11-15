# P7.17 — Auditoria de discrepâncias e prova independente de capturas

**Projeto:** NegrecoDroid, PR #13 (branch `feature/p7-negrecodroid-visual-foundation`).  
**Referências do proprietário:** `negrecodroid_controle_total_de_apks.png` SHA-256 `d0232e8a93d793c5cde3d564f90c8c5ecdd870bee497558db0442bf98326461b` e `identidade_negrecodroid_em_neon_azul.png` SHA-256 `25f93465b1ad0da45398201d9718cc070f3ba7fce11f84bf81e973c0b06d2765`.

## Evidência observada

Usei a [CI P7.15 #40010491284](https://github.com/nego001/ReaDroid-Native/actions/runs/40010491284), aprovada nas APIs 29/35 com 141 testes gerais + 1 captura isolada por API, 14 PNGs por API e relatório cruzado, como **linha base visual**. Comparei os PNGs reais `p7-brand-android-35.png`, `p7-explorer-populated-android-35.png`, `p7-design-android-35.png` com os três celulares da arte promocional original. A arte de referência tem molduras, cenário e dados ilustrativos, não é uma captura nativa. Portanto, **não calcular correspondência pixel-a-pixel automaticamente sobre a peça publicitária inteira**.

| Prioridade | Área | Diferença / constatação | Próximo critério |
| --- | --- | --- | --- |
| Alta | Símbolo N/escudo e ícone | O vetor funcional apresenta o símbolo azul, mas não reproduz integralmente o acabamento metálico azul/ciano e o grafismo luminoso da prancha de marca | Auditar geometria, gradientes e adaptive icon em vetores/recursos Android reais |
| Média | Home | Cabeçalho, mascote, saudação, grade 2×2 e ações rápidas estão presentes. Proporções e espaçamentos diferem do mockup | Comparar medidas no viewport canônico sem inventar dados |
| Média | Explorador populado | Cartão, busca, filtros, índice e lista de arquivos reais do ZIP de QA funcionam; há diferenças na densidade e na iconografia das linhas | Refinar componentes nativos preservando navegação, pesquisa e SQLite |
| Média | Design Studio | Abas, temas, layouts, criadores e presets existem; miniaturas e acabamento dos cartões ainda não reproduzem fielmente a ilustração | Confrontar previews, bordas, tipografia e posicionamento no mesmo viewport |
| Bloqueador | PNGs oficiais no GitHub | Ambos têm SHA correto na auditoria local, mas ainda não foram versionados em `design/reference/p7/` | Incorporar os dois binários exatos com hash/CRC, sem recriar imagens |
| Bloqueador | Aceite 1:1 e telefone físico | Emuladores e capturas não bastam para aprovação do proprietário | Revisão humana no viewport canônico, TalkBack e ensaio Galaxy A55 |

**Importante:** os números de projetos/APKs, datas e nomes como `Spotify_Mod` pertencem **somente ao conceito publicitário**; o estado vazio da Home e o ZIP sintético da instrumentação não são defeitos, mas regras para evitar simular dados do usuário.

## P7.17 — proteção adicional na evidência

O inventário de 14 PNGs agora rejeita screenshots **byte a byte idênticas entre cenas** pelo SHA-256, mesmo quando ambas têm estrutura, dimensões e CRC válidos. Isso detecta casos simples de reuso acidental (por exemplo, copiar o PNG de Segurança para Build). A suíte de testes cria 14 fixtures PNG sintéticas distintas e testa que uma cópia renomeada causa `ScreenshotEvidenceError`, sem publicar resultado PASS.

A verificação **não** mede semelhança visual, não impede todos os tipos de conteúdo errado e não prova fidelidade 1:1. As regras de foco real do app, detecção de modal ANR no Explorador populado, inventário de 28 imagens, segurança de APK e mecanismos de regressão continuam intactos.

## Estado e limites

- A [P7.16 CI #40012227769](https://github.com/nego001/ReaDroid-Native/actions/runs/40012227769) concluiu verde na segunda tentativa após reconexão do emulador Android 15; o job Android 10 já estava verde. 
- **`references=BLOCKED`**, **`visual_1to1=NOT_APPROVED`**, **`physical=NOT_APPROVED`** permanecem válidos.
- Nenhum merge em `main`, nem distribuição de APK ou OTA, está autorizado por este relatório.

A aprovação de uma nova CI para a checagem de duplicidade é exigida antes de considerar este guard validado nos emuladores.
