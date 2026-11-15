# P7.50.5 — quatro miniaturas de tema visíveis no viewport de referência

**Base:** PR #13 P7.50.4 (`ff15467f`); este documento registra uma alteração em **staging**, ainda sem homologação de Android/Source/cross própria.

## Diferença observada em arte e screenshot reais

Na imagem oficial `design/reference/p7/negrecodroid_controle_total_de_apks.png`, a primeira fileira do Design Studio exibe **Negreco Blue, Carbon Dark, Matrix Green e Sunset** lado a lado. Na captura Android `p7-design-android-35.png` da CI P7.50.3.1 ([#40176254848](https://github.com/nego001/ReaDroid-Native/actions/runs/40176254848)), três cards e apenas parte do quarto ficavam visíveis. O código usava largura fixa de **100 dp** mais 8 dp de espaçamento por card.

## Mudança funcional, não imagem sobreposta

- No viewport de telefone de referência de **390 a 599 dp**, com fonte efetiva normal (até 115%), as miniaturas **de tema** usam **80 dp**, com até duas linhas completas para nome e subtítulo, **sem elipse**. O quarto tema passa a caber inteiro na faixa de ~393 dp.
- Em celular estreito (menos de 390 dp), tablets (600 dp ou mais) ou fonte efetiva ampliada acima de 115%, mantém as larguras anteriores de 100/144 dp, evitando apertar rótulos ou transformar a referência promocional em requisito rígido em outras telas.
- Os cartões continuam sendo views Android clicáveis, prévias geradas com `P7ThemePreviewView`, estados aplicados consultados na configuração REAL, distinção de glow, sem mudar `applySelectedTheme`, `Android Back` ou dados do projeto.
- O teste Java existente de política responsiva foi ampliado (sem criar uma execução a mais). O smoke `tools/p7_design_smoke.py` agora exige que os **quatro cards reais** sejam identificados na árvore acessível, apareçam na mesma linha, sem sobreposição, dentro da tela e com largura visível mínima de 70 dp, quando a viewport estiver de 390 a 419 dp. Tests Python reprovam itens ausentes, duplicados, ocultos e truncados.

**Gate de aceitação:** a meta permanece em **169 testes instrumentados/API** (6 isolados + 46 navegação + 117 restantes), **14 PNG/API**, Android10/API29, Android15/API35, 320dp/130%, 200% fonte, 28/28 auditoria cruzada, Source e OTA verdes no SHA exato. Se houver deslocamento de outras seções para fora do primeiro viewport, isso é regressão e não deve ser aprovado.

**Proteções:** PR #13 draft, `main` intacta; nenhum APK/OTA publicado nem atualização de versão. A aprovação humana de fidelidade 1:1 em todos os painéis e o teste Galaxy A55/TalkBack físico seguem pendentes.
