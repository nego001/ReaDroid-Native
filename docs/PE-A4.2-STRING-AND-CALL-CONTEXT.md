# NegrescoDroid | PE-A4.2: strings e contexto de chamadas, com endereços verificáveis

## Objetivo

O Ghidra Headless agora exporta, para cada função selecionada, referências a strings **definidas e alcançadas a partir de instruções da própria função**, incluindo endereço de origem e endereço do dado. Isso enriquece a explicação automática sem inventar operações a partir de palavras sugestivas encontradas no binário.

## Limites e cadeia de evidência

- Processa até 12 funções decompiladas, no máximo 2.048 instruções por função, no máximo 16 referências por instrução, no máximo **8 strings únicas** por função e 96 caracteres ASCII imprimíveis por string, mínimo 6. Filtra strings que não correspondam a dados definidos pelo Ghidra e referências fora de endereços normais.
- Cada evidência contém `text`, `data_address` e `reference_from`. O relatório informa `strings_truncated`, `string_scan_truncated` e `instructions_scanned_for_strings`; amostras incompletas jamais são apresentadas como exaustivas.
- A saída do Java muda para `ghidra_deep_preview_v3`. O leitor Python valida tipo, tamanho, ASCII, endereços hexadecimais, duplicatas, limites e flags antes de aceitar os dados.
- A etapa de classificação PE-A4 mantém seu método conservador: **somente chamadas WinAPI explícitas no pseudocódigo ou referências externas verificadas do Ghidra** podem sustentar hipóteses funcionais. Strings são mostradas no campo `string_context` e identificadas explicitamente por `strings_are_behavior_evidence=false`.
- As relações com outras funções selecionadas são mostradas no campo `linked_selected_callees` com nome e endereço, somente quando a relação direta e o endereço de destino existem na mesma amostra. Não completa ou inventa arestas desconhecidas.

## Prova com Ghidra real

A fixture PE sintética compila uma chamada inofensiva `GetFileAttributesA("negresco_evidence_2026.txt")` na função `inspect_path`. A CI executa apenas o analisador Ghidra, **não** o programa Windows. A nova verificação exige evidência de referência a essa string, proveniência na função `inspect_path`, preservação dos endereços no relatório explicativo e a hipótese de consulta de arquivos já exigida pela PE-A4.1. Um relatório vazio ou JSON bem formado sem a referência **deve falhar**.

## Privacidade e limitações

Strings podem conter dados sensíveis embutidos no executável. Permanecem no relatório local; não são transmitidas para nuvem nem copiadas automaticamente a terceiros. Como são dados estáticos e heurísticos do Ghidra, não são prova de execução, caminho utilizado, motivo da operação nem código-fonte original.

A implementação cobre somente strings ASCII curtas e previamente identificadas como dados definidos, referências diretas de instruções e a amostra de 12 funções. Strings Unicode, ofuscação, constantes montadas em runtime, caminhos indiretos e instaladores empacotados não estão totalmente cobertos. A sandbox Bubblewrap continua sem homologação funcional em kernel real: usar VM descartável para analisar binários potencialmente hostis.

PR empilhada sobre a PE-A4.1 (#43), **Draft**, sem merge na `main` nem publicação de APK ou OTA.