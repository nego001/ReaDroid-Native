# P7.41.2 — Atualização do smoke Design para estado realmente aplicado

**Falha identificada nas duas APIs em P7.41.1:** a matriz [#40116989109](https://github.com/nego001/ReaDroid-Native/actions/runs/40116989109) executou 158 testes de instrumentação completos por Android, porém o smoke da tela Design ainda exigia o anúncio antigo `, prévia selecionada`. Desde a P7.41, o anúncio correto de uma opção persistida é `, tema aplicado`. Por isso o smoke reprovou ambas as APIs depois da instrumentação, sem gerar inventário visual completo.

## Correção fail-closed
- `tools/p7_design_smoke.py` usa `applied_theme_preview(nodes)` para exigir exatamente um cartão oficial aplicado, clicável, com identificação do brilho `Neon ·` ou `Sem brilho ·` e subtítulo. Não considera prévia pendente ou apenas selecionada como aplicada.
- Preserva a exigência original de selecionar outro tema, abrir confirmação nativa, usar Android Back sem gravação e encontrar o mesmo cartão previamente aplicado.
- `tests/test_p7_design_smoke.py` amplia verificações simuladas: marca aplicada correta, rejeição de anúncio antigo/pendente, cartão duplicado, não clicável e descrição sem brilho.
- Sem alterações de produção, emulador, segurança, arte oficial ou screenshot gates. A exigência permanece **158 instrumentados por Android, 14 capturas/API e 28 na auditoria cruzada**.

**Status:** P7.41.2 precisa validar Android10 e Android15 e cross-review antes de ser considerada aprovada. Visual 1:1 e teste físico Galaxy A55/TalkBack permanecem sem aceite.
