# P7.46 — Diagnóstico delimitado de foco do Explorador

## Contexto
A P7.45 [workflow #40151816863](https://github.com/nego001/ReaDroid-Native/actions/runs/40151816863) teve a API29 success (162 testes instrumentados/API, 14 capturas) mas API35 falhou no passo obrigatório `p7_capture_populated.sh` **antes** da suíte instrumental: `Explorer Activity lost foreground window focus after bounded recovery; no unrelated overlay was dismissed`. Não se trata da regressão 135% isolada: ela nem chegou a rodar. A segunda tentativa de API35 foi solicitada, ainda sem aprovação quando este estágio foi preparado.

## Alterações previstas (somente instrumentação/contratos)
No método `assertExplorerWindowInForeground` de `P7ExplorerPopulatedCaptureInstrumentedTest`, quando a janela real não recupera foco, o teste continua **falhando imediatamente**, sem dispensar qualquer overlay desconhecido, clicar no sistema, aumentar o timeout ou salvar uma captura. Como *diagnóstico de falha*, lê uma vez, por `UiAutomation.executeShellCommand`, apenas `mCurrentFocus=` e `mFocusedApp=` de `dumpsys window`. O resumo limita cada linha a 240 caracteres e o total a 512; se inacessível ou grande demais, registra `unavailable`. Nunca usa essas informações para aprovar a tela. A mensagem JUnit inclui `focusedSystemWindows=`, permitindo diferenciar launcher, app ANR e outra janela no próximo incidente.

A própria regressão Android de overlays testa o resumo exato do dump, descarta linhas alheias e restringe o tamanho. Contrato Python exige o método e a mensagem, sem retirar nenhum teste. Cobertura permanece **162 instrumentados/API**, 6 sessões, 14 screenshots/API, 28 cross-review.

**Status:** P7.46 preparado em staging, ainda não integrado nem executado no Android. `main` intocada, PR #13 draft, sem APK/OTA publicado, visual 1:1 e Galaxy A55/TalkBack físico não aprovados.
