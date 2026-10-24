# P7.40 — Toques repetidos em Temas com confirmação estável

P7.37 (presets) e P7.39 (layouts) impedem empilhamento de confirmações nativas. O catálogo de temas ainda permitia abrir várias janelas do tipo "Aplicar tema?". Além disso, a ação Aplicar lia `selectedTheme` mutável, portanto um segundo clique programático poderia fazer o diálogo visível aplicar um índice diferente do seu título.

## Correção proposta (staging, não integrada)
- Bloquear novas confirmações enquanto `themeConfirmation.isShowing()` for verdadeira.
- Congelar `final int choice = selectedTheme` antes de montar o diálogo, usando o mesmo `choice` para título e aplicação.
- Preservar mensagens, aplicação, recuperação em erro, Cancelar e Back. Liberar referência na dispensa do diálogo.
- Um teste de instrumentação abre um tema real alternativo, exige único AlertDialog após toque duplo, título correspondente, nenhuma preferência persistida, Cancelar, seleção restaurada e handle limpo.
- Teste de contrato do workflow exige a existência da regressão e das guardas, sem tirar testes anteriores. Quando aprovado, seriam **156 instrumentados por API** (1+1+1+37+116), além das 14 imagens por API e 28 imagens da auditoria.
- A P7.40 não autoriza assinatura, instalação, APK/OTA, merge, aceite visual 1:1 ou Galaxy A55/TalkBack.

**Status:** preparada sobre o HEAD P7.39, sem entrar na PR até ela passar em Android 10/15 + cross-review. Testes instrumentados P7.40 ainda não executados.
