# NegrescoDroid | M3.6 — prévia de protótipos e assinaturas de métodos DEX

**Base:** M3.5 (#33), homologada no SHA `f9a57f07f11825971f0f7cabe38d75d9e5391505`. Implementação experimental em PR empilhada; a `main` não é modificada e não há publicação de APK/OTA.

## Escopo implementado

O novo `DexPrototypeProbe` lê **apenas metadados estruturais de DEX v035–v040**, seguindo a cadeia:

`method_id_item.proto_idx` → `proto_id_item` (12 bytes: `shorty_idx`, `return_type_idx`, `parameters_off`) → `type_ids` → `string_ids` → `string_data`.

Opcionalmente, `parameters_off` aponta para uma `type_list`: um tamanho `uint32` e índices `uint16` de tipos. O resultado inclui nomes de métodos da M3.5, tipo de retorno e tipos dos parâmetros, além de uma assinatura DEX como `(ILjava/lang/String;)V`.

**Cuidado:** `method_ids` inclui referências a métodos externos; nem toda assinatura pertence a um método implementado pelo APK.

## Controles e limites

- Amostra de **até 4 métodos** por DEX, lista de **até 8 parâmetros** por assinatura, máximo de **240 unidades UTF-16** por descritor/shorty.
- Leitura somente por `InputStream`, reabrindo a mesma entrada ZIP que passou pelo portão M2, com limite de deslocamento de **16 MiB** e orçamento cumulativo de **64 MiB**; jamais aloca um buffer proporcional ao DEX.
- Verifica índices `proto_idx`, `shorty_idx`, `return_type_idx`, `type_idx` e `descriptor_idx` contra as contagens do cabeçalho; rejeita offsets e contagens falsificados, listas maiores que o limite ou não alinhadas.
- Valida MUTF-8/ULEB128, tipo primitivo, classe e array; proíbe `void` como parâmetro. Confere o texto `shorty` com os tipos de retorno e cada parâmetro.
- Cancelamento é `InterruptedIOException` e deve chegar ao chamador. Tipos ou mapas não suportados produzem `unreadable-prototypes` na prévia, nunca uma assinatura inventada ou execução.
- `SecurityScanner.dexPrototypePreview` inclui até **dois arquivos DEX**; cada resultado é marcado `prototype-signatures-preview` ou `unreadable-prototypes`. A saída registra números, nomes e descritores, não bytecode.

## O que ainda não existe

Não há interpretação de `class_data_item`, `code_item`, corpo de método, instruções, controle de fluxo, desmontagem Smali/Java, recursos compilados, edição DEX, assinatura do APK nem garantia de instalabilidade. O DEX 041 segue não suportado. Os testes usam DEX sintéticos com tabelas coerentes; um proto lido **não prova que o DEX completo é válido**.

## Gates para homologação

A suíte `DexPrototypeProbeInstrumentedTest` cobre retorno e parâmetros (incluindo arrays/objetos), `shorty` contraditório, `void` inválido, contagens e offsets adulterados, MUTF-8, truncamento, cancelamento, limite de amostra e integração com o scanner.

Antes de marcar M3.6 homologada, exigir **M2/M3 Android 10/API29 e Android 15/API35, M1 rebuild/SAF, Source checks e OTA todos verdes no mesmo commit**. PR deve permanecer em rascunho. Não gerar nem distribuir APK/OTA.

Fonte do formato: https://source.android.com/docs/core/runtime/dex-format
