# PE-S2.09 | Journald declarado e isolamento de armazenamento: HOLD

**Estado:** política local preparada para teste. **Não existe homologação independente em VM Arch real.** PR #47 permanece Draft, sem merge, APK, OTA ou análise de binário Windows desconhecido.

## Alteração de código

`tools/pe_journald_policy.py` lê, **sem alterar o sistema e sem sudo**, a saída de `/usr/bin/systemd-analyze cat-config --tldr systemd/journald.conf`. Exige exatamente uma política declarada suficientemente conservadora para a VM de laboratório: `Storage=volatile`, `RuntimeMaxUse` entre 8 e 32 MiB, `RuntimeMaxFileSize` até 8 MiB, `RuntimeKeepFree` de pelo menos 32 MiB, `RateLimitIntervalSec` de 1 a 60 segundos e `RateLimitBurst` de 1 a 1000. Rejeita encaminhamento via `ForwardToSyslog`, `ForwardToKMsg`, `ForwardToConsole` ou `ForwardToWall`. Exige valores explícitos, sem aceitar defaults desconhecidos.

A aceitação nativa S1.5 e o launcher de revisor S1.66 exigem essa checagem **antes do primeiro escopo systemd** e recusam ausência de configuração. Os testes no Ubuntu e no contêiner Arch são contratos simulados, não execução de journald ou kernel Arch independentes.

**Crucial:** `RuntimeMaxUse` e `RuntimeMaxFileSize` são políticas de uso/retenção do journald e **não** equivalem a `tmpfs size=`, `RLIMIT_FSIZE` ou cota compulsória do kernel. A saída de `systemd-analyze` é a configuração mesclada encontrada no disco, **não** prova que o daemon ativo a carregou, nem que toda gravação externa por serviços de log esteja limitada. A marcação retornada é `LOCAL_JOURNALD_DECLARED_POLICY_ONLY`, com `journal_kernel_quota_verified=false`, `journal_daemon_effective_runtime_verified=false` e `release_authorized=false`.

## Preparação para revisão independente

Apenas na **VM Arch descartável e administrada pelo revisor**, não no computador pessoal, o administrador da VM pode preparar uma configuração de journal adequada, reiniciar a VM e guardar snapshots. O software deste repositório não cria nem modifica essa configuração. Para revisão externa, guardar fora da VM e relacionar ao SHA Git e challenge previamente escolhidos:

1. `systemd-analyze cat-config --tldr systemd/journald.conf`, `systemctl is-active systemd-journald.service` e `journalctl --disk-usage` antes e depois dos testes. Separar observação do daemon de políticas de retenção.
2. `findmnt -T /run/log/journal` e `findmnt -T /caminho/do/tmpfs-do-revisor`, além de `/proc/self/mountinfo` com dados necessários saneados. Exigir que o `/work` use seu próprio `tmpfs` privado de 64 a 512 MiB, com `size=`, conforme S2.08.
3. Em outra máquina, validar SHA Git, integridade do Ghidra, cotas do cgroup v2, filtros seccomp efetivos e encerramento de processos descendentes. O revisor deve testemunhar o comportamento do journal e da montagem durante uma análise **apenas de PE sintético como dados**, com limites físicos de VM pré-configurados.
4. Para prova de limite rígido do `/work`, realizar ensaio controlado de `ENOSPC` exclusivamente sobre o `tmpfs` descartável, verificando que gravações fora da montagem são recusadas. Não usar o disco real do host, não encher `/`, e não deixar o journal do host sem espaço.

### PE-S2.09.1 | Verificação local da instância ativa

Novo `tools/pe_journald_runtime.py` consulta exclusivamente `systemctl --system show systemd-journald.service` (estado loaded/active/running, PID e cgroup) e compara a associação efetiva de `/proc/<PID>/cgroup` no kernel cgroup v2. Refaz a leitura e recusa alterações de PID/estado durante a observação. Não executa restart, vacuum, kill nem coleta conteúdo de logs. As entradas nativas e o launcher de revisor recusam a operação ANTES do primeiro escopo caso a instância ativa não seja observada. Testes no CI são mockados.

O resultado `LOCAL_JOURNALD_SERVICE_CGROUP_OBSERVED_ONLY` afirma SOMENTE que o processo ativo local corresponde ao serviço/cgroup no instante das leituras. Ele marca `effective_journald_configuration_verified=false`, `journal_storage_kernel_quota_verified=false`, `independent_vm_attested=false` e `release_authorized=false`. O revisor independente ainda deve acompanhar espaço/uso real, montagem de armazenamento, comportamento sob carga, e condição final da VM Arch.

**Pendências reais:** configuração carregada pelo daemon, consumo efetivo do journal, retenção e possível crescimento transitório, soma de outros destinos graváveis, prova de `ENOSPC` do `/work` na VM, resistência a remount privilegiado e evidência independente de hipervisor/kernel/cgroups/seccomp. Mesmo que o teste de configuração passe, **não liberar produção**.
