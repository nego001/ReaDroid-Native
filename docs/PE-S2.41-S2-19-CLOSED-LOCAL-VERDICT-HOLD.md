# PE-S2.41 | Contrato fechado do veredito S2.19 consumido pela S2.22 (HOLD)

## Lacuna corrigida na cadeia de revisão

A PE-S2.40 estabeleceu um conjunto fechado de 13 campos para a saída da S2.22 quando consumida pelo registro de lacunas S2.23. A etapa anterior da mesma cadeia, **S2.22 consumindo o resultado de `verify_reviewer_session()` da S2.19**, ainda aceitava campos extras ou alegações não inspecionadas. Por exemplo, `independent_host_control_attested=true` ou `unknown_windows_pe_execution_authorized=true` poderiam surgir no retorno da S2.19 sem causar rejeição na S2.22.

Isso constituía **deriva de esquema e possível mascaramento de alegações**, não uma comprovação de que ocorreu atestação externa ou fraude de evidência.

## Correção no código

`tools/pe_arch_vm_s2_22_external_reviewer_pins.py` agora define `S2_19_RESULT_FIELDS` com **14 chaves** e exige a forma exata `type(observed) is dict` e `set(observed) == S2_19_RESULT_FIELDS`.

A verificação exige, por identidade:

- `True`: assinatura V1/V2/V3, vínculo dos hashes BEFORE/AFTER, igualdade do recibo nativo com o pin assinado V1, verificação do desafio/fontes do recibo e revalidação do checkout.
- `False`: independência administrativa do host, execução do kernel guest atestada, cronologia atestada, cota efetiva do journald, atestação de VM, autorização de release, autorização de execução PE desconhecido e publicação APK/OTA.

Um campo novo, ausente ou renomeado, uma alegação indevida de aprovação ou um tipo incorreto são recusados, mesmo quando o pacote de hashes e as assinaturas locais são consistentes. Mudanças futuras no protocolo exigirão revisão consciente dos dois módulos, não aceitação silenciosa. A leitura de pins continua privada, sem escrita, sem novas permissões, sem criar VM e sem executar binários PE.

## Testes regressivos

`tests/test_pe_arch_vm_s2_22_external_reviewer_pins.py` adiciona quatro contratos que cobrem:

1. Retorno local de S2.19 com **14 campos exatos**, mantendo as sete provas externas pendentes e o estado HOLD.
2. Campos adicionais alegando atestação, novas provas ou metadados não previstos.
3. Exclusão de qualquer das **14** chaves, sem assumir valor padrão.
4. Todas as oito alegações externas/release com `True` e os cinco resultados locais com tipo inválido (`1` no lugar de `True`).

Os testes usam assinaturas Ed25519 reais de chaves descartáveis na fixture, **mas** retorno S2.19, recibo/checkout e libvirt podem ser simulados. Isso não representa um host independente ou VM Arch nativa.

## Limitação da homologação

Validação de esquema não autentica a pessoa que revisa, o host QEMU/libvirt, o boot de guest Arch ou o PID real de Ghidra, e não equivale à observação simultânea de seccomp/cgroup/journald nem prova de cleanup/cronologia. Os originais BEFORE → WORK → AFTER permanecem sob custódia do revisor humano independente.

[Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48): **OPEN**. [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47): **Draft/unmerged**. `independent_vm_attestation=false`, `release_authorized=false`. Não publicar APK/OTA, não fazer merge/release e não executar PE Windows desconhecido.
