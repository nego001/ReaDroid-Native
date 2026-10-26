# NegrescoDroid | M2.7 — tabela primitiva de caminhos ZIP

**Objetivo:** reduzir a memória permanente do conjunto de fingerprints SHA-256/128 usado na admissão ZIP, mantendo igualdade exata dos dois `long` e o limite de 150 mil caminhos.

## Mudança implementada

O motor M2.5 mantinha `HashSet<Fingerprint>`. Ele já evitava guardar nomes completos, mas ainda criava um objeto `Fingerprint` e a infraestrutura do `HashSet` por entrada.

A M2.7 usa uma tabela hash com endereçamento aberto, composta por três arrays de tipos primitivos:

- `long[] high` e `long[] low` armazenam as duas palavras do SHA-256 truncado a 128 bits;
- `byte[] occupied` diferencia posições vazias até mesmo do fingerprint composto por dois zeros;
- crescimento progressivo em potências de dois, mantendo carga abaixo de 70% e o teto de 150 mil entradas.

Um conflito no índice da tabela **não** rejeita uma entrada diferente. O código sonda a próxima posição e só considera duplicado quando **as duas palavras de 64 bits coincidem**. Uma colisão criptográfica de 128 bits entre nomes distintos continua sendo rejeitada de modo conservador, nunca aceita como dois caminhos diferentes.

O buffer de digest de 32 bytes é reutilizado por instância, reduzindo alocações temporárias por nome. A API pública de admissão ZIP não muda.

## Testes e evidências

- `ApkPrimitiveFingerprintInstrumentedTest`: 20.000 nomes e crescimento, duplicata no fim da tabela após vários redimensionamentos, sensibilidade a caixa, entradas vazias/Unicode e confirmação do limite exato de 150.000 nomes (150.001º rejeitado).
- A suíte de proteção ZIP e o teste de 16 Mi caracteres totais continuam em vigor.
- O benchmark ABBA anterior continua medindo `HashSet<String>` contra a implementação corrente de `ApkPathFingerprintSet` no **mesmo** emulador; dessa forma as métricas de M2.7 podem ser confrontadas com as de M2.6, mas com incertezas de GC, carga do host e inicialização.
- O contrato `tests/test_engine_m2_primitive_fingerprint_contract.py` protege arrays primitivos, unicidade, crescimento, limites e integração CI.
- A matriz Android 10/API29 e Android 15/API35 e os portões M1, Source checks e OTA permanecem obrigatórios.

## Limitações

A tabela primitiva não muda o teto de 1 GiB de APK nem 2 GiB de conteúdo inflado. O `ZipFile`, `getBytes(UTF-8)`, parser Android e SQLite ainda alocam memória. A quantidade de bytes nos arrays **não equivale ao pico de RAM do processo**. A alteração também não transforma ZIP reconstruído em APK assinado/instalável.

## Aceitação

Somente declarar M2.7 aprovada quando M1, M2, Source checks e OTA estiverem verdes no mesmo commit. Manter PR em rascunho, sem publicação de APK/OTA ou merge em `main`.
