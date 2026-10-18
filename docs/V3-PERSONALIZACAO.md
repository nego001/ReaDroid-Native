# V3 • Personalização (desenvolvimento em lote)

**Regra de lançamento:** desenvolver e testar na branch `feature/v3-personalizacao`; não promover à branch principal nem anunciar a V3 como lançada antes de concluir os critérios de aceite.

## Escopo
- [x] Paletas OLED, grafite e clara, com persistência local.
- [x] Quatro cores de destaque e restauração das preferências visuais.
- [ ] Aplicar cores corretamente a todas as telas, ícones, gráficos e estados de seleção.
- [x] Ajustes iniciais de densidade e escala de texto nos componentes reutilizáveis.
- [ ] Cobertura de escala tipográfica em todas as telas, leitores e diálogos; auditoria de acessibilidade.
- [ ] Preferências de navegação, atalhos e organização da tela inicial.
- [ ] Prévia visual e identidade (nome/logotipo de exibição, quando viável).
- [ ] Exportação e importação de configurações com validação e sem segredos.
- [ ] Testes Android reais, testes de regressão e auditoria de contraste.
- [ ] Preparar changelog, versão e artefato V3 único.

## Restrições
Não alterar assinaturas, chaves, permissões de segurança nem configurações OTA por personalização. Mudanças de aparência não podem modificar conteúdo de APKs ou resultados de auditoria. Evitar múltiplas publicações da V3: commits internos na branch não são lançamentos.
