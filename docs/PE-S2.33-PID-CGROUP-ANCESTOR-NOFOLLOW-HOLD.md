# PE-S2.33 | Leitura de evidências com caminhos ancorados sem symlink (HOLD)

## Risco demonstrado

Até PE-S2.32, o snapshot local S2.25 já recusava symlink na **última componente** (`O_NOFOLLOW`) de arquivos como `/proc/PID/status`, `/proc/PID/stat`, `/proc/PID/cgroup` e `/sys/fs/cgroup/.../memory.max`, `pids.max`, `cpu.max`. Isso **não** impede um link simbólico no diretório do PID ou em algum ancestral de cgroup de redirecionar o observador a outro conjunto de dados.

## Correção

`tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py` passou a reutilizar `open_absolute_directory_nofollow()` de `tools/pe_nofollow_paths.py`:

- Caminhos de diretório precisam ser absolutos, canônicos, sem `.` e `..`.
- Abertura ancorada em `dir_fd`, a partir de `/`, com `O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW` em **cada** componente ancestral.
- O arquivo final abre com `O_RDONLY | O_CLOEXEC | O_NOFOLLOW` e `dir_fd` do diretório já fixado.
- `ExitStack` fecha o arquivo e todos os descritores de diretórios, inclusive se `os.read()` falhar.
- Mantidas as leituras até EOF com teto de **16.384 bytes**, rejeição de conteúdo vazio/NUL, cotas finitas e dupla observação de PID, estado seccomp e cotas cgroup v2 da PE-S2.32.

## Verificações

O contrato em `tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py` inclui casos de symlink no diretório do PID e em um ancestral de cgroup, além de caminho relativo/não canônico e ajuste dos testes de leitura simulada para confirmar que o arquivo é aberto relativo ao descritor de diretório.

Todas as mudanças são **somente leitura**, sem sudo, montagem, serviço iniciado, execução de PE Windows, publicação de APK/OTA ou release. Caminhos artificiais dos testes não são expostos pela CLI.

## Limites

O resultado permanece uma observação local e pontual. Uma travessia ancorada evita redirecionamento por symlink, mas não certifica a identidade de Ghidra, a proveniência do guest Arch, a efetividade dos limites durante toda a execução ou controle do host pelo revisor externo.

A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) ainda exige execução e custódia por revisor independente em host QEMU/libvirt real e VM Arch nativa, com testemunho correlacionado BEFORE → WORK → AFTER. A PR #47 continua Draft, **sem merge**. `independent_vm_attestation=false` e `release_authorized=false`.
