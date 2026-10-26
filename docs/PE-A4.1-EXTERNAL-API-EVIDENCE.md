# PE-A4.1 | Corrigir evidências de chamadas WinAPI no Ghidra real

## Falha real detectada e correção

Na primeira CI PE-A4 (GitHub Actions #40417920508) o Ghidra 12.2 identificou 114 funções, mostrou 82 na prévia e decompilou 12, mas o classificador gerou **zero hipóteses** apesar de a fixture sintética chamar `GetFileAttributesA`. A execução anterior era tecnicamente verde porque a CI verificava apenas que o relatório era estruturado. Isso **não prova identificação de comportamento**.

## Mudanças da PE-A4.1

- O exportador `NegrescoDeepPreview.java` continua limitando a análise a 384 funções e 12 pseudocódigos, mas preserva evidências de funções externas chamadas via `getCalledFunctions(monitor)`. Quando Ghidra reconhece um thunk, tenta resolver o destino por `getThunkedFunction(true)` e só registra nomes se esse destino for marcado pelo Ghidra como **externo** e estiver numa whitelist WinAPI explícita.
- Essas chamadas WinAPI são armazenadas separadamente do grafo de endereços internos. Nenhum endereço `EXTERNAL:` é forçado a parecer um endereço de código do executável.
- A seleção ganha um bônus determinístico de 128 pontos quando a função tem referências a uma API da whitelist; o máximo teórico é 244. Assim, a amostra limitada tende a incluir funções de aplicação que interagem com APIs Windows, sem depender da ordem dos endereços.
- `api_call_references` contém no máximo 8 nomes, além de contagem total e truncamento. O validador Python rejeita nomes fora da whitelist, endereços malformados, duplicatas, pontuação falsificada, contagens inconsistentes e precedência fora da ordem.
- O classificador PE-A4 aceita agora duas formas separadas de evidência: chamada de API no pseudocódigo C, ou referência externa retornada e validada pelo Ghidra. Um import na tabela PE-A1 ou um nome sugestivo de função, isoladamente, **continuam sem autorização para virar hipótese**.

## Gate de aceitação fortalecido

A CI com Ghidra real **não pode mais passar apenas porque gerou JSON e 12 pseudocódigos**. Ela precisa identificar a chamada `GetFileAttributesA` da fixture PE criada pela CI e produzir uma hipótese da categoria `filesystem_inspection`. Se nenhuma referência ou hipótese concreta for encontrada, **a CI deve falhar**.

Testes Python continuam cobrindo integridade dos relatórios e falsos positivos: nomes API inventados, duplicados, importações sem chamada e comentários/strings sem invocação. Nenhum executável Windows de terceiros é baixado, instalado ou executado.

## Limitações honestas

Essa técnica ainda representa uma **hipótese estática**, não execução observada nem reconstrução fiel do código-fonte. A whitelist pode perder APIs importadas por endereços indiretos, código empacotado ou variantes desconhecidas. A eficácia real do isolamento Bubblewrap em Linux continua pendente; usar VM descartável com software potencialmente malicioso. A integração com IObit Uninstaller e uma interface de um clique ainda não foi concluída.

PR empilhada em PE-A4 (#42), em Draft; `main` não alterada e nenhuma OTA ou APK publicada.