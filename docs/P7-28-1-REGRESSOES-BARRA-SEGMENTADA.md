# P7.28.1 — Retorno ao início da barra e contraste real no tema claro

## Resultado real que motivou a correção

O commit P7.28 `c31011145ab9d429b2ea29c7c13a20e28c80cae6` teve **Source checks = success**, **OTA = success**, mas falhou nos jobs instrumentados **Android 10/API29** e **Android 15/API35** da [execução #40059313159](https://github.com/nego001/ReaDroid-Native/actions/runs/40059313159). Foram executados **144 testes por API**, com **2 falhas por API**. A auditoria visual cruzada foi corretamente pulada.

Ambas as falhas pertencem a `P7NavigationInstrumentedTest`:

1. `lightThemeDesignNavigationUsesReadableRealCardSurfaces` esperava fundo opaco (`cardFillColor(false)`) em cada aba **inativa**; porém o novo design usa fundo transparente sobre um único `LinearLayout` de fundo opaco. O teste estava descrevendo a estrutura antiga. Para garantir acessibilidade, a cor de contraste deve usar o **fundo efetivamente visto** do rail, e não a cor `TRANSPARENT`.
2. `narrowDesignKeepsSelectedTabVisible` exigia `scrollX=0` após voltar da última aba para `Temas`, mas recebeu `3` (pixels físicos). Na nova estrutura, a origem do primeiro `TextView` tem deslocamento de `1dp` pelo padding interno e `revealActiveTab()` rolava até a borda da primeira aba, não até a origem do rail.

## Correção restrita e verificável

- `P7DesignStudio.revealActiveTab()`: quando `index == 0`, chama `tabScroller.scrollTo(0,0)`. Para as outras abas, mantém a visibilidade adaptativa já existente, assim como restauração da aba após rotação e navegação por teclado.
- `P7NavigationInstrumentedTest.lightThemeDesignNavigationUsesReadableRealCardSurfaces`: exige **um único rail**, cor opaca da superfície compartilhada, item ativo com preenchimento real, itens inativos transparentes, e contraste >=4.5 **calculado sobre a cor visível** da superfície de cada item. Preserva a transição entre temas/aba Layout.
- `P7NavigationInstrumentedTest.narrowDesignKeepsSelectedTabVisible`: preserva verificação de `scrollX=0` e acrescenta altura mínima >=48dp ao retornar à primeira aba.
- Continuam válidos os contratos P7.28 de quatro abas adjacentes, seleção verdadeira, botão TalkBack, ícones dos criadores e editores funcionais. Não há alterações na persistência, SAF, APK ou lógica de segurança.

## Gates pendentes no novo HEAD

- [ ] Source checks + OTA no SHA da P7.28.1.
- [ ] Matriz instrumentada Android 10/API29 e Android 15/API35 **144/144**, ou diagnóstico explícito se nova falha.
- [ ] Captura real de **14 telas por API**, auditoria cruzada 28/28 e inspeção da faixa no tema claro, 320dp/130%, 200% de texto.
- [ ] TalkBack físico no Galaxy A55 e aprovação humana do visual 1:1.

Sem alteração de `main`, assinatura, versão, APK publicado, OTA ou integração REA. **PR #13 continua draft, `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`**.
