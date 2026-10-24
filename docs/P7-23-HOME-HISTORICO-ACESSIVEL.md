# P7.23 — Home: ações dos projetos recentes com papel de botão

**Escopo:** continuação da P7 visual na PR #13, sem APK/release.

## Problema confirmado no código

`P7HomeOverview` exibia `Ver todos ›` e `⋮` dos projetos recentes como `TextView` com listeners, foco e `contentDescription`, mas não expunha a **classe acessível Button** no `AccessibilityNodeInfo`. Isso dificultava perceber que as ações eram botões ao usar TalkBack. O problema é análogo ao menu do Explorador resolvido na P7.22.

## Alteração aplicada

- Helper `exposeAsButton(View)` marca ações como importantes para acessibilidade e fornece `android.widget.Button` como classe no nó Android, preservando os elementos gráficos e os callbacks.
- `Ver todos os projetos recentes` anuncia botão ao existir histórico. Continua oculto no estado vazio e abre o histórico real; **nenhum registro falso** é gerado para exibir o link.
- `Mais opções de <nome>` anuncia botão independente do toque na linha do histórico. O menu continua contendo **Abrir projeto** e **Remover do histórico**; a confirmação preserva o APK original e altera apenas a referência SAF.
- Teste `P7HomeOverviewInstrumentedTest` verifica os dois nós reais: classe acessível, conteúdo, `isClickable`, foco, alvo mínimo e preservação do callback `Ver todos`.
- Preservadas cores, posição, dimensões, nome/ícone reais dos APKs, histórico autorizado, `RecoveryVault`, importação/exportação e versão do app.

## Critérios que ainda precisam ser comprovados

- [ ] Matriz Android 10 (API29) e 15 (API35) totalmente verde no HEAD P7.23, incluindo a P7.21 e a P7.22.
- [ ] 14 screenshots verificadas por API e painel cruzado, com os dois PNGs originais de referência.
- [ ] Conferência de TalkBack manual no Galaxy A55 de `Ver todos`, `⋮`, abrir e remover sem apagar APK.
- [ ] Revisão 1:1 de Home, Explorador e Design Studio aprovada pelo proprietário.

**Gates:** `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`. Não fazer merge na `main`, não gerar APK de distribuição nem publicar OTA automaticamente.
