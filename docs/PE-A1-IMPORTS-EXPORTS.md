# NegrescoDroid | PE-A1: reconhecimento passivo de imports/exports Windows

**Base:** PE-A0, PR #35 homologada no commit `f1be4d475e12ca7c4ec0cdd2835ff4fea945246a`. Esta implementação é um passo em direção ao pedido de engenharia reversa automática de software Windows (por exemplo, os módulos de `IObit Uninstaller`), **mas não analisa nem classifica funções internas ainda**.

## O que faz

`tools/pe_auto_symbols.py` aceita arquivo `.exe` ou `.dll` PE32/PE32+ e gera JSON estritamente de leitura com:

- Nome de bibliotecas DLL **declaradas** no diretório de imports;
- Funções importadas por **nome** ou ordinal, com `hint` quando disponível;
- Tabela de exports (até 128 na prévia), ordinal, nome e RVA; reconhece exports **encaminhados** (*forwarders*) para outros módulos;
- Contagens e indicações claras de que o motor não recuperou funções internas, pseudocódigo ou comportamento do executável.

A leitura usa o inventário PE-A0 e traduz endereços **RVA para deslocamentos em disco** somente em seções com bytes presentes. RVAs ambiguamente mapeados, fora do arquivo, sem terminador ou com strings inválidas são recusados. Dado em memória virtual mas não presente no arquivo não pode ser tratado como byte disponível.

## Orçamentos e proteções

| Restrição | Limite |
|---|---:|
| Bytes lidos na análise dos diretórios | 16 MiB cumulativos |
| DLLs do import table | 128 |
| Entradas importadas por DLL | 512 |
| Entradas importadas totais | 2.048 |
| Funções na tabela de exports | 4.096 |
| Nomes de exports | 2.048 |
| Exports mostrados na prévia | 128 |
| Tamanho de cada nome ASCII | 256 bytes |
| Arquivo de entrada PE-A0 | 1 GiB |

**O programa analisado nunca é executado, descompactado ou enviado para nuvem.** O parser rejeita tabelas incompletas, repetidas de forma inválida, endereços fora das seções, entradas sem NUL e ordinal de export fora de alcance. São regras conservadoras; algumas implementações PE exóticas válidas poderão aparecer como não suportadas.

## Como executar o primeiro diagnóstico no Arch Linux

```bash
python3 tools/pe_auto_inventory.py /caminho/Programa.exe
python3 tools/pe_auto_symbols.py /caminho/Programa.exe
```

Não requer Windows, Wine, root nem Ghidra nesta etapa. O uso de duas linhas acima serve **somente para inspeção técnica ou teste do módulo**: o fluxo final para o usuário será uma única seleção de arquivo.

## Ponto crítico sobre o IObit Uninstaller

O instalador pode incorporar componentes, outros executáveis, DLLs e recursos. Os imports/exports do instalador **não equivalem ao inventário de funções do programa instalado**. Uma rotina sem export pode ser muito importante; nomes de funções importadas não comprovam que ela é utilizada na prática. Endereços exportados sem símbolos não revelam automaticamente seu propósito.

O estado retornado é `imports-exports-only`, com `local_function_recovery=not_implemented` e `decompilation=not_implemented`. Isso evita confundir um inventário estático com engenharia reversa completa.

## Aceite e fases futuras

O workflow `pe-auto-triage.yml` testa **fixtures PE sintéticas** em PE32 x86 e PE32+ x64, DLLs e funções importadas, ordinais, exports encaminhados, mapeamento RVA hostil, diretórios adulterados, limites e ausência de execução de executáveis. Exigir CI da etapa verde no SHA da PR; revisar Source checks e OTA. Manter a PR **Draft**, `main` intacta e sem publicar APK.

**Próximo PE-A2:** executor Ghidra Headless em ambiente isolado, com timeout, recursos limitados, artefatos JSON filtrados e uma trilha de auditoria; nenhuma rotina Windows poderá ser executada no host no modo estático.

Fonte oficial de referência: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
