# NegrecoDroid | Motor M2.1: admissão segura de APK/ZIP

**Escopo:** segurança da importação e análise, sem edição visual nem mudança da `main`. Esta PR é empilhada sobre a branch da M1 para não misturar fases enquanto ambas estão em revisão.

## Problema real

O importador já conta os bytes copiados pelo SAF e respeita o limite de 1 GiB, mas a etapa seguinte examinava metadados do ZIP antes de validar de forma independente o conteúdo realmente descompactado. Campos de tamanho, CRC e contagem do diretório central podem ser falsificados. Também havia várias rotinas de análise com políticas distintas; as mais leves podiam alcançar entradas maliciosas antes da indexação.

## M2.1 implementada

- `ApkArchiveSafety.verify` é executado **depois da cópia para cache privado e antes** do `PackageManager`, do relatório JSON e do índice SQLite.
- Lê todas as entradas em fluxo com blocos fixos de 64 KiB; confere tamanho real e CRC-32 com os metadados e permite interromper a tarefa.
- Recusa nomes duplicados, caminhos inseguros, ZIPs truncados/ilegíveis, métodos não suportados, metadados ausentes, entradas acima de 1 GiB, expansão declarada/medida acima de 2 GiB, contagem acima de 150 mil e orçamento de nomes acima de 16 Mi caracteres.
- Por precaução, arquivos de pelo menos 8 MiB com razão declarada de descompressão superior a 500:1 são recusados. Isso pode rejeitar arquivos benignos extraordinariamente compressíveis; é uma **política de admissão**, não prova de arquivo malicioso.
- A validação é somente leitura; uma falha mantém o projeto anterior e impede a adoção do candidato na rotina transacional existente da Activity.

## Evidência e testes

- Suite de **oito cenários instrumentados** com ZIPs sintéticos: DEFLATE/STORED íntegros, CRC adulterado, tamanho declarado forjado, expansão excessiva, travessia de diretórios, duplicata no diretório central, arquivo truncado e interrupção.
- Workflow Android 10/API 29 e Android 15/API 35 com relatórios de testes. A CI M1 existente também roda nos branches `feature/engine-*` e permanece exigida antes de aprovar esta pilha.
- Contrato Python impede remover/mover a checagem para depois dos parsers ao refatorar a importação.

## Limites ainda não resolvidos

1. **Custo de I/O/CPU:** a admissão percorre todo o conteúdo descomprimido antes da análise. Medir latência com APKs de tamanhos variados; não relaxar as verificações só para acelerar.
2. **Uso de memória:** os caminhos são únicos e limitados por orçamento de caracteres, mas a construção do relatório JSON legado ainda pode consumir memória significativamente. Migrar análise e exploração para paginação SQLite como etapa posterior.
3. **ZIP avançado:** formatos ZIP64 extremos, sobreposição de entradas ZIP e variantes incomuns precisam de fuzzing e validação adicional. Não declarar segurança completa contra todas as formas de ZIP bomb.
4. **Importação SAF:** o limite de 1 GiB e a reserva de armazenamento continuam. Não alegar importação multi-GB.
5. **Rebuild:** M1 permanece sem assinatura e sem garantia de instalabilidade.

## Critério de aceitação

A M2.1 só estará **validada** após aprovação dos testes instrumentados em API 29 e 35 e dos contratos da CI no SHA exato. Sem merge ou distribuição automática. A M2 seguirá com medição de memória, limites de processamento do índice, relatório de progresso e testes negativos de falha de SAF/recuperação.


## M2.2: Cópia SAF resiliente

- A cópia para cache privado utiliza `SafImportStream.copyAndHash`, que produz SHA-256 durante o streaming sem carregar o APK inteiro na RAM.
- Bytes **reais**, não o tamanho anunciado pelo provedor, respeitam um limite rígido de 1 GiB, com leitura de um byte sentinela depois do limite exato.
- A implementação não permite ciclos infinitos quando um provedor retorna continuamente `read() == 0`; 17 leituras consecutivas sem progresso encerram o fluxo com erro.
- Verifica a disponibilidade de espaço antes de escrever, periodicamente em cópias grandes, **e obrigatoriamente após a leitura final**. Preserva a reserva já existente de 64 MiB.
- Cancela antes e depois de cada leitura sem apagar o flag de interrupção. Erros de leitura/escrita propagam-se para a análise transacional, que remove o cache temporário e mantém o projeto anterior.
- Suite de 9 cenários novos: hash completo, arquivo no limite exato, um byte além, provedor travado em zero, recuperação após zeros intermitentes, espaço que acaba no final, espaço insuficiente no início, interrupção e erro real de I/O.
- A CI executa as suites de admissão ZIP e cópia SAF em Android 10/API 29 e Android 15/API 35.

**Restrições:** não resolve um `ContentProvider` que permaneça bloqueado dentro de uma chamada de leitura sem retorno; o fluxo só pode observar cancelamento quando `read()` devolve controle. Também não transforma o limite de 1 GiB em suporte multi-GB. O SHA-256 emitido comprova os bytes copiados, não a instalação do APK.

**Critério:** M2.2 só é homologada quando o workflow M2 atualizado, regressões M1, Source checks e validação OTA passam no mesmo commit da PR.
