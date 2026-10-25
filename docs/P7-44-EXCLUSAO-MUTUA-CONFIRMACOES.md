# P7.44 — Exclusão mútua das confirmações de aparência

## Problema
P7.37, P7.39 e P7.40 impediam duplicatas **dentro** da mesma família (Preset, Layout, Tema). P7.42 também impedia abrir "Ver todos" atrás de um diálogo. Mas toques rápidos enfileirados em elementos diferentes do Design Studio podiam abrir, por exemplo, a confirmação de Layout enquanto a confirmação de Tema ainda estava ativa. Isso permitia janelas sobrepostas e uma seleção visual temporária que continuava destacada após bloquear uma ação.

## Correção proposta
O predicado `appearanceDialogShowing()` verifica os quatro diálogos reais do Studio: confirmação de Tema, Layout, Preset e seletor "Ver todos". Os três caminhos `applySelectedTheme`, `confirmLayout` e `confirmPreset` o consultam antes de abrir nova confirmação; quando bloqueados, restauram sua própria prévia ao valor persistido e atualizam a interface. A confirmação já aberta continua intocada; nenhum botão Aplicar ou Cancelar é pressionado automaticamente e nenhuma preferência é salva.

Novo teste instrumentado `crossFamilyAppearanceConfirmationsNeverStackOrLeavePhantomPreview`: abre confirmações reais alternadas das três famílias, aciona os outros cartões enquanto cada uma está visível, exige ausência de confirmação concorrente e que nenhum valor do mapa de personalização seja gravado. Cancela as confirmações para liberar a sequência. O contrato fonte espera 43 métodos de navegação, portanto **162 instrumentados por API** (1+1+1+43+116), além das capturas 14/API e auditoria 28/28, compactação e fontes.

**Estado:** P7.44 em staging sobre P7.43; não incorporada nem aprovada no emulador. PR #13 draft, main intacta, nenhuma publicação APK/OTA; fidelidade visual 1:1 e Galaxy A55/TalkBack físico pendentes.
