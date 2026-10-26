# NegrescoDroid | M2.8 — perfis realistas de comprimento dos caminhos ZIP

**Estado:** implementação experimental empilhada sobre M2.7 (#27). Sem alteração de código de produção, interface, assinatura, canais OTA ou limites de importação. Não fazer merge sem validação final.

## Por que medir comprimentos diferentes?

A M2.6 demonstrou que SHA-256/128 retém muito menos memória Java que `HashSet<String>` para **8.192 nomes com prefixo de 770 caracteres**, com custo adicional de CPU em alguns emuladores. A M2.7 reduziu ainda mais o custo do conjunto ao usar arrays primitivos. Porém, APKs reais têm muitos caminhos curtos e médios; não se deve extrapolar os resultados de nomes longos para todos os pacotes.

## Implementação

O novo teste `ApkPathLengthProfileInstrumentedTest` compara no mesmo Android:

- **32 caracteres:** nomes curtos em pastas simples;
- **128 caracteres:** profundidade intermediária;
- **768 caracteres:** nomes longos, mas dentro do limite de 4.096 caracteres por caminho.

Cada perfil utiliza 4.096 caminhos sintéticos diferentes e a ordem **A1, B1, B2, A2**. A usa `HashSet<String>`; B usa `ApkPathFingerprintSet` M2.7. O teste verifica integridade de contagem e caminhos validáveis e registra duração de parede, CPU do processo, memória Java retida após coleta de lixo e PSS amostrado, sem critérios artificiais de desempenho.

Os dados são observações em ambiente de emulador, não picos reais de RAM ou garantias de velocidade. Construção das strings e GC influenciam ambos os métodos. A ordem ABBA ameniza aquecimento, mas não elimina diferenças entre execuções e versões Android.

Para respeitar a limitação de comprimento de logs do Android, o teste envia **três pequenas linhas** `M2PathLength: RESULT_JSON:...`, cada uma contendo um perfil. O extrator `tools/extract_m2_pathlength_logcat.py` exige os três comprimentos e exatamente quatro amostras ordenadas por perfil, além de API coerente, campos permitidos e marcação explícita de dados sintéticos. Logcat bruto e caminhos reais não são publicados.

## Critérios de aceite

- Source checks, OTA e todas as regressões M1 aprovados no mesmo SHA.
- Matriz M2 executada no Android 10/API29 e Android 15/API35, incluindo testes de admissão maliciosa, cancelamento, limite de 150 mil entradas e perfil anterior de 8.192 caminhos.
- Os relatórios JSON `m2-pathlength-api-29.json` e `m2-pathlength-api-35.json` devem ser validados e exportados em artifacts somente com métricas sintéticas.
- Interpretar tradeoffs de memória vs CPU por perfil, sem presumir que a configuração vencedora é universal.

**Produção:** M2.8 não muda o algoritmo ainda. A decisão posterior de usar estratégia adaptativa precisa ser justificada com dados e não pode reabrir aceitação de ZIP malicioso ou caminhos duplicados.
