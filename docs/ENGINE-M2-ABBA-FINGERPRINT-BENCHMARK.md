# NegrescoDroid | M2.6 — Benchmark ABBA de nomes ZIP e orçamento de metadados

## Motivação

A M2.5 substituiu o conjunto de nomes ZIP completos por hashes SHA-256/128. No benchmark de 2.503 entradas, a verificação ZIP variou bastante entre Android 10 e Android 15. Os testes de integridade da M2.5 foram aprovados, mas uma execução isolada de cada versão do sistema não demonstra ganho real de CPU ou memória.

## Experimento pareado e reproduzível

`ApkPathBenchmarkInstrumentedTest` gera dinamicamente 8.192 nomes sintéticos com prefixo fixo de 770 caracteres, com a mesma sequência em cada cenário, e mede no mesmo emulador:

1. `A1`: `HashSet<String>`, comportamento anterior;
2. `B1`: `ApkPathFingerprintSet`, comportamento M2.5;
3. `B2`: segunda medição dos fingerprints;
4. `A2`: segunda medição do `HashSet<String>`.

A ordem ABBA ajuda a reduzir distorções de aquecimento e mudança de carga ao longo da execução, mas **não é um ensaio controlado definitivo**. Cada amostra registra tempo decorrido, tempo de CPU, memória Java antes/depois de GC e memória proporcional residente (PSS). O teste confere que **ambos** catalogam precisamente os 8.192 caminhos, sem perda de nomes.

Importante: a medição de memória depende do coletor de lixo e pode inclusive apresentar deltas negativos. Não aplicar limiares de tempo/memória à CI em emuladores. Nenhuma execução publica caminhos, APKs ou dados privados; apenas números, contagem e identificadores de cenário.

## Limites adversariais

`ApkPathBudgetInstrumentedTest` exercita ZIPs reais que devem ser recusados sem extração:

- Um nome acima do limite individual de comprimento;
- 16.385 nomes únicos de 1.024 caracteres (16.778.240 caracteres, acima do limite agregado de 16.777.216), sem ultrapassar o teto bruto de 1 GiB.

Os testes mantêm o limite de 150 mil entradas, CRC, tamanho descompactado máximo de 2 GiB, SHA-256 para caminhos e política de falha fechada em colisões.

## Evidências na CI

O workflow M2 executa M2.1–M2.6 no Android 10/API29 e Android 15/API35. Uma linha `M2Fingerprint: RESULT_JSON` produz o registro pareado ainda durante a instrumentação; o coletor `tools/extract_m2_fingerprint_logcat.py` verifica API, contagens, campos autorizados, ordem ABBA e consistência numérica.

Apenas `m2-fingerprint-api-29.json` e `m2-fingerprint-api-35.json`, os relatórios de capacidade anteriores e os relatórios Android são armazenados como artefatos. O logcat bruto não é publicado. Testes Python cobrem rejeições de dados truncados, duplicados, incompatíveis ou com campos privados.

## Aceitação e ressalvas

- Homologar apenas se a CI M2 atual, a CI M1 herdada, os Source checks e a validação OTA passarem **no mesmo SHA**.
- Mesmo se o fingerprint apresentar menor heap Java em execução pareada, não inferir automaticamente menor **pico** de RAM ou melhora de CPU em todo APK. O ZipFile, o ManifestInspector, o SQLite e a variação de GC continuam relevantes.
- Não alterar `main`, interface, OTA, assinatura nem publicar APK de testes; manter a PR empilhada e em draft.
