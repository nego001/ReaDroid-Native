# P7.48.5 — Captura de diagnóstico do viewport compacto sem relaxar o QA

## Motivo
Na matriz #40165738245, tentativas 1 e 2, Android 10/API29 passou e Android 15/API35 passou nas 8 sessões de testes (165 instrumentados) e nas capturas normais. Após reboot comprovado, o teste compacto 320dp/fonte130% falhou nas duas execuções com `Tab 'Início' not found`, antes do primeiro PNG compacto. A origem da ausência da aba na hierarquia ainda não foi provada; a comparação cruzada de 28 imagens foi skipped.

## Mudança
Em falha do smoke compacto, **antes** da restauração de viewport e fonte, salvar um registro limitado de foco do WindowManager, atividade retomada, abas e mensagens de ANR existentes na hierarquia já capturada, além de tentar um screenshot de diagnóstico. Upload dos dois artefatos opcionais com `if: always()`. A rotina nunca disfarça falha da aba, não dispensa overlay desconhecido, não relança o teste e não conta a imagem de diagnóstico entre as 14 evidências obrigatórias por API. Se o ADB estiver indisponível, a asserção original continua falhando.

## Validação
Há regressões unitárias para foco não correspondente, indisponibilidade do ADB e coleta dos arquivos. Exigir a nova CI P7.48.5 em ambas as APIs antes de qualquer aprovação. Se o mesmo erro continuar, inspecionar diagnóstico novo e corrigir a causa específica, não reduzir o gate.

P7.49 permanece isolada em staging e precisa de execução própria (166 testes/API) após a estabilização. PR #13 draft, `main` intocada, sem distribuição de APK/OTA; 1:1 e Galaxy A55/TalkBack físico pendentes.
