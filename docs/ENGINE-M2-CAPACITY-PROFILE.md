# NegrecoDroid | Motor M2.4 — perfil de capacidade e indexação em lote

**Objetivo:** sair de palpites sobre desempenho para medidas reproduzíveis em emuladores Android 10/API 29 e Android 15/API 35. Implementação empilhada sobre a PR M2.3. Nada de merge automático, APK distribuível, OTA ou ajustes visuais.

## Otimização do índice SQLite

`ApkDiskIndex.build` agora executa `CREATE INDEX browse_parent` somente depois da inserção de todas as entradas, antes da validação final da origem e da confirmação do resultado. A chave primária continua impedindo caminhos duplicados. Transações parciais, reserva de armazenamento, tamanho máximo de 128 MiB, interrupção e limpeza de bases incompletas permanecem.

**Hipótese a medir:** construir o índice secundário uma vez reduz escritas/atualizações durante importações com muitos arquivos. Sem medições anteriores equivalentes, ainda NÃO alegar um percentual de melhoria.

## Benchmark sintético instrumentado

`ApkCapacityProfileInstrumentedTest` cria localmente um ZIP com 2.500 arquivos binários de 4 KiB, mais manifesto, DEX e uma pasta explícita vazia (2.503 entradas). O corpus utiliza bytes pseudoaleatórios reproduzíveis (seed fixa) e nunca é publicado.

Registra em `m2-capacity-api-29.json` e `m2-capacity-api-35.json`:

- `wallMs`: duração de cada etapa no relógio monotônico;
- `processCpuMs`: CPU do processo consumida por etapa;
- `javaHeapUsedBytes`: memória do heap Java na amostra final da etapa;
- `nativeHeapAllocatedBytes`: memória nativa alocada na amostra;
- `processPssKib`: memória proporcional residente do processo (PSS) na amostra;
- tamanho do ZIP gerado e contagens verificadas.

Etapas medidas: geração de corpus; admissão ZIP com CRC; prévia JSON limitada; criação do SQLite; busca de arquivo no final do ZIP; metadados de segurança. O teste também confirma:

- CRC/tamanho real da origem; 2.502 arquivos e 2.503 entradas;
- prévia limitada a 120 itens sem perder contagem total;
- navegação até `track_2499.bin` pelo índice;
- preservação de diretório explicitamente vazio;
- scanner limitado a 120 nomes;
- SHA-256 da origem igual antes e depois; exclusão de corpus e SQLite ao terminar.

O workflow M2 disponibiliza apenas relatórios de testes e **métricas JSON**, não publica o ZIP usado no teste.

### Correção da coleta pós-instrumentação

Na primeira execução, os **22 testes Android 10 passaram**, mas a etapa de evidências falhou com `run-as: unknown package: com.readroid.app`, pois `connectedDebugAndroidTest` já havia removido o pacote do emulador antes da leitura do cache privado. A falha foi do coletor pós-teste, não uma reprovação desses 22 casos.

Agora a instrumentação emite uma linha `M2Capacity: RESULT_JSON:{...}` pelo `android.util.Log` antes de finalizar. A CI coleta o filtro estrito de `logcat` e o parser `tools/extract_m2_capacity_logcat.py` aceita **exatamente um** resultado com esquema fechado, corpus sintético, API correta e contagens esperadas. Log bruto não é publicado; somente o JSON filtrado é preservado. Casos negativos do parser rejeitam logs ausentes, duplicados, truncados, de API incorreta e com dados privados extras.

A coleta não depende mais da existência do aplicativo depois que o Gradle desmonta o ambiente instrumentado. O contrato estático `tests/test_engine_m2_capacity_contract.py` impede regressões de ordem ou criação de artefatos indevidos.

## Limitações da evidência

Este é um **teste de estresse sintético com ~10 MiB descomprimidos**, não um APK comercial de 1 GiB. Métricas ao final das etapas não são picos exatos de RAM; carregamento do sistema, compilação/JIT, emulador e armazenamento alteram números. Por isso, os limites de aceitação são **integridade, contagens, indexação correta e conclusão**, não um tempo arbitrário em emulador de CI.

A estratégia ainda não remove o `HashSet` de nomes que `ApkArchiveSafety` usa para detectar duplicatas nem mede consumo máximo em dispositivo físico. A próxima iteração deverá variar cardinalidade, profundidade de caminhos e volume descomprimido antes de considerar elevar qualquer limite.

## Portões de aceitação

Considerar M2.4 validada somente quando `Source checks`, `OTA manifest validation`, `Engine M1` e `Engine M2` estiverem verdes **no mesmo SHA exato**. PRs anteriores permanecem em rascunho, `main` não muda e não há APK instalável/publicado.
