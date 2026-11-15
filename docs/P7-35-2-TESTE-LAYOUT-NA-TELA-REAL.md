# P7.35.2 — Teste de layout acessível usando navegação real em vez de substituir a tela

## Diagnóstico baseado em artefato, sem atribuição prematura

A [CI P7.35.1 #40069092786](https://github.com/nego001/ReaDroid-Native/actions/runs/40069092786) **falhou na API35** apesar de separar as 21 seleções de teste em duas sessões (uma de navegação inteira, outra com as 20 seleções restantes). A primeira sessão anunciou **36 testes**, concluiu **11**, e voltou a registrar `P7NavigationInstrumentedTest.layoutCardsKeepCompleteNamesAndNativeButtonRoleAtLargeFont` com `<failure></failure>` após 42 segundos e perda do dispositivo `emulator-5554` no ADB. Asserção real ou stack de erro do app não foi registrada. A captura sintética isolada do Explorador foi gerada antes do erro.

O código do teste problemático executava `activity.setContentView(fixture, 320dp)` dentro de uma `MainActivity` já retomada (`RESUMED`) e instanciava manualmente outra `P7DesignStudio` inteira com 12 miniaturas. Os outros testes conseguem analisar o Design Studio navegando pela `MainActivity` real. O `logcat` disponível termina depois de `ActivityScenario` reportar a MainActivity como retomada, sem identificar com certeza o motivo do sumiço do emulador.

## Correção do teste, sem reduzir a cobertura

- O método mantém o nome original e **todas as verificações**: 12 rótulos completos, largura ampliada `>=140dp`, títulos 3 linhas sem elipse, `Layout` mensurado, alvos focáveis/clicáveis, ocultação das prévias de TalkBack e nó acessível com papel `Button`.
- Em vez de substituir a Activity por uma tela artificial, abre a seção Design no rodapé, depois a subaba Layout, usando os mesmos botões reais que o usuário. Aguarda `waitForIdleSync` antes das asserções.
- A preferência de fonte 135% permanece preservada e restaurada no `finally`; não altera preferências do usuário.
- A prova de compactação 320dp continua nos scripts e casos específicos `p7_compact_smoke.py`/testes de política, com as capturas correspondentes 320dp/130%. O método aqui passa a verificar as 12 opções **na interface real com fonte ampliada**, sem alegar que a Activity real está em 320dp.
- Nenhum teste removido, nenhuma simulação de sucesso, nenhuma alteração no código de produção ou enfraquecimento de gate: as duas instrumentações da P7.35.1, 14 PNG/API e cross-review 28/28 continuam obrigatórias.

## Gates atuais

- [ ] Source checks, OTA, contrato de execução no novo SHA.
- [ ] Android 10/API29 e Android 15/API35: `P7NavigationInstrumentedTest` completa com 36/36; segunda instrumentação completa; novo cancelamento P7.35 testado.
- [ ] Capturas reais e auditoria cross-API 28/28.
- [ ] Fidelidade 1:1 humana e teste físico Galaxy A55/TalkBack seguem pendentes.

Não afirmar que o teste artificial causou a queda do emulador sem confirmação após a nova CI. PR #13 segue draft; `main` intacta; sem APK/OTA distribuídos; `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
