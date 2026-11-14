# PE-S2.35 | Recusa de processo zumbi, morto ou parado (HOLD)

## Problema

O observador local `tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py` compara PID/starttime, UID, estado seccomp e cgroup em três passagens, além de comparar cotas cgroup v2 em duas passagens (PE-S2.34). Entretanto, a função `_start_ticks()` extraía a hora de criação de `/proc/PID/stat` sem validar seu **campo 3 (state)**.

No Linux, uma tarefa terminada pode persistir temporariamente em `/proc` no estado `Z` (**zumbi**), preservando o PID e o horário de criação. Assim, informações consistentes de PID e cotas não bastavam para recusar uma tarefa que já havia terminado. O mesmo observador não deve representar um processo morto (`X`/`x`), parado (`T`) ou sob parada de rastreamento (`t`) como um processo em execução.

Referência do kernel e man-pages: [proc_pid_stat(5), manual do Arch Linux](https://man.archlinux.org/man/proc_pid_stat.5.en).

## Alteração

- Ao interpretar `/proc/PID/stat`, exigir **um único estado permitido**: `R` (runnable), `S` (sleep) ou `D` (uninterruptible sleep).
- Recusar `Z`, `X`, `x`, `T`, `t`, `I` (idle kernel thread), demais estados antigos e valores desconhecidos, inclusive tokens não canônicos. Os estados `R/S/D` são permitidos em cada leitura; mudar entre eles durante a amostragem não equivale, por si só, à troca do PID.
- Aplicar essa verificação em **cada uma das três leituras** do campo 22 (starttime): início, depois da primeira passagem das cotas e após a segunda passagem.
- Preservar os limites de 16 KiB/EOF, descritores ancorados sem symlinks, dupla verificação de cotas, seccomp filtrado, UID não root, condição de caminho cgroup e retorno sempre HOLD.

## Contratos de regressão

`tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py` acrescenta:

1. Recusa de estados `Z/X/x/T/t/I/W/K/P`, estado desconhecido e token com mais de um caractere no `stat`.
2. Aceitação local restrita de `R/S/D` com flags de atestação e release sempre falsas.
3. Processo se tornando `Z` durante a **terceira** observação do PID (após as cotas), mantendo o mesmo starttime: deve recusar.

## Gate externo

Esses testes **não provam** que Ghidra estava ativo durante toda a análise nem que o processo observado pertencia a ele. A prova real exige revisor independente, host QEMU/libvirt e VM Arch nativa, witness de PID/cgroup/seccomp durante a sessão e evidências BEFORE→WORK→AFTER.

[Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) permanece OPEN. [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece Draft/unmerged. `independent_vm_attestation=false`, `release_authorized=false`. Nenhuma publicação APK/OTA, release ou execução de PE Windows desconhecido.
