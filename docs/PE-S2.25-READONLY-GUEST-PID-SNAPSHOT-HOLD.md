# PE-S2.25 | Observação do PID/cgroup v2/seccomp durante Ghidra (HOLD)

**STATUS:** ferramenta local preparada, sem homologação nativa Arch independente. PR #47 continua Draft, sem merge/APK/OTA/release. Não executar Windows PE desconhecido. Nunca rodar como root ou desligar proteções para passar no teste.

## Por que este teste existe

A lacuna 4 da S2.23 exige que um revisor **independente** testemunhe que, **durante a mesma execução sintética do Ghidra**, o **mesmo PID** usa filtro seccomp (modo 2) e pertence a um escopo cgroup v2 com quotas de memória, tarefas e CPU efetivas. O relatório do analisador não prova isso sozinho.

O novo `tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py` **não executa Ghidra**, não cria um processo, não lê arquivos pessoais, não escreve evidências, não usa libvirt, não coleta credenciais e não afirma que o processo observado seja de fato Ghidra. Ele lê somente campos delimitados de `/proc/<PID>/{stat,status,cgroup}` e `/sys/fs/cgroup/<cgroup>/{memory.max,pids.max,cpu.max}`. Antes e depois das quotas, relê início do processo, UID, seccomp e cgroup para recusar mudanças observáveis e PID reutilizado. Exige `Seccomp: 2`, pelo menos um filtro, UID efetivo do observador, escopo exato `negresco-pe-<24 hex>.scope`, `memory.max <= 4GiB`, `pids.max <= 128` e `CPUQuota <= 200%`. Limites relaxados ou `max` são recusados.

## Execução prática para um revisor com acesso à VM descartável

1. O revisor controla **fora do guest** o host QEMU/libvirt, o desafio, domínio/UUID e a ordem de capturas BEFORE → WORK → AFTER. Se não puder testemunhar o host/guest, parar e manter HOLD.
2. Em sessão do **guest Arch real não-root**, após validar checkout e Ghidra 12.2 oficial, iniciar a análise do PE **sintético como dado** pelo protocolo [S1](PE-S1-NATIVE-ARCH-INDEPENDENT-REVIEW.md). Um segundo terminal do **mesmo usuário** deve observar o PID JVM real enquanto ainda está executando e seu escopo systemd transiente. O revisor deve confrontar a identidade do PID/escopo com a execução Ghidra, em vez de escolher qualquer processo Java com filtros.
3. Primeiro verificar o plano sem acessar arquivos do kernel:

```bash
python3 -B tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py \
  --pid "$GHIDRA_JAVA_PID" \
  --expected-scope "$GHIDRA_SYSTEMD_SCOPE"
```

4. Durante o processo em execução, optar explicitamente pela leitura local:

```bash
python3 -B tools/pe_arch_vm_s2_25_pid_kernel_snapshot.py \
  --pid "$GHIDRA_JAVA_PID" \
  --expected-scope "$GHIDRA_SYSTEMD_SCOPE" \
  --snapshot-local-pid
```

`GHIDRA_JAVA_PID` e `GHIDRA_SYSTEMD_SCOPE` são obtidos pelo revisor ao assistir à execução real. **Nunca reutilizar valores ilustrativos nem inferir o PID de registros antigos.** O processo pode terminar antes da leitura, o que exige rejeição, não relaxamento. A saída do script pode ser guardada em pasta privada do revisor *por um procedimento externo*; esta ferramenta em si não cria arquivo algum.

## Contrato dos resultados

| Modo | Status | Código | Significado |
| --- | --- | --- | --- |
| Padrão | `PE_S2_25_LOCAL_PID_SNAPSHOT_NOT_STARTED` | 0 | Nenhuma leitura do kernel executada |
| Opt-in com leitura local consistente | `LOCAL_PE_S2_25_SCOPED_PID_CGROUP_SECCOMP_HOLD` | 2 | Valores locais correlacionados; **não** é atestação externa |
| Opt-in recusado | `REJECTED_PE_S2_25_LOCAL_PID_OR_QUOTA_NOT_PROVEN` | 2 | Não há sequer uma observação local confiável |

**Nunca tratar `exit 2` isoladamente como aprovação**, porque sucesso local e rejeição têm o mesmo código. Somente o revisor externo pode correlacionar essa observação com o host real, um único PID, sessão/nonce e o trabalho sintético, e concluir em parecer humano separado.

A ferramenta não demonstra: independência do revisor, identidade real do Java/Ghidra, autenticidade da VM/kernel contra host adversário, integridade cronológica, journald hard quota ou morte dos descendentes. Permanecem os **sete HOLD** S2.23 mesmo após uma leitura local consistente. Se `Seccomp_filters` ou cgroup v2 não forem legíveis, não fazer fallback silencioso. Não publicar tokens, chaves, dados privados ou logs completos no GitHub.

## Testes e integração

`tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py` simula apenas árvores `/proc` e `/sys/fs/cgroup` com arquivos sintéticos e verifica rejeição de UID errado, seccomp ausente, quotas relaxadas, PID reutilizado, cgroup inconsistente, symlinks e comportamento sem I/O no plano. Os testes rodam no Ubuntu e Arch userspace **em contêiner**, não em VM nativa. O módulo integra o `SOURCE_FILES` usado no pin Git do checkout. O revisor independente ainda precisa executar a prova em uma VM real sob seu controle.

**Próxima dependência:** [issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) e [handoff PE-S2.24](PE-S2.24-EXTERNAL-REVIEWER-EXECUTION-HANDOFF-HOLD.md). Nenhum arquivo JSON auto-relatado, incluindo este diagnóstico, deve virar `independent_vm_attestation=true` ou `release_authorized=true`.
