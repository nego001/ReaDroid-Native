# P7.35.3 — Aguardar o cancelamento nativo do diálogo antes de conferir a prévia

## Falha reproduzível identificada

[CI P7.35.2 #40069588837](https://github.com/nego001/ReaDroid-Native/actions/runs/40069588837) executou a classe de navegação com **36 testes** nos emuladores Android 10/API29 e Android 15/API35 **sem perder o emulador**, mas em ambos houve 1 falha na nova regressão `cancellingDifferentPresetRestoresCommittedAppearance`. A segunda sessão de instrumentação não rodou, e a revisão cross-API foi bloqueada corretamente.

Os XMLs instrumentados das duas APIs registram exatamente `AssertionError` na linha 1002: a descrição do cartão escolhido ainda não voltou a `selecionar prévia` quando a verificação começou. A etapa anterior do teste já havia passado: a escolha temporária não acionou a persistência e não desenhou ✓. A asserção final de igualdade das preferências **não foi alcançada**, portanto não afirmar que todo o fluxo Back está aprovado.

## Ajuste de sincronização do teste

- Após `Instrumentation.sendKeyDownUpSync(KEYCODE_BACK)`, executar `Instrumentation.waitForIdleSync()` antes de ler o estado da `MainActivity`. O listener `AlertDialog.setOnCancelListener` pode ser processado por mensagem do looper após a entrega do evento.
- Manter todas as verificações de seleção provisória, inexistência do ✓, ausência de gravação antes da confirmação, retorno a `selecionar prévia` e comparação **integral** das preferências após cancelar.
- Incluir a descrição realmente anunciada na falha caso o estado continue pendente, melhorando o diagnóstico. Não adicionar repetição que aceite um estado incorreto, nem remover/assert skip.
- **Nenhuma mudança em código de produção ou no que é persistido.** A correção do teste de Layout (P7.35.2) e as duas sessões obrigatórias (P7.35.1) ficam preservadas.

## Gates

- [ ] Source checks/OTA atualizados.
- [ ] A nova regressão passa em API29/API35 com a comparação das preferências realmente alcançada.
- [ ] Ambas sessões completas e restantes classes, 14 screenshots/API, auditoria cruzada 28/28.
- [ ] Se voltar a falhar, investigar `AlertDialog` e listener `OnCancel` como problema real. Não suprimir a falha.
- [ ] Galaxy A55/TalkBack e 1:1 visual requerem inspeção humana.

PR #13 draft, sem merge/main, APK de distribuição ou publicação OTA. `visual_1to1=NOT_APPROVED`; `physical=NOT_APPROVED`.
