# NegrescoDroid | Motor M3.3 — prévia limitada de índices de classes DEX

**Base:** M3.2/PR #30, aprovada no commit `30c1f643c76ae5c4b877134e6962c13ab3566f26`. Esta PR é experimental; não fazer merge em `main`, publicar APK/OTA ou modificar a interface.

## Implementação

`DexClassDefProbe` lê por `InputStream` uma amostra da tabela `class_defs` de DEX tradicionais versões 035–040. Usa a validação prévia de `DexHeaderProbe`, sem carregar o DEX inteiro ou interpretar o corpo dos métodos.

Cada `class_def_item` tem **32 bytes**, com oito inteiros de 32 bits: `class_idx`, `access_flags`, `superclass_idx`, `interfaces_off`, `source_file_idx`, `annotations_off`, `class_data_off` e `static_values_off`.

O probe impõe:
- no máximo **24 definições de classes** por DEX no resultado;
- offset inicial da tabela a no máximo **16 MiB**, com descarte em blocos de 16 KiB, sem `readAllBytes()`;
- índices `class_idx` crescentes, únicos e estritamente menores que `type_ids_size`;
- `superclass_idx` válido ou o valor especial `NO_INDEX`;
- `source_file_idx` válido ou `NO_INDEX`;
- offsets de `interfaces`, `annotations`, `class_data` e `static_values` iguais a zero (ausentes) ou dentro da região de dados já validada, com alinhamento mínimo de 4 bytes quando necessário;
- cancelamento via `InterruptedIOException`, sem ler partes não necessárias do arquivo.

O novo `SecurityScanner.dexClassPreview` mostra até **quatro DEX**, com até 24 itens por arquivo. Cada item contém apenas números e metadados declarados. O relatório informa `declaredClasses`, `previewTruncated` e `dexClassPreviewTruncated`. Entradas inválidas geram `unreadable-class-index` sem derrubar o scanner. Interrupções continuam sendo propagadas.

## O que não comprova

- Não decodifica nomes de classes, strings, métodos, bytecode, anotações ou recursos compilados.
- Não garante consistência de **todas** as classes quando a tabela é maior que a amostra; as demais não são lidas.
- O status `class-index-only` não comprova validade do DEX completo ou instalabilidade de um APK.
- Não muda o limite ZIP de 1 GiB de importação, a leitura CRC da M2, a transação M1 ou assinatura de pacotes.
- DEX 041 é propositalmente não suportado nesta fase, pois exige regras de contêiner diferentes.

## Critérios de aceite

A suíte `DexClassDefProbeInstrumentedTest` cobre amostras válidas, ordenação, 26 classes com limite de 24, índices forjados, regiões de dados inválidas, truncamento, restrição de leitura, cancelamento e integração com scanner/ZIP.

A execução Android 10/API29 e Android 15/API35 herda todos os testes M1, M2, M3.1 e M3.2. Source checks e OTA devem estar verdes **no mesmo SHA**. Se falhar, manter a PR em rascunho e corrigir antes de homologar.

Referência do formato: https://source.android.com/docs/core/runtime/dex-format
