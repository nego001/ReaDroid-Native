# NegrescoDroid | PE-A3: pseudocódigo e relações de chamadas

## Entrega

Base: PE-A2.1 (PR #39). O novo script Java NegrescoDeepPreview usa Ghidra Headless e DecompInterface para recuperar uma prévia limitada do código C reconstruído e das funções chamadas. Não executa o PE Windows. Pseudocódigo gerado é inferência técnica, não código original verificado nem prova da finalidade real da rotina.

Limites do exportador: até 256 funções percorridas, 8 funções não-thunks decompiladas, 12 chamadas diretas por função, 1.800 caracteres de pseudocódigo por função e 12 segundos de descompilação por função. Os dados carregam status de recuperação, truncamentos, endereço de entrada e a proveniência obrigatória ghidra_heuristic_not_original_source.

## Integração

O runner pe_auto_ghidra.py suporta --deep-preview: após a autoanálise do Ghidra, executa tanto NegrescoFunctionInventory.java quanto NegrescoDeepPreview.java no mesmo projeto. Ele valida independentemente a saída profunda, limitando-a a 64 KiB, com contagem, endereços, arestas, origem, status e tamanho. Quando a saída não existe ou está inconsistente, não produz relatório final de sucesso. O JSON final agrega deep_preview e declara bounded_heuristic_preview e bounded_direct_references. Caso a opção não esteja ativa, preserva o comportamento da PE-A2.

O modo normal mantém Bubblewrap obrigatório por padrão; o Ghidra real usado na CI inspeciona exclusivamente um executável sintético confiável, com opção explícita de teste sem sandbox. Não foi realizado teste de isolamento funcional do Bubblewrap; não usar com executáveis hostis fora de uma VM descartável.

## Interpretação

Uma aresta em calls é somente referência estática identificada pelo Ghidra. Não afirma que a chamada seja executada na prática. A amostra de 8 funções não cobre necessariamente as rotinas mais importantes. O pseudocódigo pode conter nomes temporários, tipos estimados, branches inexatos e trechos incompletos, especialmente em código ofuscado, empacotado ou otimizado.

Não há ainda identificação automática do propósito real dos métodos, IA de classificação, desmontagem de instaladores embalados, suporte Windows do worker ou interface de um clique. O IObit Uninstaller real ainda não foi submetido ao analisador.

## Gates

Os testes sintéticos verificam limites de pseudocódigo, endereços duplicados, arestas, proveniência, falhas de compilação, ausência de saída, incompatibilidade de status e integração do comando. A CI Ghidra 12.2/JDK25 com fixture Windows deve demonstrar pelo menos uma função decompilada com pseudocódigo não vazio. Além disso, exigir Source checks e OTA verdes no mesmo SHA e manter PR Draft sem merge/publicação.

Referências oficiais:
- https://ghidra.re/ghidra_docs/api/ghidra/app/decompiler/DecompInterface.html
- https://ghidra.re/ghidra_docs/api/ghidra/app/decompiler/DecompileResults.html
- https://www.ghidradocs.com/12.0_PUBLIC/docs/GhidraAPI_javadoc/api/ghidra/program/model/listing/Function.html