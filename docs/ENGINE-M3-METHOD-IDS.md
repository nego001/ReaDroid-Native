# NegrescoDroid | Motor M3.5: prévia segura dos identificadores de métodos DEX

**Base homologada:** M3.4, PR #32, commit `7d5778c0416e3c1f4896d3e55201633c42a05228`.

## Objetivo

Na especificação Dalvik/DEX, cada `method_id_item` tem **8 bytes**: `class_idx` (ushort), `proto_idx` (ushort) e `name_idx` (uint). A tabela contém métodos **definidos ou apenas referenciados** pelo arquivo DEX. Uma entrada na tabela **não significa** que existe um corpo de método implementado naquele APK.

A implementação `DexMethodProbe` oferece uma prévia com até **8 identificadores** por DEX tradicional 035–040, recuperando nomes por `string_id_item` e `string_data_item` usando MUTF-8. Exibe índice de método, índice do tipo declarador, índice do protótipo, índice da string e nome resolvido. Não interpreta protótipos completos, `class_data` ou `code_item`.

## Regras de leitura e segurança

- Cabeçalho verificado por `DexHeaderProbe`. `method_ids_size` e `method_ids_off` vêm apenas do cabeçalho validado.
- Para cada registro de 8 bytes, `class_idx` precisa existir em `type_ids`, `proto_idx` em `proto_ids` e `name_idx` em `string_ids`.
- Entradas lidas são comparadas pela ordem normativa: tipo declarador, nome e protótipo. Repetições e regressões de ordem são recusadas.
- Cada posição de leitura alcançada por streaming é limitada a **16 MiB**, com **32 MiB cumulativos** por operação, blocos de 16 KiB, checagem de progresso e cancelamento por `InterruptedIOException`.
- Nomes têm no máximo **128 unidades UTF-16**; ULEB128, MUTF-8 e terminador NUL precisam ser coerentes. Aceita construtores `<init>` e `<clinit>` e identificadores Unicode compatíveis com a prévia. Outros formatos ainda não suportados aparecem como indisponíveis, sem bloquear a admissão ZIP.
- Cada releitura reabre a mesma entrada ZIP já verificada pela admissão M2. Nenhum DEX completo é carregado na RAM; bytecode não é interpretado/executado.
- `SecurityScanner.dexMethodPreview` mostra no máximo **2 DEX**, 8 nomes por arquivo. Status `method-ids-preview` ou `unreadable-method-ids`, mais flag `dexMethodPreviewTruncated`.

## Evidência e critérios de aceite

`DexMethodProbeInstrumentedTest` exercita nome ASCII, Unicode/MUTF-8, construtor, metadados de método, ordenação/duplicata, índices corrompidos, campos inválidos, strings truncadas, limite de amostra de 8, cota de offset, cancelamento e integração com o scanner.

O workflow M2/M3 roda as suítes existentes com o novo teste no Android 10/API29 e 15/API35; M1 (rebuild e SAF), Source checks e OTA devem ser **todos aprovados no mesmo commit** antes da homologação. Os testes operam sobre corpus sintético. A saída da CI mantém apenas relatórios, nunca APK/DEX brutos.

**Limites:** DEX 041 não suportado; não há descompilação, assinatura, análise de comportamento, prova de instalabilidade, leitura integral dos métodos ou garantia de que IDs exibidos sejam implementações locais. `main`, a interface visual e canais de publicação ficam intactos.

**Especificação oficial:** https://source.android.com/docs/core/runtime/dex-format
