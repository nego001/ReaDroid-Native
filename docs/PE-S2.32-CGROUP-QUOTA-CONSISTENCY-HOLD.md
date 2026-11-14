# PE-S2.32 | Dupla observação de cotas cgroup v2 (HOLD)

## Problema corrigido

O snapshot local PE-S2.25 confere UID e estado seccomp do PID do processo, caminho do cgroup v2 e os limites de `memory.max`, `pids.max` e `cpu.max`. Antes, os arquivos de limite eram coletados **uma vez**, entre duas leituras de identidade do processo. Uma alteração de cota durante a coleta podia deixar o resultado positivo local associado a valores antigos, sem indicar mudança de política.

## Controle novo

`tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py` agora:

1. Observa o PID, a UID, o seccomp e o cgroup pela primeira vez.
2. Lê e valida os três arquivos de cota, exigindo valores finitos dentro do orçamento.
3. Reobserva PID, início do processo, UID, seccomp e cgroup, recusando divergências.
4. Relê os **três arquivos de cota** pelo mesmo caminho e exige igualdade de memória, número de processos, quota de CPU e período entre as duas leituras.
5. Publica somente os valores observados de forma consistente; falha sem emitir resultado positivo se a cota mudar ou ficar ilimitada.

Os leitores conservam as proteções PE-S2.31: no máximo 16.384 bytes por arquivo, leitura até EOF, `O_RDONLY|O_CLOEXEC|O_NOFOLLOW`, NUL rejeitado e descritor fechado.

## Testes regressivos

`tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py` exercita leitura dupla de cada limite, alteração **ainda válida** de memória, pids e CPU entre os dois passes, relaxamento para `max` no segundo passe e recusa por troca de identidade do PID **antes** da segunda leitura das cotas.

Todos esses testes são sintéticos/localmente controlados. Mesmo duas leituras iguais **não garantem imutabilidade ao longo da execução** nem substituem testemunho independente de controle de recursos. A VM Arch nativa, o host QEMU/libvirt do revisor e as evidências de execução simultânea de Ghidra, cgroup e seccomp continuam pendentes na [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48).

**Autorização:** `independent_vm_attestation=false`, `release_authorized=false`; PR #47 Draft, sem merge, APK, OTA, release ou execução de PE Windows desconhecido.
