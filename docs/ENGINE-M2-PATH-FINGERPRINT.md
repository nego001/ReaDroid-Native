# NegrecoDroid | Motor M2.5 — unicidade ZIP com menos strings retidas

**Branch:** `feature/engine-m2-path-fingerprint` (empilhada sobre a M2.4, sem alterações na `main`, APK instalável, assinatura ou interface).

## Problema

A admissão M2.1 rejeita nomes de arquivos duplicados usando `HashSet<String>`. Em um ZIP com muitos caminhos longos, manter até 150 mil `String` completas pode elevar o consumo de heap depois da leitura do diretório central.

O limite de 16 milhões de caracteres e o limite de 150 mil entradas já existem e são mantidos. O objetivo da M2.5 é evitar reter todos esses caracteres numa segunda estrutura gerenciada.

## Alteração

- `ApkPathFingerprintSet` calcula SHA-256 para cada caminho validado e guarda apenas as **primeiras 128 bits** em dois números `long` imutáveis. O nome bruto deixa de ser retido pelo conjunto.
- A verificação `ApkDiskIndex.validatePath`, a contagem de entradas, o orçamento total de caracteres, o CRC e todos os limites de descompressão permanecem ativos.
- Um caminho duplicado gera a mesma impressão digital e é sempre rejeitado.
- Uma **colisão hipotética entre nomes distintos** também causa rejeição conservadora. Não existe aceitação silenciosa de duplicatas: a política falha de modo fechado. Ainda assim, impressões digitais criptográficas não são uma comprovação matemática de unicidade de nomes distintos.
- O novo formato usa 16 bytes de identificador por entrada, mas `HashSet`, objetos Java, o `ZipFile` e a implementação do SHA-256 ainda têm custos. **Não presumir 16 bytes de memória total por entrada.**

## Validação

- Quatro testes instrumentados: caminho Unicode repetido, 8.192 nomes extensos e distintos, diferença de caixa e composição Unicode, e ZIP com 1.024 caminhos longos conferindo conteúdo/original preservados.
- Os testes de CRC, ZIP malicioso, cópia SAF, paginação e capacidade anteriores continuam na matriz M2.
- Contrato Python verifica que o guarda não retém `Set<String>`, mantém os limites de entrada/caminho e continua rejeitando colisões.
- Medidas da M2.4 para a mesma carga sintética de 2.503 entradas são referência de *sanidade*, **não experimento A/B controlado**. Comparações só serão conclusivas após múltiplas repetições em condições equivalentes.

## Riscos e pendências

O custo computacional de SHA-256 por caminho pode superar o custo do hash padrão de `String` em APKs com muitos nomes pequenos; portanto, validar CPU antes de tratar isso como melhora líquida. A memória total do app ainda pode crescer por fatores externos, inclusive diretório ZIP, scanner, indexador SQLite e análise do manifesto.

Não aumentar o limite de importação de 1 GiB ou o teto de 2 GiB inflados. PR deve permanecer em draft até M1, M2, Source checks e OTA passarem no mesmo SHA e serem analisadas as amostras de performance. Não publicar APK ou OTA.
