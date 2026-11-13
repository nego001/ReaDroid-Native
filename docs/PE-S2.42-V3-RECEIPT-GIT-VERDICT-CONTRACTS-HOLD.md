# PE-S2.42 | Contratos fechados de V3, recibo e Git na ponte S2.19 (HOLD)

## Problema observado

A PE-S2.41 exige o formato exato da saída de S2.19 antes de S2.22, e a PE-S2.40 faz o mesmo entre S2.22 e S2.23. A própria **S2.19**, contudo, verificava apenas alguns campos das respostas de três componentes anteriores:

1. `pe_arch_vm_s2_18_signed_host_pair.verify_signed_domstats_extension()` (assinatura V3 e controles da cadeia V1/V2);
2. `pe_arch_vm_receipt_verify.verify_local_receipt()` (recibo não assinado e manifest);
3. `pe_arch_vm_checkout_pin.verify_source_checkout_pin()` (commit fixado e árvore Git local).

Uma resposta com campos extras, omissões em campos antes ignorados ou alegações contraditórias de independência poderia ser silenciosamente reduzida a um relatório S2.19 local com HOLD. Era uma **deriva de contrato entre módulos**, não prova de que houve falsificação na execução externa.

## Correção

Em `tools/pe_arch_vm_s2_19_reviewer_session_handoff.py`, as seguintes coleções fixam o conjunto exato de chaves do retorno:

- `V3_VERDICT_FIELDS`: **12 campos**, exigindo seis indicadores locais estritamente verdadeiros e cinco indicadores de isolamento externo/publicação estritamente falsos, além do status esperado.
- `RECEIPT_VERDICT_FIELDS`: **11 campos**, incluindo a presença de `report_sha256` com 64 dígitos hexadecimais minúsculos. Mantém as checagens de recibo pinado, classificação **não atestada**, desafio, fonte em montagem readonly, número de fontes e sinalizadores externos falsos.
- `GIT_VERDICT_FIELDS`: **6 campos**, mantendo commit completo, quantidade de entradas, árvore limpa e indicadores de autenticidade/autorização falsos.

Cada retorno precisa ter tipo `dict` exato e **nenhum campo novo ou faltante**, sem fallback para valores ausentes. Um campo inseguro com valor `False` **também é recusado se não estiver no contrato**: mudar o protocolo exige revisão explícita. Os booleanos críticos são comparados por identidade `is True/False` e contagens são inteiros exatos.

Essa proteção **não** torna atômica a observação dos arquivos entre verificadores, nem autentica o responsável pelos registros. O comportamento operacional permanece somente leitura; nenhuma execução de Windows PE, inicialização de VM, escrita ou autorização de release foi adicionada.

## Testes

Quatro métodos em `tests/test_pe_arch_vm_s2_19_reviewer_session_handoff.py` cobrem:

- Formatos exatos das três respostas e a compatibilidade com o cenário real de **três assinaturas Ed25519 descartáveis**, sempre HOLD.
- Saídas V3 alteradas com campo extra, omissão, valor não booleano, alegação de KVM/cgroup verificados ou autorização APK/OTA.
- Recibo alterado com campo extra, SHA de relatório inválido/ausente, suposta atestação do kernel e booleano falsificado.
- Checkout alterado com campo extra, alegações de autoria/VM, booleano falsificado e commit ausente.

Os ensaios não equivalem à revisão real de um host QEMU/libvirt nem à VM Arch nativa. O recibo e Git são simulados em parte da fixture para testar contrato; as assinaturas descartáveis exercitam o caminho criptográfico local.

## Bloqueio externo

A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) continua exigindo custódia de revisor independente, host QEMU/libvirt real, VM Arch nativa, PID real Ghidra com cgroup v2/seccomp/journald, cleanup e cronologia BEFORE → WORK → AFTER. Um conjunto de campos internamente consistente **não substitui** essas provas.

[PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) deve permanecer **Draft/unmerged**. `independent_vm_attestation=false`, `release_authorized=false`. Sem APK/OTA, release, merge ou execução de PE desconhecido.
