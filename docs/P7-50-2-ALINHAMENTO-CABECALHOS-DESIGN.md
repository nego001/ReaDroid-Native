# P7.50.2 — cabeçalho de catálogo alinhado à referência na tela compacta

**Base:** P7.50.1 `1565be55`, [CI #40173674078](https://github.com/nego001/ReaDroid-Native/actions/runs/40173674078) aprovada (API29/API35, cross 28/28, Source e OTA).

## Defeito visual observado

No `p7-compact-design-android-35.png` da evidência real, a seção **Previews de Temas** e o atalho **Ver todos** aparecem em duas linhas, adicionando uma faixa vazia acima dos cartões. Na referência oficial `design/reference/p7/negrecodroid_controle_total_de_apks.png`, estão na mesma linha. O comportamento anterior força orientação vertical de todo cabeçalho abaixo de 360dp, mesmo quando os dois textos têm largura para compartilhar uma linha.

## Alteração conservadora

- `P7DesignStudio.compactHeadingFitsInOneRow` só libera a linha compartilhada em larguras **menores que 360dp** e escala efetiva de fonte **até 140%**, quando a soma das medidas reais de texto do `TextView` cabe na largura útil depois de reservar margens e respiro adicionais.
- Continua empilhando cabeçalhos com textos grandes, com escala de 200%, quando a largura medida não comporta os dois controles e no comportamento já homologado de 393dp/fonte ampliada. A regra antiga `needsExpandedSectionHeader` permanece para altura natural, sem truncar títulos.
- **Ver todos** mantém 48dp de alvo mínimo, descrição completa para TalkBack, função original de abrir o catálogo e as mesmas guardas de diálogo. Título continua verdadeiro `AccessibilityHeading` e não é um botão falso.
- O smoke real de 320dp e fonte do sistema a 130% agora **exige geometria comprovada na hierarquia Android** para o par `Previews de Temas` / `Ver todos: Previews de Temas`: sem overlap, sem novo parágrafo, sem clipping e sem alvo faltando. Os testes Python rejeitam situações falsas; o teste instrumentado de política foi ampliado **sem remover nenhum teste anterior**.

**Meta inalterada:** 167 testes instrumentados/API em oito sessões; 14 capturas por API, cross 28, fonte 200%, viewport 320dp/130%, reboot API35, Source e OTA. Esta etapa necessita de CI própria para declarar sucesso. A homologação 1:1 completa, ícone/logo e Galaxy A55/TalkBack físico permanecem pendentes. PR #13 draft, `main` intacta, nenhum APK/OTA publicado.
