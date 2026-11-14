# PE-S2.10 | CI com ENOSPC real em /work/limited, sem homologação Arch

**Estado:** integração testável; **release HOLD**. Nenhuma VM Arch independente foi homologada. PR #47 segue Draft sem merge, APK/OTA ou execução de PE Windows desconhecido.

## Escopo preciso da evidência

`tests/pe_bwrap_work_quota_real_ci.py` executa um teste Python inofensivo no Bubblewrap **real em runner Ubuntu**, aproveitando o perfil de produção, mas trocando **somente na invocação de teste** o bind de `/work` do host por montagem nova e descartável `/work/limited` em `tmpfs`, com tamanho **64 MiB** e modo 0700. O código `tools/pe_native_workspace_budget.py` é exposto em caminho **somente leitura**, fora do volume medido. Nada é montado no host. Ghidra e Windows PE **não** são iniciados pelo ensaio.

O filho analisa `/proc/self/mountinfo` e `statvfs` reais invocando **a função de produção** `require_bounded_work_mount`. Antes da escrita exige capacidade e espaço livre, ausência de arquivo-sentinela do host, isolamento entre o dispositivo do `/work` temporário e o diretório pai. Escreve blocos limitados até receber **ENOSPC real do kernel**, apaga a tentativa e comprova espaço livre recuperado. Testes negativos também exigem rejeição para `tmpfs` de **32 MiB** e montagem filha que permitiria contornar o orçamento. O orquestrador recusa saídas malformadas e verifica que a sentinela do host não foi alterada.

Importante: este teste demonstra **um caso de funcionamento do verificador + cota do kernel em Bubblewrap Ubuntu**. NÃO demonstra que a VM Arch independente foi criada, que `/work` do revisor foi configurado corretamente, que as cotas sobreviveram a um remount privilegiado, que outros destinos graváveis estão limitados, ou que o `journald` está com uso de disco efetivamente contido. Em particular, `journal_size_kernel_enforced=false`, `independent_arch_vm_attested=false` e `release_authorized=false` devem permanecer.

## Evidência independente ainda necessária

O revisor externo precisa executar na **VM Arch descartável** e coletar em canal separado, com SHA de Git, desafio e snapshot previamente pinados: 1) mountinfo/fstatvfs de `/work` dedicado com cap 64–512 MiB; 2) prova controlada de ENOSPC no mesmo volume, antes/depois da execução sintética; 3) comportamento real do `journald` ativo com controle de espaço sem confundir retenção com cota rígida; 4) cgroup v2 + seccomp aplicados conjuntamente, cleanup de filhos e auditoria dos demais destinos graváveis. Sem essa comprovação independente, manter o bloqueio.
