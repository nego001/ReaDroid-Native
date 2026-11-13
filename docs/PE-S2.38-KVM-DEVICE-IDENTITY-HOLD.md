# PE-S2.38 | Validação do dispositivo real /dev/kvm no host revisor (HOLD)

## Falha no preflight S2.21

O preflight do host em `tools/pe_arch_vm_s2_21_reviewer_host_readiness.py` usava `os.stat("/dev/kvm")` e exigia somente `stat.S_ISCHR`. Essa verificação segue symlinks e aceita **qualquer dispositivo de caractere**, como `/dev/null`. Em um host mal configurado ou em ambiente de prova adulterado, `/dev/kvm` poderia apontar para outro dispositivo e ainda assim satisfazer essa verificação.

## Correção implementada

- `os.lstat("/dev/kvm")` examina a entrada final **sem seguir link simbólico**.
- O inode precisa ser um **dispositivo de caractere** com `os.major(st_rdev) == 10` e `os.minor(st_rdev) == 232`, alocação documentada pelo kernel para KVM.
- Recusar caminho ausente, inacessível, diretório, arquivo regular, link simbólico e dispositivo de caractere diferente **antes de consultar virsh**.
- Não abrir `/dev/kvm` com permissão especial, não enviar ioctls, não iniciar VM e não modificar host/guest.

Fontes: [dispositivos Linux, major 10 minor 232](https://www.kernel.org/doc/html/latest/admin-guide/devices.html) e [documentação Linux misc devices](https://www.kernel.org/doc/html/v4.19/admin-guide/devices.html).

## Testes

O módulo `tests/test_pe_arch_vm_s2_21_reviewer_host_readiness.py` inclui três métodos extras que verificam:

1. Dispositivo local simulado com `S_IFCHR` e `st_rdev=10:232`.
2. Recusa de symlink (inclusive para o mesmo número de dispositivo), `/dev/null` (1:3), major errado, minor errado, arquivo regular e diretório.
3. Recusa de `lstat()` indisponível ou sem permissão.

A CI contém apenas verificação **simulada desses inodes** e o controle negativo do runner. Ela não possui um revisor, host KVM independente, domínio libvirt verificado nem VM Arch nativa sob controle externo.

## Interpretação e bloqueio

A identidade local do dispositivo **não atesta propriedade ou independência do host**: `mknod` e interfaces expostas por um contêiner podem inclusive reproduzir metadados de dispositivo. O preflight precisa continuar rejeitando containers/CI reconhecidos e o parecer externo segue indispensável.

A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) continua OPEN. A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece Draft, sem merge. `independent_vm_attestation=false`, `release_authorized=false`. Sem lançamento, APK/OTA ou execução de PE Windows desconhecido.
