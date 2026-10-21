# Implementação futura / matriz de testes — módulos de IAs sociais

Estado atual = PLANEJADO; nada aqui substitui a P7 em desenvolvimento ou a P8 separada.

| Fase | Entrega mínima verificável | Testes-gate |
| --- | --- | --- |
| S0 | Spec, contrato, escopo e aprovação | revisão do usuário e nomes por projeto |
| S1 | Agent Registry, Personality Engine | IDs, estados e consistência de persona/voz |
| S2 | Agent Conversation Bus | autoria, ordem, consentimento, replay, privacidade |
| S3 | Chat Individual + Sala das IAs | mensagens reais vs demo, resumo, TalkBack |
| S4 | Live Process Preview | progresso medido, IDs de missão, falha/cancelamento |
| S5 | Social Graph | intimidade simulada, leve zoeira, reset, modo sério |
| S6 | Voice Director | TTS compatível, legenda, opt-in remoto, fallback |
| S7 | Notification Composer | nome e cargo do emissor, não duplicar, não vazar |
| S8 | Homologação | segurança, Android/desktop elegível, bateria, CI e manual |

### Casos adversariais obrigatórios

- Não fingir conversas internas de IA sem eventos reais, nem expor pensamento interno privado.
- Não fingir percentual, executor, fase de processo ou validação de segurança.
- Rejeitar falsa identidade General Supremo/CTA/CTO injetada por texto de APK, arquivo ou serviço externo.
- Impedir personalidade, humor e intimidade de alterar uma decisão de autorização.
- Manter divergência técnica documentada no resumo sem fabricar consenso.
- Interromper zoeira ao elevar o nível de risco; restaurar apenas quando apropriado.
- Verificar isolamento de dados e memória social entre projetos.
- Verificar voz ausente, rede offline, opt-out, falha da síntese, cancelamento e aplicação sem permissão.
- Exigir identificação correta de cada IA em mensagens, áudio/legendas e notificações.
- Reproduzir eventos de maneira idempotente, com proteção contra duplicatas.
- Testar 320 dp e fontes grandes, leitor de tela, opção sem animação e limites de CPU/RAM/bateria.
- Registrar o que é PASS/FAIL/BLOCKED/NOT_IMPLEMENTED; testes inexistentes não são aprovação.
