# P7.43 — Seleção real nos três catálogos, com confirmação obrigatória

A P7.42 impede empilhamento de diálogos “Ver todos”. O passo seguinte valida também o comportamento operacional do seletor: um toque em item de Tema, Layout ou Preset **não pode salvar** antes da confirmação nativa Aplicar, e Cancelar deve deixar todas as preferências intactas.

## Novo teste Android
`catalogSelectionsRequireNativeConfirmationBeforeSaving` abre a aba Design real, percorre os três catálogos via “Ver todos”, exige lista nativa com número correto de opções, seleciona uma opção diferente da aplicada, verifica que o seletor fecha e abre o diálogo Aplicar da família certa com título exato, e que nenhum valor em `v3_personalizacao` foi salvo antes da confirmação. Clica Cancelar, aguarda o loop Android, exige as quatro referências de diálogos limpas e o mapa inteiro de preferências idêntico ao inicial.

Não altera código de produção nem permite publicação. Exigência prevista **161 testes instrumentados por API** (1+1+1+42+116), com 14 capturas/API, 28 cross-review, 320dp/130%, 200% e todos os outros gates existentes.

**Status:** staged, ainda não integrado à PR #13 nem executado em emulador; requer matriz P7.42 completa verde antes de entrar. Aceite visual 1:1 e Galaxy A55/TalkBack continuam pendentes.
