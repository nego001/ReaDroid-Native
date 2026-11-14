# PE-S2.40 | Contrato fechado da saída S2.22 no registro de lacunas S2.23 (HOLD)

## Defeito de integração corrigido

O registro de lacunas S2.23 verificava o estado e um subconjunto dos campos da resposta de `pe_arch_vm_s2_22_external_reviewer_pins.review_custody()`, mas **não verificava o conjunto completo de chaves**. Uma atualização no produtor S2.22 poderia acrescentar um campo com alegação de homologação, de prova externa ou de autorização sem que o consumidor S2.23 percebesse a mudança. O registro descartava a chave nova e continuava a devolver seu relatório de pacote local consistente.

É uma **ambiguidade de contrato entre módulos**, não uma confirmação de que já ocorreu falsificação de provas nem uma maneira de autenticar o revisor.

## Implementação

`tools/pe_arch_vm_s2_23_external_gap_register.py` agora define `S2_22_RESULT_FIELDS` com **13 chaves permitidas** da resposta S2.22. Antes de considerar um pacote local correlacionado, exige:

- valor de tipo `dict` exato e `set(signed) == S2_22_RESULT_FIELDS`;
- os quatro campos de cadeia local e pins com `True` por identidade;
- as sete classes externas na mesma ordem da matriz `pins.UNPROVEN`;
- todas as alegações de independência, atestação, autorização de APK/OTA, execução de PE e release com `False` por identidade.

Qualquer campo **novo, ausente ou rebatizado**, mesmo que a alegação adicional seja `False`, provoca recusa. Isso obriga futuras mudanças de protocolo a passarem por revisão consciente em ambos os módulos. A verificação de assinaturas Ed25519 V1/V2/V3 e dos pins da S2.22 permanece intacta.

## Testes

Quatro contratos novos em `tests/test_pe_arch_vm_s2_23_external_gap_register.py`:

1. Saída S2.22 com as 13 chaves exatas e sete provas pendentes continua retornando apenas **HOLD**.
2. Campos extras simulando aprovação, prova de VM ou caminho de dado privado são recusados (mesmo valor `False`).
3. Remoção de **qualquer uma das 13 chaves** é recusada sem valor padrão silencioso.
4. Lista das sete classes em ordem alterada, tipo incorreto ou inteiro no lugar de `False` são recusados.

Os testes complementam o cenário já existente com assinaturas Ed25519 reais de chaves **descartáveis**, recebimento/checkout locais simulados e libvirt simulado. Não criam um host revisor nem uma VM Arch.

## Limite, privacidade e liberação

O verificador não recebe provas brutas de host/guest para torná-las públicas, não verifica a independência de um ser humano e **não oferece mecanismo de marcar nenhuma das sete classes como aprovada**. Não muda recibos, assinaturas ou flags de release.

Para resolver [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48), ainda é obrigatório um revisor independente com host QEMU/libvirt real e VM Arch nativa, observações de PID Ghidra + cgroup v2/seccomp/journald, cleanup, hashes externos e BEFORE → WORK → AFTER.

[PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) segue Draft/unmerged. `independent_vm_attestation=false`, `release_authorized=false`, sem APK, OTA, execução de PE desconhecido ou release.
