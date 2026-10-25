# P7.48.6 — handshake de tamanho/fonte do teste compacto (staging)

A P7.48.4 falhou nas duas tentativas da matriz #40165738245 após os 165 testes instrumentados API35, capturas normais e reboot validado: `Tab 'Início' not found` logo após `wm size` (320 dp) e `font_scale` (1.3). O diagnóstico P7.48.5 foi integrado em `1a552514`, com execução Android ainda pendente no momento deste estágio.

Este estágio **não presume a causa da ausência da aba**. Ele corrige uma lacuna objetiva no contrato de teste: comandos de configuração anteriores não verificavam que o sistema efetivamente aplicou o viewport necessário antes da navegação e dos screenshots.

- Após definir tamanho e fonte, conferir por `wm size` que há override exato dos pixels calculados para 320×720 dp; conferir `wm density` sem alteração e `settings get system font_scale` igual a 1.3 (tolerância numérica de 0.002).
- Repetir a conferência imediatamente após relançar o aplicativo, antes de tocar na aba `Início`.
- Qualquer falha gera o relatório/PNG opcional de diagnóstico P7.48.5, preservando a exceção original e a restauração em `finally`.
- Testes unitários rejeitam override ausente/incorreto, densidade diferente, escala errada, NaN e dados malformados. O fluxo Android continua exigindo todas as 14 capturas oficiais, 165 testes/API, 8 sessões e auditoria cruzada das 28 imagens.

**Estado:** branch separada. Não integrar enquanto a matriz P7.48.5 estiver rodando; usar o diagnóstico dessa execução para determinar se sincronização, janela ou layout nativo é a causa real. Não relaxar o gate; P7.49 (166 testes/API) segue isolada. PR #13 draft, `main` intacta; nenhum APK/OTA publicado; 1:1 e Galaxy A55/TalkBack físico pendentes.
