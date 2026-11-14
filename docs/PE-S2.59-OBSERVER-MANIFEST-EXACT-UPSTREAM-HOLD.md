# PE-S2.59 | Manifesto do observador exige contratos completos S1.73 e S2.13 (HOLD)

## Lacuna de segurança

O preparador S1.65 verificava apenas cinco atributos do resultado de revisão S1.73 e três atributos do resultado S2.13. Em uma mudança futura de API, um verificador poderia acrescentar `independent_host_control_verified=true`, `kernel_or_hypervisor_authenticated=true`, `unknown_windows_pe_execution_authorized=true` ou mesmo omitir um campo de validação, e o preparador continuaria publicando um manifesto como se o conjunto completo fosse estritamente consistente.

O SHA-256 de entrada e a assinatura posterior não representam um contrato de significados entre componentes. Esta etapa fecha essa passagem **antes da publicação**.

## Alterações

- S1.65 introduz `S1_73_RESULT_FIELDS` e `S2_13_RESULT_FIELDS`, conjuntos explícitos dos nomes retornados pelos dois revisores. Qualquer campo extra ou ausente aborta a preparação.
- Exige todos os indicadores de correlação em `True` literal, todos os indicadores de autenticação independente e liberação em `False` literal, exatamente dois registros por gate, `guest_os_id_self_reported=arch`, formato de versão de kernel admitido pelo parser, e lista completa de registros ainda não verificados.
- O estado só pode ser `HOLD_PE_S1_73_TWO_PINNED_HOST_RECORDS_NOT_VM_ATTESTED` no S1.73 e `LOCAL_S2_13_TWO_TEXT_RECORDS_STRUCTURALLY_CORRELATED_HOLD` no S2.13.
- Não muda a gramática dos quatro arquivos originais, não reescreve evidências, não executa nada no host e não autoriza liberação.

## Testes

Três novos métodos com fixtures sintéticas, mas revisores originais executados: (1) dez mutações do resultado S1.73, incluindo flags falsos, campos extra/ausente, texto em vez de booleano, falta de correlação e supressão da lista de pendências; (2) oito mutações do S2.13, incluindo alegação de autenticação independente, retirada de chave e falso vínculo de hash, todas recusadas sem criar manifesto ou assinatura; (3) fluxo positivo que continua apenas preparando manifesto não assinado e com HOLD. Os testes não substituem a homologação externa.

## Exigência externa

PR #47 permanece Draft/unmerged, Issue #48 OPEN. Sem provas humanas e nativas de host QEMU/libvirt independente, VM Arch nativa, PID Ghidra, seccomp e cgroup v2 simultâneos, journald/cleanup e cronologia BEFORE → WORK → AFTER, os processos seguem bloqueados para análise de Windows PE desconhecido, merge, APK, OTA e release.
