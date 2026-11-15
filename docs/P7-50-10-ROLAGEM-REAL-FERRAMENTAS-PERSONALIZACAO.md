# P7.50.10 — rolagem real para ferramentas de personalização abaixo da primeira dobra

## Risco descoberto após P7.50.9

A P7.50.9 passou integralmente na [CI Android #40222070005](https://github.com/nego001/ReaDroid-Native/actions/runs/40222070005), com **170 testes instrumentados por API e 28/28 imagens**. Os PNG `p7-design-android-29.png` e `p7-design-android-35.png` verificam que a primeira faixa termina nos cinco presets, sem início de título cortado atrás do menu inferior. As três ações legadas reais de personalização ficam abaixo da primeira dobra e **devem permanecer alcançáveis pela rolagem vertical**. A P7.50.9 tinha uma checagem textual na fonte e geometria do primeiro viewport, mas faltava comprovar esse acesso num emulador.

## Contrato de funcionamento, não cosmética

Novo método `hiddenBelowFoldAppearanceToolsRemainReachableAndUnchanged` em `P7NavigationInstrumentedTest`, sobre a `MainActivity` genuína:

- Abre a seção **Design** pelo botão de navegação real e aguarda o ciclo da UI.
- Localiza o `TextView` nativo `Personalização existente`, verifica o papel de heading de acessibilidade nas APIs compatíveis e solicita ao Android que role a janela para expô-lo completamente, sem mover/desabilitar a barra inferior.
- Localiza as três ações nativas **Cores e tons**, **Exportar aparência** e **Importar aparência** por descrição de acessibilidade e role `Button`. Cada alvo precisa continuar clicável, focável, ter altura mínima **48dp** e ser *efetivamente visível sem recorte vertical após a rolagem*, verificado por `getGlobalVisibleRect` e altura real.
- Confere que somente navegar/rolar **não grava nenhuma preferência** em `v3_personalizacao`. Nenhuma ação de alteração é executada, nenhum APK/arquivo SAF é tocado e nenhuma permissão é solicitada.
- O teste usa `requestRectangleOnScreen` do View real em vez de uma árvore XML sintética. Não apaga `heading`, não aplica `View.GONE` e não fabrica capturas.

A P7.50.10 não modifica UI de produção. Endurece o teste instrumentado de **47 para 48 métodos de navegação**, e o contrato Python `tests/test_p7_capture_runner.py` exige a presença exata do método novo. Meta passa a **171 testes instrumentados/API** (6 isolados +48 navegação +117 outros); mantém 14 PNG/API, cross 28/28, 320dp/130%, fonte 200%, reboot API35, Source e OTA.

**Estado:** implementação em staging baseada no último SHA verde P7.50.9 `10d30c9f`. Só integrar se revisão do diff garantir ausência de mudança no código de produção e considerar aprovado após nova CI 171/API e auditoria cruzada 28/28. PR #13 draft, `main` intacta, nenhum APK ou OTA publicados. Aprovação visual humana 1:1 e teste físico Galaxy A55/TalkBack continuam pendentes.
