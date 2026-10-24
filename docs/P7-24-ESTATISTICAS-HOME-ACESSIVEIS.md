# P7.24 — Home: quatro métricas reais faladas como pares completos pelo TalkBack

**Repositório:** `nego001/ReaDroid-Native`, branch `feature/p7-negrecodroid-visual-foundation`, PR #13. **Fase:** P7 visual e acessibilidade.

## Problema concreto

Os quatro cartões exibiam valores e títulos em `TextView` independentes. No leitor de tela, `—` (métrica indisponível) não fornece contexto, e ouvir título/valor separadamente pode levar a interpretações erradas. Os resultados de builds e ameaças **não têm contadores comprovados**; anunciá-los como `0` seria falsear o estado do aplicativo.

## Alterações implementadas

- `P7HomeOverview` mantém referências dos quatro cartões, configura cada um como grupo acessível focável e atualiza seu `contentDescription` com **rótulo e valor verdadeiro**: `Projetos: N`, `Arquivos: N`, `APKs Builds: não disponível`, `Ameaças: não disponível`.
- Os elementos de texto continuam **visíveis e idênticos**, mas são omitidos como nós acessíveis individuais para não duplicar a leitura. Ícones decorativos já eram omitidos.
- `updateAccessibleStats()` é invocado após `renderHistory()`; logo, mudanças no relatório da sessão, abertura/fechamento e alteração no histórico renovam o anúncio juntamente com os números reais.
- Não transforma o cartão em botão: é **somente informativo**, sem ação falsa. Foco é compatível com navegação de teclado/leitor de tela.
- `P7HomeOverviewInstrumentedTest.statisticsSpeakVerifiedValuesAndExplicitlyUnknownMetrics` verifica árvore de nós real no Android, não apenas strings: estado vazio (0 projetos, arquivos desconhecidos), entrada sintética com `fileCount=301`, atualização de projetos da sessão, retorno ao vazio, sem duplicidade textual e sem clickability inventada.

## Gates de qualidade

- [ ] CI Android API29/API35 com o teste novo **e toda a regressão P7.21–P7.24**.
- [ ] Verificar capturas de 14 cenários por API e relatório visual cruzado.
- [ ] Comparar três telas com os **dois PNGs originais oficialmente versionados**; equivalência 1:1 requer inspeção humana.
- [ ] TalkBack manual e validação física no Galaxy A55.
- [ ] Respeitar `visual_1to1=NOT_APPROVED` e `physical=NOT_APPROVED` até aceite.

**Restrições:** somente representação e acessibilidade nativa; nada de tocar em arquivos de projeto, operações do APK, chaves, permissões SAF, assinatura, build, versionCode ou OTA. Não fazer merge para a `main` ou gerar APK de distribuição para mudanças pequenas.
