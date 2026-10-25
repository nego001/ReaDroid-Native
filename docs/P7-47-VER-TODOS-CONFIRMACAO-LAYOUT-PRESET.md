# P7.47 | Ver todos não atravessa confirmações de Layout e Preset

## Falha de cobertura
P7.42 confirmava o bloqueio do botão **Ver todos** durante a confirmação de Tema, e a implementação também continha guardas para Layout e Preset. Mas só o comportamento do Tema tinha um teste que exercia bloqueio e recuperação depois de Cancelar.

## Instrumentação adicionada
Dois testes Android: `viewAllWaitsForLayoutConfirmationAndRecoversAfterCancel` e `viewAllWaitsForPresetConfirmationAndRecoversAfterCancel`. Cada um usa a Activity e o `P7DesignStudio` reais. Escolhe uma opção diferente da persistida, confirma que a janela Aplicar está aberta e tenta abrir **os três catálogos** por trás dela, verificando que nenhum catálogo aparece, a janela original continua sendo a mesma, e o mapa `v3_personalizacao` permanece idêntico. Depois clica Cancelar, espera `OnDismiss` e verifica a liberação das referências. Finalmente abre e fecha normalmente os três catálogos, esperando o processamento das filas e rechecando a persistência.

A implementação do app não muda. A contagem de navegação cresce de 42 para **44**, com **164 instrumentados por API** (`1+1+1+1+44+116`), 14 evidências/API e 28 cross. Sem skip, retry automático ou bypass de captura. O contrato fonte exige os dois testes, as proteções de estado e a nova contagem.

**Estado:** inicialmente em staging, sem aprovação até CI de Source, OTA, Android29, Android35 e auditoria cruzada concluir. PR em rascunho; main intacta; visual 1:1 e Galaxy A55/TalkBack físico pendentes.
