# PE-S2.11 | Native work tmpfs ENOSPC preflight (LOCAL, release HOLD)

**Status:** implementação e regressões criadas; homologação em VM Arch externa **pendente**. Sem merge, APK, OTA ou execução de PE desconhecido.

## O que foi desenvolvido

O módulo `tools/pe_native_work_enospc.py` usa a verificação local de `require_bounded_work_mount()` da PE-S2.08 antes de qualquer escrita, e roda **somente** na aceitação sintética explicitamente solicitada da VM Arch descartável do revisor. Abre um FD de diretório protegido, cria um arquivo privado via `O_NOFOLLOW|O_EXCL` dentro do `tmpfs` dedicado (64–512 MiB), reserva 1 MiB por `posix_fallocate` e exige diminuição correspondente de espaço disponível. Em seguida tenta reservar **tamanho total do próprio tmpfs + 1 MiB** e exige o erro real do kernel `ENOSPC`, sem realizar um loop de gravação capaz de encher um disco host arbitrário. Sempre fecha e remove o arquivo temporário, depois verifica que o tamanho da montagem permaneceu estável e que o espaço foi recuperado.

**Risco e limite:** `posix_fallocate` pode reservar páginas reais de memória em um `tmpfs`. Isso ainda é um teste que consome recursos, por isso pertence SOMENTE à VM descartável e autorizada pelo revisor, com reserva de memória adequada e snapshot antes da execução. Não rodar no notebook pessoal. O máximo de reserva solicitado é o tamanho da montagem (<=512 MiB) + 1 MiB e o resultado deve ser `ENOSPC`; um syscall que não imponha cota é rejeitado.

A verificação entra no `run_acceptance()` **após** o preflight Arch, validação de montagem e observações do journald, mas **antes** do primeiro `systemd-run`/smoke de cgroup, Ghidra e subprocesso de PE sintético. O launcher preserva modo padrão sem execução. Testes CI para esse novo módulo usam **mocks**, não montam `/work` do host. A prova real de `tmpfs` Ubuntu da PE-S2.10 continua separada.

## O que a PE-S2.11 NÃO demonstra

A prova é **local**, não certifica o operador, hipervisor, configuração carregada pelo journald, cotas de outros locais, defesa contra remount com privilégio nem os cgroups+seccomp simultâneos na VM independente. Não altera o esquema v2 de recibo estrito nem acrescenta novo campo de aprovação: o resultado do helper é um gate pré-escopo, **não um atestado externo preservado**. Os revisores ainda precisam conferir evidência independente da execução no mesmo SHA. A PR deve permanecer Draft até lá.
