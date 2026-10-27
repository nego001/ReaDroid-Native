# NegrescoDroid PE-A4.4 | Possíveis destinos de chamadas calculadas com prova explícita

## Motivação

A PE-A4.3 foi homologada em Ghidra 12.2 após repetição de um job cancelado (Actions #40425835633): o PE sintético tinha dois locais de chamadas calculadas em `inspect_path`. Ambos apareciam como destino desconhecido, corretamente. A nova etapa só pode acrescentar um destino quando houver **referência de chamada explícita e única** para um ponto de entrada de função interna no modelo estático do Ghidra.

## Regras do exportador

- Mantém a janela de até 512 funções, 16 pseudocódigos e 8 locais de chamadas calculadas por função, bem como cotas anteriores de CPU, tempo, strings e relatório.
- Para cada instrução identificada como CALL calculado, verifica no máximo 16 referências da instrução. Requer que o Ghidra marque a referência como **CALL**, que o endereço de destino seja de memória e que exista uma função interna no **ponto de entrada exato** desse endereço. Ignora funções externas e thunks.
- Se aparecerem referências para destinos internos distintos, **não declara um alvo único**. Se a janela de referências exceder 16, não aceita uma aparente unicidade baseada num conjunto incompleto.
- Exporta somente candidatos provados pelo grafo estático no campo `explicit_computed_targets`: local da instrução, endereço de entrada, nome encontrado e a origem `ghidra_unique_explicit_internal_call_reference`. O atributo `computed_call_destinations=explicit_references_only` descreve a **política**, não diz que todos os locais tenham destino.
- O validador Python verifica que os endereços são hexadecimais, o local está entre os CALLs calculados observados, o nome não contém caracteres de controle, os dados não se repetem e a origem é a esperada.
- O relatório explicativo separa `explicit_reference_candidates` e `unknown_destination_sites`. Um candidato estático **não prova que o programa chamou essa função em execução**, nem se torna uma hipótese comportamental sem as evidências WinAPI já exigidas na PE-A4.

## Testes e limites

Os testes sintéticos de estruturas JSON verificam sucesso de um candidato único, rejeição de endereço externo ou local inventado, duplicidade, origem falsa e ausência de classificação comportamental. A CI Ghidra 12.2 com PE sintético conserva os gates da PE-A4.3: duas chamadas calculadas em `inspect_path`, string de teste e categoria `filesystem_inspection`. **Não exige que algum computed CALL tenha referência explícita resolvida**, pois o Ghidra pode legitimamente não conseguir resolver um ponteiro; essa ausência não é erro de análise.

Esta etapa não usa heurísticas especulativas, exploração dinâmica nem reconstrução completa de código-fonte. O motor continua limitado à amostra, sem análise do IObit Uninstaller real. Sandbox Bubblewrap ainda exige prova funcional em Linux antes de uso fora de VM com binários potencialmente hostis. A PR fica Draft sobre PE-A4.3 (#45); `main`, APK e OTA permanecem intactos.

Fontes técnicas: https://ghidra.re/ghidra_docs/api/ghidra/program/model/listing/Listing.html e https://ghidra.re/ghidra_docs/api/ghidra/program/model/symbol/FlowType.html