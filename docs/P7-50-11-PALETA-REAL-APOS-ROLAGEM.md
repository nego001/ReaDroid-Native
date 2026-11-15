# P7.50.11 — ação de cores realmente operacional após rolar a página

## Origem

A P7.50.10 passou **171 testes instrumentados por API** na [CI #40223740007](https://github.com/nego001/ReaDroid-Native/actions/runs/40223740007), tentativa 2, com 3/3 jobs verdes e cross 28/28. A regressão anterior provava que **Cores e tons**, **Exportar aparência** e **Importar aparência** continuam inteiros e acessíveis abaixo da primeira dobra. Ainda não provava que tocar em uma ação deslocada acionava sua função real.

## Implementação (apenas teste; código de produção intocado)

Novo `P7NavigationInstrumentedTest.belowFoldColorActionOpensNativeChooserAndCancelIsNonDestructive`:

1. Abre `MainActivity` genuína e navega para a aba inferior **Design**.
2. Encontra o cartão **Cores e tons** por `contentDescription` e o rola para a tela via `requestRectangleOnScreen`, confirmando visibilidade e papel nativo de botão.
3. Salva um snapshot de **todas** as preferências de `v3_personalizacao`, sem alterar estado.
4. Aciona o `performClick` real. Inspeciona a **janela ativa de acessibilidade** através do `UiAutomation` do Android (um AlertDialog tem janela própria e não está na árvore da Activity). Exige os títulos/opções **Cor de destaque, Azul, Roxo, Verde, Laranja, Minha cor (HEX), Cancelar**, textos exatamente iguais aos da implementação existente.
5. Aciona o **Cancelar** real por `AccessibilityNodeInfo.ACTION_CLICK`, aguarda a UI e confirma que o conjunto de preferências permanece idêntico, a ação continua clicável e a navegação continua em Design.

Não seleciona cor, não executa exportação, não concede permissões, não acessa SAF nem altera APK ou projeto. Teste falha ao invés de improvisar se janela/itens/cancelamento desaparecerem. O código de produção `P7DesignStudio` e `MainActivity` não foi modificado.

`tests/test_p7_capture_runner.py` exige **49 métodos de navegação**, inclusive os três contratos prévios. Meta sobe para **172 testes instrumentados por API** (6 isolados +49 navegação+117 restantes), sem remover nenhum. Mantidas as 14 capturas por API, cross 28/28, viewport 320dp/130%, fonte 200%, reboot API35 e Source/OTA.

## Estado e aprovações

Base inicial: P7.50.10 totalmente verde `f68b555c`. P7.50.11 somente pode ser considerada aprovada após a CI completa no SHA exato e evidências reais nas duas APIs. `main` intacta, PR #13 em rascunho, nenhum APK ou OTA publicados. Homologação visual humana 1:1 e teste físico do Galaxy A55 com TalkBack continuam pendentes.
