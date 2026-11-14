# PE-S2.39 | Probe de API KVM sobre descritor fixado (HOLD)

## Risco remanescente da PE-S2.38

A PE-S2.38 passou a recusar links simbólicos e dispositivos que não fossem de caractere com major 10, minor 232 em `/dev/kvm`. Isso evita falsas identificações triviais, mas um nó de dispositivo com metadados parecidos pode não responder de fato como KVM. Além disso, o inode poderia mudar entre `lstat()` e qualquer uso posterior do caminho.

## Novo teste de pré-condição

A função `_require_kvm_device()` em `tools/pe_arch_vm_s2_21_reviewer_host_readiness.py` agora:

1. Usa `os.lstat("/dev/kvm")` e recusa links simbólicos; exige dispositivo de caractere major 10/minor 232.
2. Abre o caminho com **`O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK`**, sem escrever no dispositivo ou criar VM.
3. Usa `os.fstat(fd)` e confere o **mesmo inode e filesystem** (`st_ino`, `st_dev`) obtido em `lstat`, além de revalidar tipo e números do dispositivo no FD real.
4. Executa somente **`fcntl.ioctl(fd, KVM_GET_API_VERSION)`**, comando da API KVM codificado por `_IO(0xAE, 0x00)` (`0xAE00`). O resultado precisa ser exatamente **inteiro 12**.
5. Fecha o FD sempre, inclusive quando o dispositivo muda, `fstat()` falha ou o ioctl rejeita. Qualquer falha impede `virsh` e devolve `REJECTED_PE_S2_21_REVIEWER_HOST_NOT_PROVEN` no modo CLI opt-in.

O código **não chama** `KVM_CREATE_VM`, não inicia guest, não instala módulos, não modifica configuração libvirt e não executa binário PE Windows.

**Fonte primária:** [KVM API, § 4.1, KVM_GET_API_VERSION](https://www.kernel.org/doc/html/latest/virt/kvm/api.html) informa retorno 12 e distingue a criação de VM via `KVM_CREATE_VM`.

## Testes regressivos

`tests/test_pe_arch_vm_s2_21_reviewer_host_readiness.py` inclui:
- Aceitação *somente sintética* de inode estável 10:232 com `ioctl(KVM_GET_API_VERSION) == 12`, validando flags de abertura somente leitura e fechamento.
- Recusa de troca do inode, filesystem ou número de dispositivo entre `lstat` e `fstat`, antes do ioctl.
- Recusa de respostas de API 0/11/13, `True`, `12.0` ou `None`.
- Recusa de erro de `open`, `fstat` ou `ioctl`, preservando fechamento e bloqueando `virsh` quando a API não é 12.

CI testa a lógica do ioctl via mocks, **não usa um /dev/kvm real nem autentica um host externo**. O teste negativo do runner CI continua recusando o host antes de consultar KVM ou libvirt.

## Limitações e HOLD

Responder 12 **não autentica** a origem do host: um ambiente adulterado ainda poderia simular o ioctl. A confirmação de propriedade do hipervisor, controle humano independente, guest Arch nativo, PID real do Ghidra, limites seccomp/cgroup, journald, cleanup e cronologia BEFORE → WORK → AFTER continua sendo requisito externo.

A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) permanece OPEN. A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece Draft sem merge. `independent_vm_attestation=false` e `release_authorized=false`; sem APK/OTA, release ou execução de PE Windows desconhecido.
