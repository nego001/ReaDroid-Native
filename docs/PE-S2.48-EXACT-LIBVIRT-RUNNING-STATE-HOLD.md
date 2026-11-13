# PE-S2.48 | Estados `running` exatos entre captura e revisão offline (HOLD)

## Falha de contrato identificada

S1.70 (`capture_host_domain`) e S1.71 (`capture_guest_kernel_observation`) utilizavam `.casefold()` ao validar o estado do domínio, aceitando `RUNNING` ou `Running`. Os mesmos valores eram registrados **sem normalização** dentro dos logs privados. Já os leitores S1.71 (`_check_snapshot`) e S1.73 (`_review_host` / `_review_guest`) exigem exatamente a string `running` em cada estado do envelope.

Consequência: a captura poderia ser relatada como bem-sucedida, possuir SHA-256 correto e ainda assim ser impossível de validar na revisão offline. A falha foi identificada por auditoria do produtor/consumidor, não por execução real de um hipervisor.

## Correção

- `tools/pe_arch_vm_s1_70_readonly_libvirt_host_capture.py`: exigir `first_state == "running"` e `final_state == "running"`, bem como `info_state == ["running"]`, antes da publicação do primeiro arquivo. Preserva texto original, não reescreve a evidência.
- `tools/pe_arch_vm_s1_71_guestinfo_os_capture.py`: exigir `before_state == "running"` e `after_state == "running"` antes de publicar a autodeclaração do guest agent.
- A política é conservadora: se uma versão futura ou localidade libvirt devolver outra grafia, o revisor deve investigar a divergência e manter **HOLD**, não realizar uma normalização invisível de dados.
- Não foram modificados os formatos de registros assinados, pins externos, chaves Ed25519, o comando `virsh --readonly` ou os resultados de autorização.

## Regressões

Três métodos novos cobrem dez adulterações de estado em saída `virsh` simulada (duas grafias × estados inicial/final de S1.70, duas grafias no campo `State:` de `dominfo`, e duas grafias × estados inicial/final de S1.71):

1. `test_s2_48_host_mixed_case_domstate_refused_before_publication`
2. `test_s2_48_host_mixed_case_dominfo_refused_before_publication`
3. `test_s2_48_guest_mixed_case_domstate_refused_without_record`

Todos exigem exceção explícita e **nenhum arquivo de evidência publicado**. Os testes positivos anteriores permanecem para `running` literal e continuam verificando a compatibilidade do envelope com S1.71/S1.73. A CI já inclui as suites S1.70, S1.71 e S1.73 tanto em Ubuntu quanto em Arch userspace, mas não constitui homologação independente.

## Bloqueios preservados

- [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48): **OPEN** até revisão humana independente com host QEMU/libvirt real, VM Arch nativa, evidência BEFORE → WORK → AFTER, PID do Ghidra, cgroup v2/seccomp simultâneos, journald e cleanup.
- [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47): **Draft**, sem merge.
- `independent_vm_attestation=false`, `release_authorized=false`. Nenhuma execução de PE desconhecido, release, APK ou OTA está autorizada.
