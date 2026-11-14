# PE-S2.51 | `dominfo` do host: registros somente ASCII imprimível e LF (HOLD)

## Lacuna

A política PE-S2.47 restringiu rótulos do `virsh dominfo` a ASCII, mas deixou caracteres Unicode nos **valores** das linhas. O S1.70 podia receber `Id: 5\u2028shadow` (separador U+2028), U+0085, U+2029, U+200B (zero-width), U+202E (controle bidi) ou NBSP, publicando a saída sem alteração porque apenas bytes de controle ASCII e DEL eram proibidos. Essa entrada pode aparentar linhas extras ou ocultar texto numa revisão visual, apesar de não existir uma quebra de linha LF no log.

O S1.71, o S1.73 e o S2.21 já chamam a validação S1.70 ao revisar a mesma saída. A lacuna existia na função **compartilhada**, portanto hashes SHA-256 corretos não eram suficientes para detectá-la.

## Mudanças

- `tools/pe_arch_vm_s1_70_readonly_libvirt_host_capture.py`: `_checked_text` aceita somente ASCII imprimível (`U+0020..U+007E`) e LF antes de `.strip()`. Isso evita normalização silenciosa de Unicode escondido na saída `virsh`.
- `_validate_dominfo_shape` exige apenas ASCII imprimível em cada linha depois da divisão por LF; rótulos únicos e estrutura `Label: value` continuam obrigatórios.
- S1.71 e S1.73 recusam o registro S1.70 re-hasheado por usar esse mesmo validador. O preflight S2.21 também falha fechado antes de declarar `CANDIDATE`.
- Saída legítima de `virsh` sob `LC_ALL=C` com `Id`, `Name`, `UUID`, `State`, `CPU(s)` e `OS Type` em ASCII segue válida. Se futuramente um host confiável exigir conteúdo não ASCII, é necessária revisão explícita do contrato; não permitir aceitação silenciosa de separadores Unicode ou controles visuais.

## Regressões

São seis métodos novos: três em `tests/test_pe_arch_vm_s1_70_readonly_libvirt_host_capture.py`, um na S1.71, um no revisor S1.73 e um no preflight S2.21. Testam captura bloqueada sem arquivo, hashes reconstruídos de **ambos** os registros no S1.73, bloqueio antes de `guestinfo`, preflight sem falso candidato e compatibilidade positiva em ASCII.

Todos usam `virsh` simulado e arquivos descartáveis. Nenhum host independente foi consultado e não existe prova da VM Arch nativa.

## Segurança e status

[Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) **OPEN / EXTERNAL HOLD**. A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece **Draft/unmerged**. Revisor independente, host QEMU/libvirt e guest Arch nativo, cgroup/seccomp e journald efetivos, limpeza e BEFORE → WORK → AFTER ainda precisam de testemunho externo. Nenhum APK, OTA, merge, release ou execução de Windows PE desconhecido é autorizado.
