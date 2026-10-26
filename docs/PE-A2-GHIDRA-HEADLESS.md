# NegrescoDroid PE-A2 | Ghidra Headless local sem interface

**Base:** PE-A1, PR #36, commit `b06aa9cc2445d345f2a163d47f78fa21f5324f5b`. Esta fase continua separada do motor Android M1/M2/M3, sem merge, APK ou OTA.

## Capacidade adicionada

O novo `tools/pe_auto_ghidra.py` é um orquestrador para **Linux (incluindo Arch Linux)**. Ele recebe um PE32/PE32+ que passou pela validação da PE-A0, cria uma cópia em pasta temporária privada, inicia uma instalação **já existente** do Ghidra Headless sem interface e executa `NegrescoFunctionInventory.java` após a análise automática nativa do Ghidra.

O script Java percorre a lista de funções que o **Ghidra conseguir reconhecer**, exportando apenas até **256 pares de endereço/nome**, com `is_thunk`, contagem total e indicação de truncamento. Nomes como `FUN_00401000` são gerados pela ferramenta, não nomes do código-fonte. Nenhum código de terceiro é executado pelo programa analisado: ele é inspecionado estaticamente pelo Ghidra.

O orquestrador valida o relatório JSON exportado, limita a saída a 128 KiB e grava um relatório externo com SHA-256 da cópia analisada, arquitetura e limitações honestas. Caso a análise falhe, expire ou produza JSON malformado, não publica um relatório de sucesso.

## Uso técnico no Arch Linux

Após instalar o Ghidra de uma fonte confiável e ter Java compatível:

```bash
python3 tools/pe_auto_ghidra.py /caminho/Programa.exe \
  --ghidra-home /caminho/ghidra \
  --output /caminho/resultado-pe-a2.json \
  --timeout-seconds 600
```

Esse comando é a interface **técnica de desenvolvimento**. O objetivo de PE-A5 continua sendo uma **ação de selecionar arquivo na interface**, que descobrirá o worker e executará todo o fluxo automaticamente, sem o usuário digitar comandos ou nomear funções manualmente.

## Como o Ghidra é chamado

A invocação usa a API de linha de comando **oficial** do `analyzeHeadless`: `-import`, `-scriptPath`, `-postScript`, `-analysisTimeoutPerFile`, `-max-cpu`, `-readOnly` e `-deleteProject`. `-noanalysis` **não** é usado, para permitir a identificação automática das funções. O script de exportação vem de um caminho fixo do próprio repositório e não é aceito como argumento externo.

Proteções ativas:
- Suporte operacional deliberado somente a Linux nesta fase; Windows não foi validado.
- Ghidra confiável precisa estar instalado localmente; o programa não instala software automaticamente nem baixa ferramentas de um servidor desconhecido.
- Entrada normal, não simbólica, de até **1 GiB**, copiada e verificada novamente pelo PE-A0; hash SHA-256 da cópia.
- Nome de projeto, pasta temporária privada, `HOME`, `TMPDIR` e cache separados; o Ghidra nunca recebe o caminho do arquivo original, apenas a cópia.
- Lista de argumentos sem `shell=True`, timeout global de até **1800 segundos**, `GHIDRA_HEADLESS_MAXMEM=2G`, `-max-cpu 2` e encerramento do grupo de processos no Linux em timeout.
- Evidências de funções limitadas a **256**, saída bruta no máximo **128 KiB**, rejeição de JSON falso, endereços duplicados e contagens/proveniência contraditórias.
- A saída não substitui um arquivo já existente.

## Limitações que não podem ser omitidas

**PE-A2 não é uma sandbox do sistema operacional.** A análise estática de um executável hostil por uma ferramenta complexa ainda representa risco de falha ou vulnerabilidade no analisador. Por enquanto, analisar binários não confiáveis requer uma conta isolada ou VM descartável sem arquivos sensíveis e acesso à rede quando possível. A futura PE-A2.1 deverá impor sandbox real com restrições verificáveis de processos, filesystem e rede.

**A CI atual valida somente o executor com um Ghidra SIMULADO**, e arquivos PE sintetizados; **não executa uma instalação real de Ghidra nem prova integração de ponta a ponta num executável proprietário**. A homologação do executor e de sua compatibilidade real com Ghidra são gates separados.

O que o código ainda não fornece:
- Recuperação de pseudocódigo/C; referências cruzadas e grafo de chamadas;
- Decomposição automática do instalador para localizar outros `.exe/.dll` embalados;
- Classificação semântica de funções e explicações de IA;
- Identificação perfeita de funções perdidas por ofuscação, empacotamento ou stripping;
- Integração de um clique com a interface Android/PC;
- Garantia de execução segura em processos fora de uma sandbox.

## CI, aceitação e próximos marcos

`tests/test_pe_auto_ghidra.py` simula um comando `analyzeHeadless`, verifica cópia PE, comandos, relatório, não sobrescrita, timeout, kill do grupo de processos, links simbólicos, compilação Python e recusas a evidências inválidas. Os testes de PE-A0/PE-A1 continuam ativos.

- **PE-A2 runner aprovado em CI** significa somente que o orquestrador funciona com o *mock* testado.
- **PE-A2 integração real aprovada** exige uma matriz com Ghidra instalado em Linux e um PE sintético compilado, demonstrando emissão do relatório Java e endereços reais.
- **PE-A3** acrescentará grafo de chamadas e pseudocódigo quando recuperáveis, mantendo limites e transparência da confiabilidade.
- **PE-A5** unirá importação, análise, classificação e relatório em um fluxo de um clique.

**Fontes oficiais:** https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md e https://ghidradocs.com/11.4_PUBLIC/support/analyzeHeadlessREADME.html.
