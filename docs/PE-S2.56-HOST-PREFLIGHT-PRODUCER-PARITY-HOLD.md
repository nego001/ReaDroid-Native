# PE-S2.56 | Preflight S2.21 alinhado à captura S1.70/S1.71 (HOLD)

## Desvio identificado

O preflight S2.21 usava o resolvedor genérico `gate._trusted_vm_tool("virsh")`, que pode aceitar alias root-owned de um único symlink dentro de `/usr/bin`, desde que a árvore de diretórios seja confiável. Porém, desde PE-S2.55, S1.70/S1.71 exigem especificamente `host._trusted_virsh_executable()`, que **rejeita symlinks** e exige o caminho literal `/usr/bin/virsh` ou `/bin/virsh`. Assim, o preflight poderia anunciar `LOCAL_PE_S2_21_READONLY_LIBVIRT_HOST_CANDIDATE_HOLD` em uma máquina onde a coleta seguinte falharia por violar a confiança de binário.

Além disso, `_info_matches()` consultava apenas a estrutura `dominfo` (`_validate_dominfo_shape`), sem reaplicar o sanitizador exato `_checked_text` da captura S1.70. A S2.53 exige recusa de espaços no início/fim e LF excedente. Esse segundo controle ainda não era aplicado à rotina de `_info_matches` isolada.

## Correções

- `_host_prerequisites()` exige diretamente `host._trusted_virsh_executable()`, propagando uma rejeição genérica para o preflight. O caminho é o **mesmo** que os produtores S1.70 e S1.71 usam, sem permissões extras.
- O preflight continua verificando primeiro o host não-root, marcadores de CI/container, `/dev/kvm`, diretório privado vazio e `systemd-detect-virt --container --quiet`.
- `_info_matches()` reaplica o `host._checked_text(..., "dominfo")` e exige igualdade textual antes de checar labels/UUID/estado. Não normaliza espaços ou quebras de linha.
- O estado `CANDIDATE` permanece somente uma **candidatura local à análise externa**. Não constitui atestado do hipervisor, origem do guest ou do revisor.

## Testes

Três novos métodos adversariais no preflight S2.21 confirmam que falha de confiança do produtor bloqueia todos os comandos libvirt, respostas `dominfo` com framing bruto inválido não geram `CANDIDATE` e o sanitizador compartilhado continua obrigatório. O teste positivo de pré-requisitos foi atualizado para requerer o novo resolvedor, sem simular uma VM real.

## Ajuste da regressão do Ubuntu

Na primeira execução, o teste `test_s2_56_alias_or_untrusted_virsh_never_yields_candidate` falhou porque o mock de `os.geteuid()` (módulo compartilhado) interferia na verificação anterior de propriedade da pasta privada. A asserção foi restrita a `_host_prerequisites()`, que é o componente responsável por verificar o executável depois dos pré-requisitos simulados. A captura S1.70/S1.71 e a rotina de produção S2.21 permanecem inalteradas; o teste continua provando bloqueio antes de consulta a `virsh`.

## HOLD externo

[PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece Draft/unmerged; [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) permanece OPEN. A CI não equivale a provas humanas do host QEMU/libvirt independente, VM Arch nativa, PID do Ghidra, cgroup v2/seccomp conjuntos, journald, cleanup e BEFORE → WORK → AFTER. Nenhuma execução de Windows PE desconhecido, merge, APK, OTA ou release está autorizada.
