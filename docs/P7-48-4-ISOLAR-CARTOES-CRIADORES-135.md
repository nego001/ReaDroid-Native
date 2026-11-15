# P7.48.4 — Criadores a 135% isolados sem retirar nenhuma regressão

## Evidência observada
A matriz [#40161577072](https://github.com/nego001/ReaDroid-Native/actions/runs/40161577072) da P7.48.3 falhou nas tentativas 1 e 2 da API35, com API29 `success` (165 testes, 14 capturas). Na tentativa 1, a captura do Explorador foi bloqueada por ausência de foco (diagnóstico `focusedSystemWindows=unavailable`). Na tentativa 2, Explorer e 5 sessões isoladas foram aprovados; após 12 testes da classe de navegação o dispositivo `emulator-5554` desapareceu durante `enlargedFontsStackCreatorCardsWithoutLosingActions`. O JUnit da API35 registra esse caso com duração de **80,954 segundos**, falha sem mensagem, seguida por `device 'emulator-5554' not found` e `Expected 44 tests, received 12`. Não há prova do defeito funcional do app, mas há falha concreta de estabilidade da sessão de teste.

## Mudança sem redução de cobertura
Move **exatamente o método original completo** `enlargedFontsStackCreatorCardsWithoutLosingActions` para a classe `P7CreatorCardsLargeFontInstrumentedTest`, que roda como sessão Gradle independente, sem mudar asserções, preferências, verificações de orientação, altura, TalkBack ou restauração no `finally`.

Obrigatórias agora **8 sessões / 27 seletores únicos**, distribuindo **165 testes/API** em `1+1+1+1+1+1+43+116`. Permanece integral o isolamento prévio do logotipo 135%, a regressão nativa do botão Voltar e a espera real pela janela. Source contracts exigem transferência única da regressão, configurações 135%, dimensões, botão acessível e restauração. Não há skip, retentativa automática, relaxamento do gate, alteração no código de produção nem mudança de evidência.

Permanecem 14 capturas/API, 28 cross, reboot API35, testes compactos e fontes 200%, Source/OTA e falha fechada. **Só aprovar após CI nova API29/API35/cross completamente verde.** P7.49 permanece em branch separada, sem aprovação de merge. PR #13 draft, `main` intacta, nenhum APK/OTA publicado, visual 1:1 e Galaxy A55/TalkBack físico pendentes.
