# P7.42 — Um único seletor nativo “Ver todos” por vez

## Problema
Os três controles “Ver todos” (Temas, Layouts, Presets) construíam um `AlertDialog` novo a cada ativação. Cliques duplos ou eventos de acessibilidade enfileirados podiam criar seletores sobrepostos e permitir a abertura de outro seletor atrás da confirmação Aplicar/Cancelar.

## Mudança
- Mantém uma única referência `catalogChooser` vinculada à instância corrente do Design Studio e ignora acionamentos enquanto ela está aberta.
- Recusa abrir um novo seletor se já há confirmação ativa de tema, layout ou preset, sem descartar nenhuma janela do sistema.
- Preserva texto, escolha única, títulos, opções, botão “Fechar” e callbacks existentes.
- Limpa a referência no `OnDismissListener`, evitando janela antiga mantida na instância.

## Regressão
`repeatedViewAllNeverStacksNativeCatalogChoosers` passa pelos três controles reais: duas ativações consecutivas, mesmo diálogo ainda visível, título correspondente ao catálogo, nenhuma gravação em `v3_personalizacao`, botão Fechar, diálogo encerrado e referência limpa. Contrato Python exige testagem e guarda; não remove teste algum.

Ao integrar, matriz exigirá **160 instrumentados por Android** (1+1+1+41+116), 14 capturas reais/API e 28 na revisão cruzada. Continua sem homologação de fidelidade visual 1:1, Galaxy A55/TalkBack físico, nem autorização de APK/OTA ou merge.

**Status:** P7.42 preparada separadamente enquanto P7.41.1 aguarda matriz.

Também há regressão que bloqueia Ver todos atrás da confirmação de tema; após Cancelar, verifica que o seletor volta a abrir, sem alterar as preferências.
