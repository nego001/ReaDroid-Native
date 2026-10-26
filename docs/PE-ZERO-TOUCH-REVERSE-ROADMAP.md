# NegrescoDroid | Engenharia reversa de executáveis Windows sem etapas manuais

## Objetivo do produto

O usuário seleciona um arquivo `.exe` ou `.dll` de Windows (por exemplo, um componente do IObit Uninstaller) e pressiona **Analisar automaticamente**. O software deve executar sozinho o inventário de componentes, a busca de funções, a descompilação de funções recuperáveis, a coleta de pistas, a categorização de comportamentos e a criação de um relatório navegável com **evidências e confiança**. O usuário não precisa renomear funções, procurar endereços nem operar Ghidra manualmente.

**Limitação técnica irredutível:** nenhum sistema pode garantir recuperação perfeita de todas as funções, nomes de origem ou intenções, especialmente em binários ofuscados, empacotados, parcialmente criptografados ou sem símbolos de depuração. Nesse caso, gerar `desconhecido` com explicação, jamais inventar funcionalidades.

## Situação real no repositório

- O NegrescoDroid é atualmente um aplicativo **Android** baseado em Java/Gradle, com M1/M2/M3 focados em APK/DEX. Não há agora descompilador PE nem analisador automático de funções x86/x64.
- Este ramo experimental `feature/pe-auto-triage` acrescenta somente **PE-A0: leitura offline segura dos cabeçalhos PE32/PE32+** em `tools/pe_auto_inventory.py`, com testes sintéticos e CI específica.
- **PE-A0 não identifica/descompila funções, não extrai o instalador, não integra a interface Android e não torna o aplicativo capaz de analisar IObit Uninstaller de ponta a ponta.**
- A aplicação atual preserva o processamento APK existente sem regressões por este ramo: nenhum arquivo Android de produção é alterado.

## Arquitetura para automação integral

1. **Detecção automática e isolamento do arquivo:** distinguir APK/ZIP, PE Windows, executável empacotado/instalador e outros formatos. Copiar para diretório privado com limites, tamanho, hash, detecção de componentes e nenhum carregamento/execução do executável de terceiros.
2. **Inventário PE:** checar MZ/PE, CPU, arquitetura 32/64 bits, seções, imports/exports, bibliotecas, recursos, sinais de .NET/empacotadores, assinaturas e símbolos. Considerar DLLs ou subprocessos entregues junto com o produto, pois um instalador pode não conter o código do programa principal.
3. **Análise estática sem GUI:** executar **Ghidra Headless** em um worker local isolado, com limites de tempo, RAM, disco e processos, importando automaticamente `.exe/.dll` e aplicando scripts de pós-análise. Coletar funções, endereços, referências cruzadas, call graph, strings e pseudocódigo recuperável. Ghidra permite operações de importação, autoanálise e scripts via `analyzeHeadless`.
4. **Classificação automática com evidência:** atribuir categorias hipotéticas às funções com base em imports do Windows, strings, chamadas e pseudocódigo; atribuir confiança e exemplos, relacionando funcionalidades com suas dependências. Quando houver símbolos originais, preservá-los; sem símbolos, propor apelidos sem apresentá-los como nomes reais. Nunca esconder o status `não identificado`.
5. **Relatório navegável e reproduzível:** árvore de DLLs/EXEs, módulos, funções, chamadas, pseudocódigo, possíveis rotinas de desinstalação, remoção de resíduos, serviços ou registro (somente quando houver evidência!), hashes, limites, alertas e resumo para leigos.
6. **Integração zero-toque:** no **Arch Linux/Windows**, o worker Ghidra roda localmente com um serviço que inicia a análise no momento em que o arquivo é selecionado. No Android, o NegrescoDroid atua como interface de envio/recebimento **somente após pareamento e consentimento explícito com um PC ou serviço dedicado**. Não prometer Ghidra completo no celular sem validar recursos e isolamento.

## Segurança e privacidade

- **Nunca executar** um `.exe` de terceiros para analisá-lo estaticamente, mesmo no Linux. Uma fase dinâmica deve ser separada, com consentimento explícito e VM descartável.
- A coleta não deve enviar executáveis, trechos proprietários ou relatórios privados para serviços de nuvem sem consentimento claro.
- Metadados interpretados e nomes sugeridos pela IA devem ser rotulados como inferências, não verdade absoluta.
- Instalar ou reempacotar software proprietário, remover DRM/licenciamento, distribuir binários alterados e burlar controles não fazem parte do fluxo automático solicitado.
- Preferir ferramentas e métodos compatíveis com licenças aplicáveis, sem prometer acesso ao código-fonte original.

## Primeiro incremento: PE-A0

`tools/pe_auto_inventory.py` faz leitura delimitada e passiva:
- aceita apenas arquivos regulares não simbólicos de até **1 GiB**;
- exige cabeçalho `MZ`, `e_lfanew` a até **1 MiB**, assinatura `PE\0\0`, cabeçalho COFF e PE32/PE32+ compatível com x86/x86_64/ARM64;
- verifica máximo de 96 seções, cabeçalho opcional até 4 KiB, limites da tabela e região de bytes das seções;
- retorna JSON com formato, arquitetura, entry point RVA, seções e presença de diretórios declarados; **não interpreta os corpos das seções, os imports reais nem as funções**;
- reporta explicitamente `automatic_function_identification=not_implemented` e `decompilation=not_implemented` em vez de resultados fictícios.

A CI `pe-auto-triage.yml` usa **somente fixtures PE sintéticas** e verifica rejeição de cabeçalhos forjados, arquiteturas incompatíveis, seções inválidas e symlinks. Não executa binários Windows, não instala desinstaladores e não coleta arquivos reais do usuário.

## Próximos marcos técnicos

| Marco | Entrega verificável |
|---|---|
| PE-A0 | Inventário PE seguro, CI sintética, relatório JSON de cabeçalho |
| PE-A1 | Extração de imports/exports e referências RVA com limites/relatório reproduzível |
| PE-A2 | Runner local Ghidra Headless com testes de integração e isolamento de execução |
| PE-A3 | Exportador automático de inventário de funções, pseudocódigo e call graph |
| PE-A4 | Etiquetagem semântica com evidências, confiança, aliases e casos desconhecidos |
| PE-A5 | Orquestração *um clique* no desktop Arch/Windows; UI Android pareada ao worker |

**Não fazer merge da PR experimental ou alegar suporte ao IObit completo enquanto todos os componentes PE-A1–PE-A5 e respectivos testes não existirem.**

Referência oficial: https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md
