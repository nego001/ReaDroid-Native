# PE-S2.34 | Identidade final do processo após a segunda leitura das cotas (HOLD)

## Lacuna corrigida

O observador local S2.25 obtinha duas leituras consistentes de PID, hora de criação, UID efetiva, modo/filtros seccomp e cgroup. O reforço S2.32 passou a ler `memory.max`, `pids.max` e `cpu.max` **duas vezes**, rejeitando cotas divergentes.

Porém, a **última leitura das cotas ocorria após a última verificação de identidade do processo**. Um PID encerrado/reutilizado, uma mudança de UID/seccomp ou migração para outro cgroup durante a última passagem podia não ser detectado pelo snapshot.

## Alteração

Depois de comparar as duas leituras de cotas, `tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py` agora relê `/proc/PID/stat`, `/proc/PID/status` e `/proc/PID/cgroup`, comparando hora de criação, UID/seccomp/filtros e cgroup com os valores iniciais. Se qualquer um mudou ou não estiver disponível, a observação **recusa**.

Não há privilégios adicionais, escrita, uso de shell, inicialização de processo, execução de binário Windows ou mudança de parâmetros de release. Todos os arquivos continuam sujeitos ao caminho ancorado sem symlinks da PE-S2.33 e ao limite/EOF da PE-S2.31. As cotas seguem estritas e finitas.

## Testes regressivos

`tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py` agora verifica:
- Num cenário local estável, há **3 observações** de stat/status/cgroup e **2 de cada cota**, com a última observação de identidade após as cotas.
- Mudança **durante a segunda leitura de `cpu.max`** de (a) starttime do PID, (b) modo seccomp ou (c) cgroup, todos recusados. Antes da PE-S2.34 esses três casos poderiam gerar um resultado de observação local consistente indevido.

## Limitação de evidência

Releituras do kernel diminuem uma janela de corrida, mas **não provam continuidade** em toda a execução do Ghidra, nem excluem mudanças transitórias entre amostras. Essa é uma verificação **pontual, local e não atestada**. É obrigatório obter evidências independentes correlacionadas durante a execução completa num host do revisor e VM Arch nativa.

Issue [#48](https://github.com/nego001/ReaDroid-Native/issues/48) **OPEN**; PR [#47](https://github.com/nego001/ReaDroid-Native/pull/47) **Draft/unmerged**. `independent_vm_attestation=false`, `release_authorized=false`. Nenhum APK/OTA/release autorizado, nem execução de PE desconhecido.
