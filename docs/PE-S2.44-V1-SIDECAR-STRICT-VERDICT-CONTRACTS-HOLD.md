# PE-S2.44 | V1 e libvirt S2.15: vereditos completos no consumidor V2 (HOLD)

## Lacuna concreta

A PE-S2.43 fechou as respostas V2 e BEFORE/AFTER consumidas por V3. A verificação `_verified_upstream()` da própria V2 ainda selecionava apenas três campos do retorno V1 (S1.63) e quatro do revisor de counters libvirt S2.15. Uma mudança de protocolo que adicionasse `independent_vm_attestation=true` com outro nome, omitisse campos importantes ou substituísse contagens por booleanos poderia ser ignorada pelo consumidor.

Essa correção trata *deriva de contrato local*; **não** indica falsificação detectada em host real, nem comprova origem física.

## Correção implementada

Arquivo: `tools/pe_arch_vm_s2_16_signed_domstats_extension.py`.

- `V1_VERDICT_FIELDS`: **16 campos exatos**, inclusive identificação do observador, commit e SHA do manifesto fixados externamente. Exige cinco sinais locais com `is True`, contagem de quatro observações com tipo inteiro exato e seis alegações externas/liberação com `is False`.
- `SIDECAR_VERDICT_FIELDS`: **9 campos exatos**. Exige correlação de hashes e sessão como booleanos verdadeiros, `cpu_time_ns_as_reported_by_host` como inteiro positivo menor que `2**64`, e as quatro alegações de autenticação do hipervisor/guest, VM e release como booleanos falsos.
- Respostas não `dict`, omissões, campos extras (até com valor `False`), números usados como booleanos, contagens inexistentes ou identidades divergentes são recusados via `SignedDomstatsExtensionError`, **antes** de preparar/validar o suplemento V2.
- A semântica de assinaturas Ed25519 V1/V2/V3 e os formatos já assinados não mudam. Não há novo acesso live a libvirt no consumo offline.

## Regressões

Quatro métodos de `tests/test_pe_arch_vm_s2_16_signed_domstats_extension.py` exercitam vereditos exatos, campos inesperados/ausentes, alegações falsas, identidade e hashes trocados, booleano como contagem, CPU negativa/zero/maior ou igual a `2**64`, e tipos de retorno inválidos. Os ataques de esquema usam mocks apenas para a resposta entre módulos. A suíte existente mantém os exercícios reais de assinatura com chaves temporárias.

A CI da PR #47 roda a suíte em Ubuntu e Arch userspace e inclui o laboratório Ubuntu/Ghidra. **Arch userspace em contêiner não é uma VM Arch nativa independente.**

## Gate que permanece fechado

O relatório de libvirt registra counters fornecidos pelo próprio host; não autentica o proprietário, nem prova uma sessão Ghidra com seccomp e cgroup v2, controle real de journald, cronologia BEFORE → WORK → AFTER ou limpeza independente. Mesmo um pacote válido continua HOLD.

- [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47): manter Draft, não mesclar.
- [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48): bloquear até revisão humana independente em host QEMU/libvirt e VM Arch nativa.
- `independent_vm_attestation=false`, `release_authorized=false`, sem APK/OTA, release ou execução de PE desconhecido.
