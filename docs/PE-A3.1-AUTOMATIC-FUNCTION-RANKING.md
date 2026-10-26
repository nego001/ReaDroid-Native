# NegrescoDroid | PE-A3.1: priorização automática de funções e referências

## Objetivo

Selecionar, sem operações manuais, funções potencialmente interessantes dentro de um executável PE32/PE32+ analisado pelo Ghidra Headless. O mecanismo prioriza **conectividade de chamadas dentro de uma amostra limitada** e algumas pistas fracas de nomes (como `main` e `WinMain`). Isso NÃO é uma classificação do comportamento da função nem prova de que uma rotina foi executada.

## Mudanças técnicas

- O exportador `NegrescoDeepPreview.java` agora examina até **384 funções** em ordem de endereço, não apenas as oito primeiras. Ignora thunks e seleciona até **12 funções** para decompilação.
- Para até **64 referências diretas** por função examinada, calcula conectividade observada dentro da própria amostra: `sample_inbound_count` e `direct_callee_count`. Pontuação heurística determinística: `4 × min(16, inbound) + 2 × min(16, chamadas) + dica fraca do nome (0/5/20)`.
- Estabelece ordem estável decrescente por `selection_score` e desempate pelo endereço da função. Mostra `selection_rank`, score e contagens de conexões, sempre com `graph_scope=scanned_functions_only`.
- Cada função selecionada mostra até **24 chamadas diretas**, informa truncamento e marca `calls_status=unavailable` quando referências não são obtidas.
- Decompila no máximo **12 funções**, até **10 segundos por função**, exportando até **1.800 caracteres de C heurístico** por item. O pseudocódigo NÃO é fonte original.
- O novo esquema `ghidra_deep_preview_v2` preserva `ghidra_heuristic_not_original_source`; o Python rejeita scores incoerentes, classificações inventadas, falsos contadores, dados desordenados e amostras superiores às cotas. Limites: **64 KiB** para evidência profunda e **128 KiB** para relatório.

## Interpretação correta

A pontuação é uma indicação de prioridade para análise automática, **não de confiança** de que o código representa uma função de desinstalação, limpeza ou proteção. O ranking pode favorecer bibliotecas de inicialização do Windows/CRT, assim como ignorar funções importantes fora da amostra de 384. As chamadas são referências estáticas observadas pelo Ghidra, não execução dinâmica.

## Segurança e testes

O modo padrão continua exigindo isolamento Bubblewrap, cuja eficácia efetiva ainda não foi homologada. A CI com Ghidra **real 12.2/JDK 25** utiliza apenas uma fixture PE sintética e a exceção de teste confiável sem sandbox. Nenhum executável de terceiros é instalado ou executado. A PR fica Draft e não há merge na `main`, APK ou OTA.

Critérios: testes sintéticos do parser/runner/relatórios aprovados, CI Ghidra real demonstrando pontuação ordenada e pseudocódigo, Source checks e OTA no mesmo SHA. A próxima PE-A4 poderá classificar hipóteses de funcionalidades a partir das evidências recuperadas, com justificativa e níveis de confiança. Antes de lidar com binários hostis fora de VM, validar sandbox efetiva.