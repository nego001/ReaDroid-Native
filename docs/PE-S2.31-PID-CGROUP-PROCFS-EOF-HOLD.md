# PE-S2.31 | EOF obrigatório em evidências de PID, cgroup e cotas (HOLD)

**Situação:** reforço dos diagnósticos **locais** S2.25. A PR #47 continua Draft/unmerged; a Issue #48 continua aberta. **Sem atestação independente**, autorização de release, APK, OTA ou execução de PE Windows desconhecido.

## Por que é necessário

A função `_read_bounded()` do arquivo `tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py` antes efetuava **uma única chamada** `os.read(fd, MAX_BYTES + 1)` para arquivos do kernel: `/proc/PID/stat`, `status`, `cgroup` e os arquivos de cgroup v2 `memory.max`, `pids.max`, `cpu.max`.

Um `read()` pode devolver **menos bytes do que foram solicitados** sem significar que toda a saída foi consumida. Caso a primeira parte parecesse válida, um registro contraditório posterior podia ficar sem análise, levando a um **falso diagnóstico local** de PID, cgroup ou quota.

## Alteração implementada

A leitura agora repete `os.read` **até EOF** com orçamento máximo de `MAX_BYTES + 1 = 16.385` bytes, sem escrita e sem iniciar processos. Se houver mais que 16.384 bytes, um byte NUL, conteúdo vazio, symlink na última componente ou erro de leitura, a função recusa. `O_RDONLY | O_CLOEXEC | O_NOFOLLOW` continuam obrigatórios e o descritor é sempre fechado.

O snapshot S2.25 ainda compara **duas observações** de início de PID, UID, estado do seccomp e cgroup, entre leituras das cotas **finitas** do kernel. Ele não comprova que o processo é Ghidra, que as cotas realmente acompanharam uma execução completa, ou que a infraestrutura pertence a um revisor independente.

## Regressão sintética

O arquivo `tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py` inclui novos testes para:

- Primeiro bloco de cgroup aparentemente válido seguido por entrada contraditória.
- Cota de `pids.max` aparentemente válida seguida de conteúdo adicional.
- Arquivo maior que o limite mesmo quando enviado em blocos.
- Fechamento do descritor quando `os.read` falha.
- Rejeição de byte NUL e symlink no caminho final.

Esses testes são executados pela CI Ubuntu e pelo **contêiner Arch Linux userspace** já existentes. Não são provas de VM Arch nativa, de host QEMU/libvirt ou de autenticação humana de evidências.

## Bloqueio e próxima ação

A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) exige revisor independente e host QEMU/libvirt real, guest Arch nativo descartável, testemunho da identidade do processo Ghidra e das cotas cgroup v2/estado seccomp **ao mesmo tempo**, além de armazenamento journald efetivo, encerramento e cronologia BEFORE→WORK→AFTER. O [handoff externo PE-S2.24](PE-S2.24-EXTERNAL-REVIEWER-EXECUTION-HANDOFF-HOLD.md) continua obrigatório.

**Não interpretar resultado sintético de CI ou saída local HOLD como `independent_vm_attestation=true` ou `release_authorized=true`.**
