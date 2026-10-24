# P7.41 — Aplicação de Tema não pode mudar com segundo toque

## Falha evitada

A P7.40 congela `final int choice` no momento da confirmação; o teste de toques repetidos confirma apenas que existe um diálogo e que Cancelar não grava preferências. O cenário com dois temas **diferentes** seguido por Aplicar exige um teste integrado do resultado persistido.

## Cenário Android real

1. Abrir MainActivity e o Design Studio, guardar todas as preferências de aparência atuais.
2. Escolher um tema A diferente do salvo e confirmar que um AlertDialog nativo mostra exatamente o nome de A.
3. Simular clique já enfileirado num cartão de tema B diferente de A, usando a instância de View anterior a `render()`.
4. Exigir o **mesmo** diálogo, sem alteração em `v3_personalizacao`.
5. Pressionar **Aplicar** no diálogo original, aguardar ocioso após `Activity.recreate()` e ler `P7ThemeCatalog.currentTheme(context)` do armazenamento real. Só **A** pode estar salvo; B deve ser rejeitado.
6. Restaurar em `finally` as chaves `theme`, `accent`, `studio_glow` e `p7_active_preset` ao estado inicial; conferir todo o mapa de preferências, evitando contaminar os demais testes.

O contrato Python exige a regressão instrumental adicional: **38 métodos de navegação**, totalizando **157 por Android** (`1+1+1+38+116`), preservando todos os PNGs e validações. Nenhuma mudança em código de produção, assinatura, APK, OTA ou `main`.

**Status:** staging isolado; nunca tratar como aprovado antes da matriz Android10+15 e auditoria de 28 capturas. Visual 1:1 e Galaxy A55/TalkBack permanecem não homologados.
