# NegrecoDroid — Motor M2: triagem de ZIP/APK hostil

## Objetivo e escopo

A M1 (PR #18) foi validada no SHA `fc2fc5648f4ef1f6e578b0ef0bd41ae5da2c7a51`, CI [#40244197734](https://github.com/nego001/ReaDroid-Native/actions/runs/40244197734), com **14 testes de rebuild/API em Android10/15 + E2E de importação, edição textual, reconstrução ZIP sem assinatura e exportação SAF verificada por SHA-256**.

A M2 corrige um problema anterior à edição: ZIPs compactos com metadados hostis podiam chegar ao analisador de manifesto e ao índice sem uma política uniforme de expansão. **M2 é triagem de metadados, não descompressão/análise completa nem garantia de ausência absoluta de ZIP bombs.**

## O que mudou no motor

- Nova classe `ApkArchiveBudget`, leitor **somente de diretório central ZIP** (via `java.util.zip.ZipFile`), sem extrair conteúdo nem criar arquivos.
- Todos os leitores de metadados passam por uma política única: `MainActivity.analyze` invoca `verifyArchive` imediatamente após cópia do SAF e **antes** de analisar manifesto, DEX, inteligência, segurança e índice; `ApkExplorer.inspect` e `ApkDiskIndex.build` também a aplicam independentemente para não dependerem exclusivamente do chamador.
- Rejeita caminhos absolutos, componentes `..`, `.`, vazios, barra invertida, byte NUL, mais de **4.096 caracteres** ou profundidade excessiva; entradas duplicadas; mais de **150 mil** entradas; tamanho declarado negativo/desconhecido; entrada acima de **1 GiB**, soma declarada acima de **2 GiB**.
- Rejeita entrada maior que **16 MiB** com razão de descompressão acima de **1000:1**, ou com tamanho comprimido declarado zero e tamanho descomprimido positivo. O piso de 16 MiB reduz falsos alarmes em arquivos pequenos altamente comprimidos. **O limite é uma escolha conservadora inicial, a calibrar com APKs reais.** É uma barreira adicional, não valida integridade CRC de todas as entradas.
- Mantém o teto de **1 GiB para APK comprimido ao copiar via SAF**, reserva de armazenamento, cancelamento por interrupção e remoção do cache em caso de exceção; adiciona falha determinística quando o provedor retorna **mais de 16 leituras vazias consecutivas** em vez de ficar num loop infinito.
- Indexação mantém **rollback e remoção de banco SQLite** em falhas, sem sobrescrever índices existentes e sem tocar o APK de origem.

## Evidência obrigatória

Novo `ApkArchiveBudgetInstrumentedTest` com **8 casos**: arquivo normal permitido (Explorador + SQLite), ZIP altamente comprimível real de **24 MiB** bloqueado nas três camadas com origem intacta e banco removido, tamanho desconhecido, tamanho individual forjado, soma acima de 2 GiB, duplicatas/traversal/NUL, cancelamento e ZIP central corrompido. Testa também tolerância a metadados pequenos comprimíveis.

A CI dedicada `engine-m2-archive-admission.yml` roda em **Android 10/API29 e Android 15/API35** no SHA exato. O workflow M1 existente também é disparado para branches `feature/engine-*`, mantendo os **14 testes/API** de rebuild e o E2E SAF como regressão. Source checks e manifesto OTA devem permanecer verdes.

## Limites e próximas fases

1. O diretório central de um ZIP é **metadado não confiável**: tamanho/CRC podem ser falsificados. Para autenticar o conteúdo real é necessária leitura completa com limite por bytes efetivos e CRC/SHA-256. O verificador M1 já faz isso em entradas preservadas no rebuild, mas a admissão M2 ainda não verifica o conteúdo de todas as entradas.
2. A detecção de taxa de compressão não é absoluta: uma taxa menor que 1000:1 e tamanho total dentro do teto ainda pode consumir tempo, CPU ou memória. Progresso, cancelamento efetivo, análise incremental e limites por módulo continuam necessários.
3. Não há suporte comprovado a APKs multi-GB, nem assinatura Android moderna, zipalign, edição DEX/Smali ou instalação do APK modificado.
4. **Próxima etapa M2.1:** tratar rejeição detalhada e estados de recuperação de diferentes provedores SAF; verificar leitura real de metadados e checksums sob orçamentos; medir tempo e RAM em APKs representativos.

**Política do projeto:** motor primeiro; PR #13 visual em pausa. M1 e M2 em PRs draft, `main` intocada. Não publicar APK/OTA nem declarar compatibilidade universal ou homologação em Galaxy A55 físico.
