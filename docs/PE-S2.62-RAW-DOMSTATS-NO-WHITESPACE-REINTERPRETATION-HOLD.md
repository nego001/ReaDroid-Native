# PE-S2.62 | Sem normalização de campos brutos do virsh no runtime (HOLD)

## Divergências corrigidas

Mesmo após a PE-S2.61 exigir LF literal e UTC canônico, a rotina `S2.15._stats()` ainda utilizava `line.strip()` para as linhas brutas do comando `virsh domstats --raw --state --cpu-total`. Isso ocultava indentação duplicada e espaços finais, permitindo que um sidecar ou um JSON de fase S2.17 adulterado e re-hashado fosse interpretado com os mesmos valores que a saída `" key=value"` usada pela captura real. Esse permissivismo não é necessário para a saída C-locale esperada.

O segundo desvio estava em `S2.17._live_sample()`, que tratava `RUNNING` ou `Running` como equivalentes a `running` usando `casefold()`, enquanto S1.70/S2.15 utilizam igualdade literal do estado devolvido pelo `virsh` no locale fixado.

## Endurecimento aplicado

- O parser de domstats exige exatamente **um espaço inicial** em cada campo `key=value`, sem espaços adicionais ao começo ou fim da linha e sem espaços internos no campo ou valor.
- A rotina deixa de chamar `strip()` antes de interpretar campos. `_stats()` continua rejeitando caracteres de controle, duplicatas, valores não numéricos, domínio divergente e contadores inválidos.
- A captura de duas fases agora exige os dois estados `running` em minúsculas, exatamente, e UUID estável antes/depois. Não confundir o padrão de saída do virsh com atestado real do host.
- Permanecem pinagem SHA256, limites de subprocesso, URI readonly, formato UTC, controle de arquivos privados, assinatura V1/V2/V3 e resultado exclusivamente HOLD.

## Regressões

Quatro novos métodos:
- Seis variantes de formatação ambígua em `_stats()` são recusadas, com fixture canônica positiva;
- Três alterações do sidecar S2.15, com SHA256 recalculado, são recusadas na leitura offline;
- Três alterações no `domstats_raw` do JSON S2.17, com JSON canônico e SHA recalculados, são recusadas;
- Estados alterados para `RUNNING`, `Running` ou com espaços em BEFORE e AFTER não geram arquivos de evidência.

## HOLD independente

Esta etapa altera somente interpretação de texto e estados de coleta; não demonstra a independência do revisor, a identidade do host QEMU/libvirt, a origem de um guest Arch nativo, seccomp+cgroup v2 num PID Ghidra real, journal quotas, cleanup ou cronologia BEFORE → WORK → AFTER. PR #47 permanece Draft/unmerged; Issue #48 OPEN. Nenhum Windows PE desconhecido, merge, APK, OTA ou release autorizado.
