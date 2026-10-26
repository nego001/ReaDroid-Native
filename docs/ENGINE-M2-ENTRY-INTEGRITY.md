# M2 — inspeção de entradas ZIP com integridade comprovada

O desenvolvimento do NegrecoDroid continua pelo **motor**, com a UI P7 congelada.

## Primeiro risco abordado

O `ApkEntryInspector.inspect` calculava SHA-256 e apresentava o CRC-32 informado no cabeçalho ZIP, mas **não calculava nem conferia o CRC dos bytes realmente lidos**. Uma entrada adulterada no diretório central podia então resultar em um relatório com aparência normal. O método também não consultava a interrupção da thread durante uma leitura longa.

## Mudança

- Exigir tamanho descomprimido, comprimido e CRC declarados; recusar metadados ZIP desconhecidos.
- Antes de abrir grandes entradas, recusar tamanho declarado acima de **1 GiB**.
- Ler por blocos de 64 KiB, calcular SHA-256 e CRC-32 dos bytes efetivos, limitar tamanho real a 1 GiB, verificar cancelamento e conferir CRC/tamanho reais com o diretório central.
- Mostrar no relatório o CRC **calculado**, jamais confiar em valores não verificados.
- Não extrair arquivos nem escrever no APK original.

## Testes

`ApkEntryInspectorInstrumentedTest` tem 4 casos: entrada íntegra, corrupção real do CRC no diretório central, cancelamento e caminho de travessia. CI dedicada Android 10/API29 e Android15/API35 precisa concluir 2/2 verde no mesmo SHA.

**Escopo honesto:** isso fortalece a inspeção de uma entrada, não torna todas as operações do Explorer livres de ZIP bombs. O próximo recorte da M2 será validar metadados de todo o arquivo, tamanhos desconhecidos, profundidade de diretórios e pressão de recursos com testes artificiais controlados. Nenhum APK instalável/OTA é publicado; PR #18 do motor M1 permanece separada e em rascunho. Não fazer merge automático na main.
