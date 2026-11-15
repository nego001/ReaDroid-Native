# P7.50.6 — menu de três pontos funcional no cabeçalho do Design Studio

## Origem visual (25/10/2026)

A arte **oficial** `design/reference/p7/negrecodroid_controle_total_de_apks.png` mostra, no topo do terceiro telefone (Design Studio), um ícone vertical de três pontos do lado direito. Nas capturas reais P7.50.5 `p7-design-android-29.png` e `...35.png` há ícone de paleta, título e subtítulo, mas **não havia a ação de menu correspondente**. Não substituir esse controle por símbolo sem função.

## Implementação nativa

- Cabeçalho mantém paleta, títulos e hierarquia de acessibilidade; a coluna de texto usa peso elástico, reservando exatamente **48 dp** para `Mais opções do Design Studio` no lado direito.
- O botão é `TextView` visual com `⋮`, descrito como **Button** para TalkBack, foco de teclado e alvo mínimo **48 × 48 dp**.
- Um `android.widget.PopupMenu` Android real oferece **somente fluxos existentes**: `Catálogo de temas` → catálogo/confirmar atual; `Criador de ícones` → oficina real; `Logo Studio` → oficina real. Reutiliza `showCatalogDialog(0)` e `open(-4/-5)`, sem ações inventadas, permissões novas nem reimplementar lógica de exportação.
- Proteção contra popup duplicado e contra apresentação simultânea com confirmação de aparência. O popup é descartado ao sair; abertura do destino ocorre em callback da UI após o evento de seleção. Somente abrir ou cancelar **não altera preferências**.
- Como o menu aparece no topo da página, o teste de alvo não precisa de APK sintético ou arquivo SAF; todos os controles existentes continuam alcançáveis.

## Testes obrigatórios

- Novo `P7NavigationInstrumentedTest.designOverflowIsRealAccessibleMenuAndCatalogOpensWithoutApplying` abre a Activity real, verifica descrição, role Button, mínimo 48dp, PopupMenu nativo de três ações, acionamento real do catálogo, cancelamento e **ausência de gravação** em `v3_personalizacao`.
- Gate Python `test_p7_capture_runner.py` passa de 46 para **47** métodos `@Test` de navegação, sem remover teste anterior.
- **Meta total da matriz:** **170 testes instrumentados/API** (seis sessões individuais + 47 navegação + 117 restantes), 14 PNG/API (28 ao todo), cross-api, 320dp/130%, fonte 200%, reboot API35, Source e OTA.
- **Não aprovar** sem resultados verdes no SHA exato. Contrato visual 1:1 integral e Galaxy A55 físico/TalkBack permanecem pendentes.

Estado inicial: branch staging baseada na P7.50.5 verde `824978c0`. PR #13 draft, `main` intacta, nenhuma publicação APK/OTA.
