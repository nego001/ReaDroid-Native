# P7.49.1 — Diagnóstico fail-closed da tela compacta API35 (staging)

## Evidência
Na P7.48.4, matriz [#40165738245](https://github.com/nego001/ReaDroid-Native/actions/runs/40165738245), tentativa 1: API29 aprovou. API35 executou os 165 testes instrumentados e o reboot obrigatório; o teste de 320 dp / fonte 130% falhou ao buscar `Tab 'Início' not found`. A origem dessa ausência **não foi provada**. A tentativa 2 foi iniciada para o job API35 sem rerodar a API29.

## Alteração isolada
Base: P7.49 v3, commit `f0a8c1c0`, contendo guarda única de modais e regressão adicional de Android Back. Esta subetapa adiciona **apenas diagnóstico de teste**, sem alterar UI de produção nem reduzir cobertura.

- Antes da restauração obrigatória do viewport/fonte em caso de falha, salvar `p7-diagnostic-compact-android-{api}.txt` com foco do WindowManager, atividade retomada e descrições **filtradas** da hierarquia já capturada (abas e ANR), sem publicar o dump integral.
- Tentar um PNG de diagnóstico `p7-diagnostic-compact-android-{api}.png`, separado das **14 imagens oficiais por API**. A ausência do PNG, do ADB ou do dump nunca converte falha em aprovação.
- `raise` preserva a exceção original do teste, seguido pelo bloco `finally` que restaura tamanho, fonte e relança o app.
- O upload `if: always()` coleta os novos arquivos; testes unitários simulam foco incorreto e indisponibilidade do ADB.
- Não dispensa overlays desconhecidos, não desativa verificações, não relaxa a asserção `Início` nem tenta classificar visualmente uma tela inacessível como aprovada.

## Gate de integração
A **P7.48.4** só pode ser homologada com Android 10, Android 15, todos 165 testes, telas compactas, fontes ampliadas, 14 PNG por API e comparação cruzada verde. A **P7.49 / P7.49.1** deve então receber CI própria de 166 testes por API e auditoria cruzada. Nenhum resultado da P7.48.4 prova a P7.49.

A PR #13 permanece em rascunho, `main` intacta, APK e OTA sem publicação. Homologação 1:1 e Galaxy A55 / TalkBack físico pendentes.
