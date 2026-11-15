# P7.37.1 — Teste de ícones com fonte 135% isolado

A [matriz P7.37 #40106710970](https://github.com/nego001/ReaDroid-Native/actions/runs/40106710970) concluiu Android10 com sucesso, mas Android15 perdeu `emulator-5554` durante `fourIconTemplatesGrowWithLargeTextAndAnnounceSingleButtons`, após somente 11/36 resultados de navegação. A auditoria cruzada foi bloqueada. Não há stack comprovando defeito do aplicativo nem relação causal com o novo teste de duplo clique.

O método original foi movido integralmente à nova `P7IconTemplatesLargeFontInstrumentedTest`, incluindo fonte 135%, nomes dos quatro templates, dimensões, acessibilidade, papel Button, ausência de ellipsis e restauração das preferências. Foram copiados apenas os helpers de busca de Views de que esse método depende. **Nenhum teste foi desabilitado e nenhuma asserção foi removida.**

O workflow agora exige cinco invocações Gradle por API: 1 barra inferior + 1 boas-vindas + 1 ícones + 35 navegação (inclusive duplo clique) + 116 demais, somando **154 testes**. O contrato exige 24 seleções únicas e a exclusividade do método na nova classe. Mantidos Android 10/15, 14 PNGs por API, viewport 320dp/130%, fonte 200% e auditoria 28/28, todos fail-closed.

A separação é mitigação de isolamento, não prova da causa raiz do desaparecimento do emulador. PR #13 continua draft, sem merge `main`, APK ou OTA publicados; visual 1:1 e Galaxy A55/TalkBack pendentes.
