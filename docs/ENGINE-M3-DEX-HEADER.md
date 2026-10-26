# NegrescoDroid | Motor M3.1 — leitura segura do cabeçalho DEX

**Base:** M2.8 homologada, PR #28. Esta fase não adiciona descompilação, edição binária, execução de bytecode, assinatura nem publicação de APK/OTA.

## O que é implementado

`DexHeaderProbe.inspect(InputStream, long)` lê **somente os primeiros 112 bytes** do cabeçalho de cada DEX tradicional, versões 035 até 040. Nenhum corpo DEX, cadeia de caracteres, método ou classe é carregado na memória pelo novo leitor.

As validações são independentes do parser principal: assinatura `dex\\nVVV\\0`, versão suportada, `file_size` igual ao comprimento declarado da entrada ZIP, `header_size = 112`, endian padrão, mapa dentro da região de dados, contagens e deslocamentos das tabelas dentro dos limites com multiplicações protegidas contra overflow.

**DEX 041 é explicitamente recusado** neste protótipo. O formato experimental de contêiner do Android 16 usa cabeçalho de 120 bytes e regras diferentes de offsets, e não deve ser tratado como DEX tradicional.

No `SecurityScanner.scan`, os 12 primeiros DEX ganham uma prévia com versão, tamanho e contagens *declaradas* de strings, tipos, protótipos, campos, métodos e classes. O relatório inclui `dexHeaderPreviewTruncated` quando há mais DEX. Um cabeçalho rejeitado recebe o status `unreadable-header`; isso **não invalida automaticamente a importação** nem significa que a declaração contida em um cabeçalho aprovado seja um DEX completo válido.

Cancelamento da tarefa gera `InterruptedIOException` e continua propagando até o chamador. O scanner não o converte em aviso. O fluxo existente de admissão M2, com CRC e leitura de todas as entradas, deve continuar sendo executado antes das análises da origem.

## Limites de segurança

- O probe lê somente 112 bytes; não calcula SHA-1 nem Adler-32 internos do DEX, não interpreta `map_list`, não decodifica instruções, não valida referências cruzadas nem prova instalabilidade.
- A integridade dos bytes de arquivo ZIP continua competência da admissão M2.1, não da prévia DEX.
- `sizeBytes` e as contagens são apenas os **valores do cabeçalho** após checagens estruturais de limites; não garantem que a seção possua itens válidos.
- O teto de importação, as verificações de ZIP, a indexação SQLite e o mecanismo de exportação SAF não são alterados.
- Nenhum conteúdo bruto de DEX ou chave/arquivo privado é exportado como artefato da CI.

## Aceitação

- Android 10/API29 e Android 15/API35 executam a suite `DexHeaderProbeInstrumentedTest`, cobrindo versões 035, 039 e 040, DEX 041 recusado, corrupção, tamanhos forjados, offsets extrapolados, leitura de até 112 bytes e interrupção.
- Regressão de integração: `SecurityScanner` reporta DEX de cabeçalho plausível e DEX inválido sem crash.
- M1, M2, Source checks e OTA devem estar **todos verdes no mesmo SHA**, e PR deve permanecer em rascunho.

Especificação de referência: https://source.android.com/docs/core/runtime/dex-format
