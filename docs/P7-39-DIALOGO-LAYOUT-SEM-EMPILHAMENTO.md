# P7.39 — Impedir confirmações duplicadas ao aplicar Layout

## Motivação
A P7.37 impede empilhamento de confirmações para presets, mas confirmLayout() criava novo AlertDialog em cada toque. Cliques repetidos poderiam deixar uma segunda confirmação atrás da primeira, mesmo sem salvar alterações.

## Alteração de produção e regressão
- Guardar layoutConfirmation apenas na instância atual; não abrir diálogo extra quando já houver confirmação visível.
- Manter exatamente o texto, os botões e callbacks de Aplicar / Cancelar / Back anteriores.
- Limpar a referência no OnDismissListener. Cancelar restaura selectedLayout ao valor realmente salvo.
- Novo teste instrumentado repeatedLayoutTapNeverStacksNativeConfirmations abre Design, escolhe layout alternativo, toca duas vezes no cartão, exige a mesma instância e nenhum salvamento de v3_personalizacao, cancela e verifica referência limpa e estado anterior.
- Contrato Python exige guarda, limpeza e presença da regressão. Nenhum APK de usuário, build, assinatura ou OTA alterados.

## Critérios
Integrar somente depois de a matriz P7.38 estar verde. Ao entrar, a matriz passa a 155 testes instrumentados/API (1+1+1+36+116), preservando 14 capturas/API e cross-review 28/28. Visual 1:1 e Galaxy A55/TalkBack permanecem pendentes.

**Status:** preparação isolada; ainda não testada em emulador nem incorporada à PR #13.
