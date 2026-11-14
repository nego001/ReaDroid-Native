# PE-S2.47 | Campos canônicos e exclusivos em `virsh dominfo` (HOLD)

## Inconsistência identificada

A PE-S2.46 recusava marcadores do envelope de evidências apenas quando apareciam no início da linha. Uma linha com espaço inicial, variação de maiúsculas ou um `Name:`/ `Id:` duplicado podia ser armazenada pelo produtor S1.70 e passar pelo leitor S1.71, pois as verificações anteriores reconheciam somente as grafias exatas de `Name:`, `UUID:` e `State:`. Um hash SHA-256 novo não torna uma observação textual enganosa autenticamente proveniente do host.

Não foi observada exploração em hypervisor real; a lacuna foi identificada por análise de código e exercitada com saídas `virsh` sintéticas.

## Correção

- `tools/pe_arch_vm_s1_70_readonly_libvirt_host_capture.py`: função `_validate_dominfo_shape()` verifica cada linha de `dominfo` como `Label: valor`, com nome legível e valor não vazio. Rejeita prefixo de espaço, rótulo com espaço final, `=` em qualquer parte da linha, linhas sem dois-pontos, caracteres de controle e rótulos duplicados sem considerar maiúsculas/minúsculas.
- Os marcadores reservados da PE-S2.46 continuam proibidos. O produtor valida antes de `_publish_new_file`; campos suspeitos não viram arquivo privado nem recibo.
- `tools/pe_arch_vm_s1_71_guestinfo_os_capture.py` chama **exatamente a mesma função** no registro S1.70 com hash externo, mesmo que o operador forneça novos hashes. O S1.73 já chama `guest._check_snapshot()`, herdando essa verificação.
- O `virsh` continua com conexão `--readonly`, argumentos explícitos, sem shell. O formato de assinatura Ed25519 e os arquivos externos pinados não foram alterados.

A política aceita campos comuns como `CPU(s):`, `CPU time:`, `Max memory:`, `Persistent:`, `Autostart:` e `Security model:`. Um formato futuro de libvirt incompatível deve gerar **HOLD para revisão**, não um ajuste silencioso da prova.

## Regressões

- Três testes novos em `tests/test_pe_arch_vm_s1_70_readonly_libvirt_host_capture.py`: injeção de campos disfarçados/duplicados/sem formato, compatibilidade positiva com saída libvirt estendida e tipos de entrada inválidos.
- Um teste novo em `tests/test_pe_arch_vm_s1_73_two_record_review.py`: **ambos** os registros são reconstruídos com hashes coerentes, mas a revisão offline rejeita a linha camuflada.
- Não são provas de execução numa VM Arch independente; `virsh` é simulado nos casos adversariais.

## Homologação e publicação

A cadeia continua **HOLD**: `independent_vm_attestation=false`, `release_authorized=false`. A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) exige revisor humano independente, host QEMU/libvirt sob custódia externa e VM Arch nativa com evidências de Ghidra/seccomp/cgroups/journald, limpeza e BEFORE → WORK → AFTER.

A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) continua Draft e não mesclada. Sem APK, OTA, release ou execução de Windows PE desconhecido.
