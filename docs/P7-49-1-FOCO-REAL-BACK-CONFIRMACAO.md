# P7.49.1 — confirmar foco da janela nativa antes do Android Back

## Falha observada (25/10/2026)

Na matriz [#40171467969](https://github.com/nego001/ReaDroid-Native/actions/runs/40171467969) da P7.49 v4 (commit `553d2c5c`), **Android 10/API29 e Android 15/API35 reprovaram no mesmo teste novo** `androidBackRollsBackThemeLayoutAndPresetConfirmations`: `Android Back must dismiss Apply confirmation`. Os seis testes isolados anteriores passaram em cada Android; o teste novo falhou na sessão de navegação e impediu a sessão restante de 116 testes, as capturas posteriores e a auditoria cruzada. Source e OTA passaram.

O teste novo confirmava apenas `dialog.isShowing()` dentro de `ActivityScenario.onActivity` e **imediatamente** enviava `KEYCODE_BACK` fora dessa callback. A regressão de Back em catálogos já existente aguarda `waitForIdleSync` e confirma `decorView.isAttachedToWindow()` antes de enviar a tecla. `isShowing()` sozinho **não prova** que WindowManager anexou e focou a janela; um Back prematuro pode ser dirigido à Activity subjacente. Essa explicação é uma **hipótese técnica**, não uma causa raiz comprovada.

## Mudança isolada de instrumentação

Antes de injetar **um único** `KEYCODE_BACK`, o novo teste agora exige, para o **mesmo** diálogo capturado e handle da família de aparência:
- `isShowing()`, `Window != null`, `decorView.isAttachedToWindow()` e `decorView.hasWindowFocus()` verdadeiros;
- sincronização da main thread entre verificações e até 12 leituras delimitadas, com pausa de 150 ms entre leituras malsucedidas;
- falha explícita caso o diálogo não obtenha foco. Não clicar em overlays, dispensar outro modal, reenviar Back ou remover asserções.

Depois da tecla, permanece obrigatória a verificação de que a janela fechou, **todos** os handles foram limpos, preferências ficaram idênticas, a prévia anterior foi restaurada e o diálogo reabriu/cancelou normalmente, repetido para tema, layout e preset. Contrato Python impede a retirada desses checks.

## Critério de aceitação

Somente CI própria da P7.49.1 com **166 testes por Android**, 8 sessões, compact 320dp/130%, fonte 200%, 14 PNG/API, cross 28, Source e OTA pode aprovar essa subetapa. Se o Back ainda falhar **após comprovação do foco real**, investigar tratamento de evento/diálogo em produção; não modificar o esperado dos testes.

PR #13 draft; `main` inalterada, sem merge nem publicação de APK/OTA, homologação visual 1:1 e testes físicos Galaxy A55/TalkBack pendentes.
