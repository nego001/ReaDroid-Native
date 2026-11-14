# PE-S2.43 | Contratos fechados V2 e BEFORE/AFTER consumidos pela V3 (HOLD)

## Problema

A PE-S2.42 fixou a estrutura de V3, recibo e Git na passagem para S2.19. Entretanto, a função `_verified_upstream()` da V3 (`tools/pe_arch_vm_s2_18_signed_host_pair.py`) ainda conferia somente parte dos retornos do verificador V2 e do revisor dos dois registros de host. Campos externos e metadados adicionais poderiam ser ignorados silenciosamente. Entre eles: `host_hypervisor_independently_attested`, `guest_cgroups_seccomp_verified`, `apk_or_ota_publication_authorized`, `host_provenance_independently_attested` ou `samples_signed_in_s1_63_or_s2_16`.

Essas informações devem permanecer **False**, independentemente de consistência de SHA-256, assinaturas locais ou aumento declarado no contador de CPU do libvirt.

## Alteração

A função exige o formato exato dos dois vereditos de origem, sem tolerar campos desconhecidos nem omissões:

- `V2_VERDICT_FIELDS`: **11 campos**. Status V2 válido; assinatura V2, namespace específico, assinatura V1 rechecada, vínculo do sidecar e manutenção do manifesto V1 iguais a **True** por identidade. Alegações de host, guest, VM, release e APK/OTA obrigatoriamente **False**.
- `PAIR_VERDICT_FIELDS`: **9 campos**. Status das capturas *before/after*; hashes, domínio/sessão correlacionados e incremento de CPU relatado pelo libvirt iguais a **True** por identidade. Host, guest, assinaturas de capturas, VM e release obrigatoriamente **False**.

Qualquer tipo diferente de `dict`, campo novo/ausente, valor não booleano nos indicadores ou declaração contraditória provoca `SignedDomstatsExtensionError` antes que a V3 aceite o resultado como cadeia local consistente. Nenhuma mudança no protocolo de assinatura Ed25519 V1/V2/V3, sem consulta de live libvirt neste verificador, sem execução Windows PE e sem permissão de publicação.

## Regressões

Quatro testes novos em `tests/test_pe_arch_vm_s2_18_signed_host_pair.py`:

1. Contratos exatos positivos nos dois módulos, com status externo HOLD.
2. Resposta V2 alterada: chave extra mesmo com valor falso, chave removida, alegações de host/guest/publicação e indicadores `1` em vez de booleano.
3. Capturas *before/after* alteradas: chave extra, chave removida, suposta procedência independente, assinatura indevida ou indicador não booleano.
4. Retornos de tipo inválido como lista, string, inteiro e nulo rejeitados antes de formarem a verificação V3.

Os testes usam retornos simulados dos dois módulos para os casos adversariais. A suíte também mantém o exercício separado com **três assinaturas reais de chaves Ed25519 descartáveis**. Isso não demonstra a procedência do host/guest.

## Limite de segurança

Um contador CPU crescente não prova que o Ghidra executou na VM Arch nativa ou que o host pertence a um revisor independente. Permanecem indispensáveis originais BEFORE → WORK → AFTER sob custódia externa, evidências simultâneas PID/seccomp/cgroup/journald e limpeza da árvore de processos.

[Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48): OPEN. [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47): Draft e sem merge. `independent_vm_attestation=false`, `release_authorized=false`. Sem release, APK/OTA ou execução de Windows PE desconhecido.
