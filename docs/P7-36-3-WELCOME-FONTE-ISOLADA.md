# P7.36.3 — Isolamento do teste integral do cartão de boas-vindas

## Evidência registrada
[Workflow P7.36.2 #40105068417](https://github.com/nego001/ReaDroid-Native/actions/runs/40105068417) falhou em Android15/API35 durante a segunda sessão da instrumentação, **antes** da captura compacta e antes do `adb reboot` adicionado na P7.36.2. A primeira sessão de barra inferior passou 1/1. A classe de navegação começou 36 testes, coletou 34/36, mas o método `welcomeCardGrowsWithLongTextInsteadOfClippingIt` terminou como `FAILED` **sem stack de asserção** e ocorreu `device emulator-5554 not found`. Logo, a P7.36.2 **não chegou a testar** o reboot e não pode ser aprovada.

## Isolamento conservador, cobertura idêntica
- Copiar **integralmente** `welcomeCardGrowsWithLongTextInsteadOfClippingIt` para `P7WelcomeLargeFontInstrumentedTest`. Mantidos: `font_percent=135`, `ActivityScenario` real, medições de cartão/texto em `WRAP_CONTENT`, aumento dinâmico do parágrafo (35 repetições), espera pelo layout, pelo menos 10 linhas reais, 0 linhas elipsizadas e restauração das preferências no `finally`.
- Quatro invocações **obrigatórias** de `:app:connectedDebugAndroidTest`: primeiro barra inferior fonte 135% (1), segundo welcome-card fonte ampliada (1), terceiro navegação restante (35, inclui Back e Cancelar de presets), quarto as mesmas 20 seleções (116 testes). Total **153 por API (1+1+35+116)**, sem excluir ou aceitar falhas.
- `tests/test_p7_capture_runner.py` passa a exigir 4 comandos, 23 seleções únicas, exatamente 35 testes na navegação e o método isolado com as verificações principais. Nenhuma alteração de produção, overlays, política de fonte ou persistência.
- A sequência de capturas continua inalterada. Após 153 testes e telas normais, somente a API35 reinicia a AVD com o reboot verificado da P7.36.2; a captura compacta 320dp/130%, a de fonte 200% e o inventário de 14 capturas/API permanecem obrigatórios.

**Condição de saída:** Source/OTA, API29/API35 completas, 28 PNGs e cross-review 28/28; homologação humana Galaxy A55 e fidelidade 1:1 pendentes. PR #13 draft, sem merge, distribuição APK ou OTA, `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.

**Causa raiz ainda aberta:** não há evidência suficiente para concluir se a perda de ADB resulta de emulador, launcher ou aplicação. O isolamento busca obter execução reprodutível e não mascara falhas.
