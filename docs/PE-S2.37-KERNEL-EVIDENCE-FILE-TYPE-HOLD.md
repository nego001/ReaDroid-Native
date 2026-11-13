# PE-S2.37 | Arquivos de evidência regulares, sem FIFO bloqueante (HOLD)

## Risco identificado

O observador local PE-S2.25 já exige caminho absoluto canônico, abre diretórios ancestrais sem symlinks (S2.33), limita cada leitura a 16 KiB até EOF (S2.31), confere UID/seccomp e cotas (S2.32–34), rejeita PIDs inativos (S2.35) e mantém `pidfd` (S2.36). Porém `os.open(..., O_RDONLY | O_NOFOLLOW)` no arquivo final **não exigia que o descritor representasse um arquivo regular**.

Num caminho desviado em um ambiente não confiável ou numa árvore de teste, um FIFO (pipe nomeado) poderia causar **espera indefinida na abertura**, antes da primeira leitura ou do limite de 16 KiB. Um diretório ou dispositivo especial também não é uma fonte válida de `/proc/PID/stat`, `status`, `cgroup` ou de `memory.max`, `pids.max`, `cpu.max`.

Referências Linux: [fifo(7)](https://man7.org/linux/man-pages/man7/fifo.7.html) e [open(2)](https://man7.org/linux/man-pages/man2/open.2.html).

## Implementação

`tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py::_read_bounded` agora:

- Abre o arquivo final ancorado no `dir_fd` do diretório validado com `O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK`.
- Logo após `open`, chama `os.fstat(fd)` e exige `stat.S_ISREG(...)` **sobre o próprio descritor**, sem reconsultar o nome e sem seguir symlinks.
- Recusa arquivo FIFO, diretório, dispositivo e outros tipos de inode **antes de `os.read`**.
- Fecha todos os descritores com `ExitStack` mesmo em falha de `fstat`, mantendo limite de tamanho, EOF, rejeição de NUL e o conjunto de verificações S2.31–S2.36.

`O_NONBLOCK` impede a espera de abertura de FIFO somente leitura sem escritor. Ele **não promete tempo máximo de I/O para arquivos regulares** e não torna o observador um mecanismo contínuo de segurança da execução.

## Regressões

Quatro testes novos em `tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py`:

1. FIFO real sem escritor deve ser recusado **sem chamada de `os.read`**, sem ficar bloqueado no `open`.
2. Diretório aberto como arquivo de evidência deve ser recusado.
3. Erro de `fstat` deve falhar fechado antes de ler.
4. Em Linux, a leitura real de `/proc/<PID do próprio teste>/stat` continua aceita como arquivo regular, sem sinalizar ou modificar o processo.

Os testes sintéticos de leituras curtas, limite de 16 KiB e limpeza de descritores foram ajustados para representar a nova verificação de tipo.

## Aprovação e custódia

A inspeção de tipo de inode **não comprova a origem do guest**, identidade verdadeira do Ghidra, isolamento contínuo, journald efetivo ou independente custódia da execução. A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) continua exigindo host QEMU/libvirt controlado por revisor, VM Arch nativa e provas correlacionadas BEFORE → WORK → AFTER.

A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece **Draft / sem merge**, `independent_vm_attestation=false`, `release_authorized=false`. Sem publicação APK/OTA, release ou execução de PE Windows desconhecido.
