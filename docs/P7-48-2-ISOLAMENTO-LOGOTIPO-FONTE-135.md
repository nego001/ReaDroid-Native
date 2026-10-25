# P7.48.2 — Corrigir risco de perda do emulador na prévia 135% do logotipo sem alterar produção

## Diagnóstico reproduzido
A matriz P7.48.1 [#40159722827](https://github.com/nego001/ReaDroid-Native/actions/runs/40159722827) teve API29 **success** com 165 testes e 14 capturas. API35 falhou em duas tentativas consecutivas no mesmo teste `logoPreviewAnnouncesSavedNameAndSubtitleWithoutDuplicateNodes`. Na tentativa 2, os quatro testes isolados e captura Explorer inicial passaram; a classe de navegação iniciou com 45 testes, mas o dispositivo `emulator-5554` desapareceu: `Expected 45 tests, received 2`. O XML do JUnit de API35 registra o método durante aproximadamente 52,661 segundos e uma falha vazia, sem stack de asserção; seguido de `device 'emulator-5554' not found`. Isso **não comprova bug funcional** no método, mas impede a homologação de API35.

## Correção estritamente da instrumentação
Esta alteração transplanta de staging **somente o isolamento do método original de logotipo** para a própria branch da PR, sem a alteração de produção nem a nova regressão da P7.49. Todos os asserts continuam: Activity real, textos `display_name`/`display_subtitle`, 135% de fonte, descrição única TalkBack e estrutura sem nós duplicados, ajuste dinâmico de altura, restauração de preferências via `finally`.

O teste passa para `P7LogoIdentityLargeFontInstrumentedTest` em sessão obrigatória própria; helpers `describedView` e `clickableText` tornam-se package-private **apenas em androidTest**. O workflow exige **7 sessões**, **26 seletores distintos**, com `1+1+1+1+1+44+116 = 165 testes/API`. A regressão de Android Back da P7.48.1 e sua verificação de janela anexada **depois de waitForIdleSync** continuam intactas.

Não há remoção de teste, skip, retry automático, bypass de captura, mudança do APK de produção ou aprovação fictícia. Gates de 14 PNG/API, auditoria 28/28, fonte 200%, compacto 320dp, reboot API35, Source e OTA permanecem obrigatórios. A mudança continua **não aprovada** até passar a própria matriz Android29/API35 e cross. P7.49 e P7.50 staging originais não foram integradas como estão.

PR #13 permanece draft, main não alterada, sem APK/OTA publicado, visual 1:1 e Galaxy A55/TalkBack físico NOT_APPROVED.
