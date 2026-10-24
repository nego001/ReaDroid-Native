# P7.37 — Toques consecutivos em preset não podem empilhar confirmações

## Base
A P7.35.5 introduziu `P7DesignStudio.presetConfirmation` para impedir duas janelas de confirmação abertas em paralelo; P7.36 cobriu Cancelar e Back. Falta uma regressão instrumentada que prove o bloqueio de dois cliques rápidos.

## Caso instrumentado
`P7NavigationInstrumentedTest.repeatedPresetTapNeverStacksNativeConfirmations`:
1. Abre a MainActivity/Design reais, registra o mapa completo de `v3_personalizacao` e escolhe preset diferente do aplicado.
2. Dispara o clique no cartão e exige AlertDialog real visível.
3. Dispara o mesmo listener do cartão original outra vez, modelando um segundo toque enfileirado antes de a janela modal impedir o toque físico; exige **a mesma instância do AlertDialog**, ainda visível, e nenhuma gravação.
4. Clica em Cancelar, aguarda o looper, exige janela dispensada, referência do Studio limpa, estado de acessibilidade `selecionar prévia` restaurado e preferências integralmente idênticas.
5. Mantém limpeza fail-closed no `finally` sem converter falha em sucesso.

O teste não presume que um segundo toque físico atravessa o diálogo. Verifica somente o tratamento de eventos de clique já enfileirados. Não altera a implementação de produção nem os mecanismos de persistência.

## Gates obrigatórios
- [ ] Integrar somente após a conclusão e análise da matriz P7.36.4.
- [ ] Source checks e OTA na P7.37.
- [ ] Sessões API29 e API35: 1 teste de barra inferior, 1 de cartão de boas-vindas, 36 de navegação e 116 demais; **154 por API**, sem falhas.
- [ ] 14 capturas reais por API e cross-review 28/28.
- [ ] Inspeção humana Galaxy A55/TalkBack e aceite 1:1 separados.

PR #13 draft; main intocada, sem APK de distribuição ou OTA. `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
