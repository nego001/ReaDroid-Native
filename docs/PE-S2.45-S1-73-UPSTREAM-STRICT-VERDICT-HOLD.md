# PE-S2.45 | Contrato exato S1.73 consumido pelo libvirt S2.15 (HOLD)

## Problema

Depois da PE-S2.44, V2 exigia contratos fechados para V1/S1.63 e para S2.15; entretanto, o próprio módulo S2.15 `_offline_pins()` consumia o relatório S1.73 conferindo apenas quatro campos (`status`, `semantic_records_checked`, `independent_vm_attestation`, `release_authorized`). Novos indicadores de suposta origem independente, autorização de Windows PE, remoção de flags de segurança, ou valores de tipo errado poderiam passar despercebidos na fronteira entre o revisor de duas observações e o coletor de counters.

## Implementação

Em `tools/pe_arch_vm_s2_15_readonly_host_domstats.py`:

- `S1_73_VERDICT_FIELDS`: **20 campos exatos**. Exige `dict` de tipo exato; sem campos novos ou ausentes.
- Seis vínculos locais entre host/guest, hashes, domínio, commit e challenge exigidos como `True` por identidade.
- `semantic_records_checked`: `int` exato igual a 2; não aceita `True` no lugar de 1, nem contagens diferentes.
- `other_unverified_records`: lista exata, na ordem original, das duas observações restantes em `semantic.UNVERIFIED`.
- `guest_os_id_self_reported` e `guest_kernel_release_self_reported`: strings presentes, limitadas a 128 caracteres, sem caracteres de controle. São **autodeclarações do agente guest**, não provas do kernel.
- Nove indicadores de consulta live, independência do host, verificação de kernel/seccomp/cgroups/cleanup, atestação de VM, execução de PE e publicação exigidos `False` por identidade.
- Falhas terminam com `HostDomstatsError` antes da busca de `virsh` no caminho de captura.

## Regressões

Quatro novos testes no `tests/test_pe_arch_vm_s2_15_readonly_host_domstats.py` cobrem contrato positivo e parser real de arquivos sintéticos, campos extras/ausentes e flags de homologação forjadas, tipos/contagens/listas erradas, strings de guest inválidas e falha antes de consultar o hipervisor. Os retornos adversariais S1.73 são **simulados**, sem execução de VM ou libvirt reais.

A suíte já está inscrita nos jobs Ubuntu e Arch userspace de `.github/workflows/pe-ghidra-sandbox-real.yml`. Sem alterar o protocolo de captura, hashes externos ou assinaturas Ed25519 anteriores.

## Sem homologação externa

A PE-S2.45 fortalece apenas a **consistência do contrato local**. Relatórios textuais e counters não provam que um revisor humano controla fisicamente um host QEMU/libvirt independente, que o Arch tem kernel próprio, nem que seccomp/cgroups/journald/cleanup funcionaram simultaneamente numa sessão Ghidra real. O mecanismo não abre caminho de release.

- [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47): Draft, não mesclar.
- [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48): OPEN e bloqueadora.
- `independent_vm_attestation=false`, `release_authorized=false`; nenhum APK, OTA, release ou Windows PE desconhecido autorizado.
