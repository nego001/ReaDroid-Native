# NegrescoDroid | M3.4 — nomes de classes DEX com leitura limitada

**Base:** M3.3 (PR #31) homologada no SHA `bf533a7a1059659d96ea3f232c9fb14da7c380a6`. PR empilhada, em rascunho; sem merge, distribuição de APK, OTA, assinatura ou alteração de interface.

## Objetivo

As etapas M3.1–M3.3 mostravam cabeçalhos, seções e números de `class_def_item`, mas ainda não resolviam os nomes das classes. A M3.4 lê os índices de tipos e strings do DEX e resolve um pequeno conjunto de nomes, permanecendo **somente leitura**, com consumo e tempo de processamento delimitados.

A cadeia de resolução é:

`class_def_item.class_idx` → `type_id_item.descriptor_idx` → `string_id_item.string_data_off` → `string_data_item` (comprimento `uleb128` + **MUTF-8** + NUL).

A implementação `DexClassNameProbe` reabre fluxos da **mesma entrada ZIP previamente aprovada na admissão M2** para leituras esparsas. Não extrai, executa ou carrega o DEX inteiro. Checa os limites das seções no cabeçalho, índices dentro de `type_ids_size`/`string_ids_size`, referências dentro de `data_off/data_size`, comprimentos de strings, codificação modificada UTF-8 (inclusive UTF-16/surrogates) e sintaxe básica de descritores de classes.

## Restrições deliberadas

- Até **6 nomes por DEX** e somente os **primeiros 2 DEX** no relatório de segurança.
- Cada deslocamento de leitura individual fica limitado a **16 MiB**; orçamento cumulativo de **64 MiB** de bytes percorridos/consumidos por prova de nomes.
- Comprimento de cada descritor limitado a **240 unidades UTF-16**. Se o arquivo tiver strings mais distantes ou longas, a prévia indica que elas não são suportadas em vez de ultrapassar o orçamento.
- O leitor retorna os descritores no formato `Lpacote/Classe;` e nomes de visualização como `pacote.Classe`. Não inventa nomes a partir de índices que não pôde resolver.
- `DexClassDefProbe` limita a amostra da tabela, os leitores anteriores continuam válidos e a interrupção da tarefa mantém `InterruptedIOException`.
- `SecurityScanner.dexClassNamePreview` tem `class-names-preview` para resolução limitada e `unreadable-class-names` quando o formato, a referência ou a cota não permitem resolver nomes. Nunca trata isso como prova de APK malicioso.
- O corpus de testes é sintético. String Unicode válida em codificação MUTF-8 é permitida; índices fora de limite, codificação inválida, truncamento, NUL prematuro, string com dimensão forjada e caracteres incompatíveis com descritor de classe são rejeitados.

## Limites de interpretação

Este **não é um descompilador**: não identifica o comportamento de métodos, não reconstrói Java/Smali, não interpreta corpo de DEX, não decodifica Manifest/recursos, não verifica todas as classes ou assinatura. Um descriptor resolvido prova somente coerência dos elementos percorridos. DEX 041/contêiner experimental segue não suportado.

As cotas se aplicam ao leitor novo e não substituem os limites da admissão M2 (1 GiB de APK, 2 GiB de dados inflados, CRC-32, caminhos ZIP, cópia SAF). Nenhum artefato de build APK é publicado.

## Aceitação

Homologar somente com a suíte `DexClassNameProbeInstrumentedTest` aprovada no Android 10/API29 e 15/API35 e com regressões M1, M2/M3, Source checks e OTA verdes no **mesmo SHA**. Os testes exigem nomes ASCII e Unicode, até seis nomes, índices forjados, MUTF-8/truncamento/cancelamento, leitura somente em fluxo e integração scanner.

**Referência normativa:** https://source.android.com/docs/core/runtime/dex-format
