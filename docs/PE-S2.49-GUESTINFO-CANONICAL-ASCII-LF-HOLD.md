# PE-S2.49 | Delimitadores canônicos no guestinfo --os (HOLD)

## Problema de interpretação

O parser S1.71 de `guestinfo --os` usava `str.splitlines()`. Python trata NEL (U+0085), U+2028 e U+2029 como separadores de linhas, enquanto os arquivos de evidência assinados e o leitor offline S1.73 são separados apenas por byte LF (`\\n`). Era possível formar campos `os.id` e `os.name` que o parser interpretava como linhas separadas, mas que pertenciam à mesma linha física do registro S1.71. Espaço Unicode não quebrável podia ser aceito por `\\s*` apesar de não ser uma representação ASCII canônica.

Essa inconsistência de framing é local. Não foi observada exploração de uma VM/host real.

## Correção

- `tools/pe_arch_vm_s1_71_guestinfo_os_capture.py` rejeita tipos que não sejam string exata, entradas vazias, mais de 8192 caracteres ASCII, controles não LF e caracteres Unicode fora de ASCII imprimível.
- Exige que as linhas sejam delimitadas somente por LF; aceita um único LF final para entradas diretas do parser, mas não aceita linhas internas vazias ou finais duplicados.
- Mantém validação de campos `os.*` únicos e do triplo `os.id=arch`, `os.kernel-release`, `os.machine`. Não reescreve silenciosamente o texto coletado nem modifica o protocolo V1/V2/V3.
- A verificação offline S1.73 continua consumindo esse mesmo parser e rejeita os bytes de controle invisíveis, mesmo quando a observação do guest foi recalculada e pinada com SHA-256 correto.

## Regressões

Três métodos novos exercitam a recusa de NEL, U+2028, U+2029, NBSP, tipos inválidos, separadores CR/TAB, linha vazia e tamanho excedido; o formato `guestinfo` sintético válido continua aceito. Um teste adicional da revisão S1.73 substitui LF por três separadores Unicode e recalcula o pin externo da segunda observação; a revisão precisa rejeitar sem consultar libvirt.

Testes usam saída `virsh` simulada, arquivos temporários e hash local. Nenhum host QEMU/libvirt independente, kernel Arch nativo ou sessão Ghidra real é comprovado aqui.

## Bloqueios

A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) continua **Draft**. A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) continua **OPEN** exigindo revisor independente, host QEMU/libvirt real, VM Arch nativa, identidade de PID/Ghidra, cotas cgroup v2 e seccomp simultâneos, journald, limpeza e cronologia BEFORE → WORK → AFTER.

Sem autorização para merge, análise de PE desconhecido, APK, OTA ou release. `independent_vm_attestation=false`; `release_authorized=false`.
