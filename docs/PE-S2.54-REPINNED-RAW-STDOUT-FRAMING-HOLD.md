# PE-S2.54 | Recusa de framing re-hasheado nas evidências do host e guest agent (HOLD)

## Desvio entre captura e consumo

A PE-S2.53 endureceu `host._checked_text()` para rejeitar stdout de `virsh` com espaços nas extremidades ou LF extra, antes de produzir registros. Mas os consumidores de registros com SHA-256 externo novo ainda aplicavam apenas parsers de campos:

- S1.71 `_check_snapshot()` aceitava `State: running ` na **última linha física** do `dominfo` de um S1.70 re-hasheado, pois `_validate_dominfo_shape()` permitia espaços finais dentro do valor e a comparação semântica fazia `.strip()`.
- S1.73 `_review_guest()` aceitava ` os.id : arch` na primeira linha de `guestinfo --os` ou `os.machine : x86_64 ` na última, pois `_parse_guest_os()` aceitava espaços nos dois limites.
- Esses registros podiam ter hashes SHA-256 recalculados, e ainda assim seriam rejeitados pelo produtor original S1.70/S1.71. O hash garante identidade de bytes, não que a origem real pudesse gerar esses bytes segundo o contrato.

## Correção

- S1.71 reconstrói exatamente o texto `dominfo` do registro S1.70 e exige que `host._checked_text()` aceite o texto sem normalização, **antes** da análise de rótulos e de qualquer chamada a `virsh`.
- S1.73 reconstrói as linhas do `guestinfo --os`, aplica **o mesmo sanitizador S1.70/S1.71** sem alterar os bytes e só então invoca `guest._parse_guest_os()`.
- Linhas válidas com espaçamento interno em `Label: value` continuam aceitas. `independent_vm_attestation=false` e `release_authorized=false` são invariantes; não há escrita, execução de host, nova chave ou nova assinatura.

## Ajuste da CI após a regressão histórica

Na primeira execução, o job Ubuntu detectou três subcasos reprovados no teste histórico `test_s2_49_repinned_unicode_guestinfo_separator_rejected_offline`. A rejeição Unicode aconteceu corretamente, mas no novo sanitizador S2.54 (antes do parser S2.49), alterando a classe textual da mensagem esperada. O teste passou a exigir a mensagem do gate mais precoce. Não houve relaxamento de validação de dados, autorização ou alteração do código de produção na correção.

## Regressões

Cinco novos testes: dois S1.71 (host re-hasheado malformado e compartilhamento do sanitizador), três S1.73 (re-pinar ambos os hashes após falsificação de `dominfo`, re-pinar guestinfo com espaços no início/fim e confirmar uso do mesmo sanitizador). A suíte existente mantém cenários legítimos de S1.70 e S1.71.

Tudo foi testado com respostas sintéticas e arquivos privados temporários. Nenhuma VM Arch nativa, host QEMU/libvirt independente ou testemunho real foi substituído.

## Segurança

[PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) continua Draft/unmerged e [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) continua OPEN. Nenhuma autorização para merge, execução de PE desconhecido, APK, OTA ou release. Ainda são necessárias provas externas de revisor independente, VM Arch nativa, Ghidra PID, seccomp/cgroup v2, journald, cleanup e sequência BEFORE → WORK → AFTER.
