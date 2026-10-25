# P7 Preview 5 — auditoria visual com captura real

**Data:** 20/10/2026  
**Referência vinculante:** arte enviada pelo proprietário, três telas NegrecoDroid, referência `negrecodroid_controle_total_de_apks.png`.  
**Ambiente de comparação:** tela real do app em emulador Android 15/API35, a partir do workflow P7.  
**Status:** melhora material da composição; **NÃO 1:1 homologado**.

## Evidência verificável

- [Workflow Android 10/15 aprovado do protótipo compacto](https://github.com/nego001/ReaDroid-Native/actions/runs/39381467220).
- Artefatos `p7-brand-android-35.png`, `p7-explorer-android-35.png`, `p7-design-android-35.png` no workflow acima.
- O screenshot de Design foi conferido visualmente, não apenas por texto ou compilação.
- A próxima execução precisa repetir os mesmos três screenshots com o commit final da Preview 5.

## Design Studio: diferenças reais corrigidas

| Região na arte original | Preview 4 anterior | Preview 5 |
|---|---|---|
| Título e tabs superiores | Título e abas grandes | Cabeçalho e quatro abas compactados |
| Previews de Temas | Cards altos e aplicação em faixa inteira | Cards menores, check azul e botão de catálogo `Ver todos ›` funcional |
| Opções de Layout | Miniaturas iguais às de temas | Miniaturas de esquema de layout com proporção independente |
| Criador de Ícones / Logo Studio | Ficavam abaixo da dobra | Dois cartões lado a lado, visíveis no primeiro viewport |
| Presets de Aparência | Ficavam fora da primeira tela | Cinco miniaturas compactas, com visual próprio, visíveis na primeira tela |
| Aplicação e persistência | Botões enormes interrompiam a galeria | Acesso por diálogo de catálogo, confirmação, gravação e recriação real da UI |

## Integridade funcional

1. `P7DesignStudio.showCatalogDialog` abre lista nativa de opções existentes, seleciona, pede confirmação e usa os aplicadores reais `P7ThemeCatalog` e `P7VisualCatalog`.
2. Mantidos import/export JSON, segurança do workspace, SAF, edição pendente, índice SQLite e rollback via cancelamento do diálogo.
3. `P7ThemePreviewView` ganhou três modos Canvas diferentes: tela de tema, esqueleto de layout e chip visual de preset, sem bibliotecas extras ou network.
4. `tools/p7_design_smoke.py` exige **no mesmo viewport**: cabeçalho, Temas, Layout, Ícones, Logotipo, Previews de Temas, Opções de Layout, Criador de Ícones, Logo Studio, Presets de Aparência, Dark OLED. O teste também abre `Ver todos` e confere o catálogo real.

## Pendências bloqueando o aceite literal 1:1

- As miniaturas são reproduções vetoriais aproximadas; ainda não são os recortes oficiais usados no mockup original.
- O mascote nativo na Home ainda é uma aproximação em Canvas e não a figura oficial da arte aprovada.
- Presets `Glass` etc usam composições de paletas já implementadas, não renderização completa dos efeitos visuais.
- O histórico de projetos múltiplos, os números de builds e a contagem de ameaças exigem dados reais antes de exibição.
- As duas artes PNG originais precisam ser incorporadas à árvore GitHub como binários para auditabilidade.
- Faltam comparação de recortes, resultados de CI do commit exato Preview 5 e avaliação física no Galaxy A55.

**Regra:** jamais declarar a P7 como visual 1:1 concluído com base apenas em compilação ou screenshots aprovados em testes automatizados. O proprietário deve poder comparar e aprovar a composição literal.
