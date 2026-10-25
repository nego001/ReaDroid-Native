# P7.41 — Só marcar como aplicado o tema ou layout realmente salvo

## Problema e correção
O Design Studio permitia marcar com ✓ uma **prévia ainda não confirmada** de Tema ou Layout. O selo era associado ao estado temporário da escolha, não ao valor persistido. O TalkBack também anunciava "prévia selecionada" sem esclarecer se havia sido aplicada.

Agora o selo ✓ de Tema, Layout e Preset é calculado exclusivamente dos valores confirmados em `v3_personalizacao`; a miniatura pré-visualizada conserva seu contorno. Para temas, o ID de miniatura não é índice do catálogo: a comparação é feita com o nome canônico do tema atualmente salvo, evitando um mapeamento de superfícies para o índice errado.

Falas de acessibilidade: "tema aplicado" ou "layout aplicado" para o valor confirmado; "prévia escolhida, ainda não aplicada" para prévias pendentes; "selecionar prévia" para demais opções. O comportamento de presets permanece inalterado.

## Testes e barreiras
Novo teste Android instrumentado `themeAndLayoutBadgesRequireCommittedAppearance` exercita ambos os catálogos reais, o badge antes e após uma escolha pendente e os botões nativos Cancelar. Exige que nenhum valor seja salvo antes de Aplicar ou após Cancelar. O teste fonte exige a regra de selo, a fala e os 38 testes da classe de navegação.

Nova matriz exigida: **157 testes instrumentados por API (1+1+1+38+116)**, 14 capturas por API, 28 capturas e revisão cruzada, 320dp/130%, 200%, Source Checks e OTA. Não altera autorização para assinar, publicar ou instalar APK. Aceite visual 1:1 e Galaxy A55/TalkBack físico ainda pendentes.

**Status:** alteração enviada para validação, ainda sem aprovação instrumental P7.41.
