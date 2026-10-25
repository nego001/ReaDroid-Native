# P7.33 — Presets explicam seus efeitos reais ao TalkBack e na confirmação

## Por que esta etapa existe

A P7.32 corrige a aparência das cinco miniaturas para usar os mesmos tokens de `P7VisualCatalog.persistPreset`, porém os cartões continuam anunciando apenas `<nome>, selecionar prévia`. A confirmação usa uma frase genérica sobre cores e densidade. Isso não permite que a pessoa saiba **qual** tema, cor, glow, layout e raio serão salvos antes de aplicar.

## Mudança proposta na branch de desenvolvimento

- `P7VisualCatalog.presetSummary(index)` deriva **somente** dos mesmos arrays privados usados por `persistPreset` e rejeita índices fora do catálogo.
- Cada cartão de preset continua sendo um único botão real acessível, agora com leitura de tema, acento, brilho neon, layout e raio, sem adicionar controles ou focos duplicados.
- O diálogo **Aplicar?** detalha os valores concretos e preserva `Aplicar/Cancelar`, o reinício controlado e as referências ao projeto ativo.
- Resumos esperados: Dark OLED = OLED/azul/sem glow/Padrão/18dp; Cyber Neon = OLED/roxo/glow/Moderno/26dp; Minimal = claro/azul/sem glow/Compacto/12dp; Glass = grafite/azul/glow/Moderno/26dp; Retro = OLED/laranja/sem glow/Compacto/12dp.
- `P7VisualCatalogInstrumentedTest` garante todas as frases e a rejeição de índices inválidos. `P7NavigationInstrumentedTest` abre o Design Studio nativo e confere que as cinco ações preservam papel `Button` com a descrição completa.

## Critérios de validação

- [ ] P7.32 concluída na própria matriz antes de alterar a branch; não cancelar automaticamente sua validação.
- [ ] Source checks e OTA do novo SHA.
- [ ] Android 10/API29 e Android 15/API35 com a instrumentação atualizada, captura sintética protegida, 14 PNGs por API e auditoria cruzada.
- [ ] Verificação humana da confirmação, TalkBack no Galaxy A55 e aprovação 1:1 separada.

**Fronteiras:** melhora apenas explicações, sem alterar a lógica de persistência, dados de APK, SAF, assinatura, build, versionCode ou OTA. PR #13 draft, `main` inalterada, `visual_1to1=NOT_APPROVED` e `physical=NOT_APPROVED`.
