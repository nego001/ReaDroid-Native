# PE-S2.26 | Limite de armazenamento do journald: observação do tmpfs (HOLD)

**ESTADO:** implementado um verificador **local e somente leitura** de capacidade de montagem. **Nenhum host QEMU/libvirt independente nem VM Arch nativa foi executado ou homologado por esta etapa**. PR #47 continua Draft: sem merge, APK, OTA, lançamento ou análise de PE Windows desconhecido.

## Problema de segurança

A PE-S2.09 lê a política declarada de `Storage=volatile`, `RuntimeMaxUse`, tamanho de arquivo, taxas e encaminhamentos; a PE-S2.09.1 observa o processo `systemd-journald` e seu cgroup. Ambas deixam explícito que **a configuração não comprova um teto rígido de armazenamento imposto pelo kernel**.

O novo módulo `tools/pe_journald_mount_capacity.py` exige, para uma observação local favorável, **uma montagem tmpfs dedicada exatamente em `/run/log/journal`**, separada de `/run`, com capacidade total de filesystem de **no máximo 32 MiB**, medida por `statvfs`. Isso é um teto de espaço *daquele filesystem*, não uma prova de quota individual do serviço, nem prova de que o daemon realmente o está utilizando.

**Não tente modificar o notebook pessoal, o host ou uma VM produtiva para atingir esses valores.** Se a VM descartável do revisor não tiver a montagem própria, a verificação deve recusar e a condição permanece HOLD. Criar/montar o tmpfs, quando apropriado, é decisão e preparação separada do administrador/revisor independente, nunca trabalho deste programa.

## O que a ferramenta faz e o que não faz

- Modo padrão: imprime apenas `PLAN`, código 0, **sem I/O de kernel, sem processo filho e sem modificação**.
- Modo explícito: usuário **não root** em Linux lê somente `/proc/self/mountinfo` e metadados de `/run`, `/run/log`, `/run/log/journal`, além de `statvfs` da montagem. Proíbe symlinks e diretórios graváveis por grupo/outros nessa cadeia; exige proprietário root, montagem exatamente no alvo, tipo `tmpfs`, raiz `/`, modo `rw` e **sem montagens filhas**.
- Recusa ausência de montagem, capacidade inexistente/maior que 32 MiB, filesystem overlay/ext4, bind de subárvore, montagem trocada ou mudança de capacidade observável entre duas leituras. Dados de mountinfo têm limites de bytes/linhas e decodificação estrita.
- Não reinicia, edita, consulta ou escreve logs do journald; não ajusta `journald.conf`, `mount`, `systemctl`, kernel, `fstab` ou `sysctl`.
- Mesmo no resultado local favorável, mantém `journald_uses_this_storage_independently_verified=false`, `journald_effective_runtime_policy_verified=false`, `journald_storage_quota_independently_verified=false`, `independent_vm_attestation=false`, `release_authorized=false`.

## Uso somente em VM Arch descartável, controlada pelo revisor

Execute **dentro do guest** no checkout pinado, com usuário normal:

```bash
# Plano: não acessa o kernel
python3 -B tools/pe_journald_mount_capacity.py

# Leitura explícita da montagem corrente, sem alterações
python3 -B tools/pe_journald_mount_capacity.py --inspect-local-journal-mount
```

Resultado e códigos:

| Condição | Status | Exit |
| --- | --- | --- |
| Plano, sem coleta | `PE_S2_26_JOURNAL_MOUNT_CAP_PLAN_NOT_STARTED` | 0 |
| Limite do filesystem observado localmente | `LOCAL_PE_S2_26_DEDICATED_TMPFS_CAP_OBSERVED_HOLD` | 2 |
| Limite não demonstrado ou leitura falhou | `REJECTED_PE_S2_26_JOURNAL_KERNEL_STORAGE_BOUND_NOT_PROVEN` | 2 |

É obrigatório interpretar o campo `status`, **não somente o exit 2**, que é usado tanto para observação quanto recusa.

### Entrega externa necessária

O revisor deve correlacionar **na mesma sessão e fora do controle do operador**:

1. Identidade, controle e procedência reais de host QEMU/libvirt e guest Arch descartável.
2. Política declarada S2.09 (`Storage=volatile`), runtime S2.09.1 e observação S2.26 da montagem de kernel. Confirmar **por evidência original testemunhada** onde o journald de fato gravou, se houve outra via de log/encaminhamento, e se o limite era efetivo enquanto o Ghidra analisou apenas o PE sintético.
3. Estado e capacidade do filesystem antes/durante/depois; quotas de outros filesystems, `/work`, cgroups e limpeza de processos são **exigências separadas**, não supridas pela capacidade do journal.
4. Retenção de observações originais e hashes em custódia externa, sem publicar logs pessoais, chaves privadas ou dados brutos sensíveis.

**Limite conceitual:** `RuntimeMaxUse=32M` é uma política de retenção do daemon; uma montagem `tmpfs` de 32 MiB põe teto no espaço **total desse filesystem**, caso o serviço escreva lá. Um ou outro isoladamente não autentica a execução no kernel Arch, nem comprova retenção do journald, nem garante resistência a um guest malicioso.

## Testes

`tests/test_pe_journald_mount_capacity.py` usa mountinfo e statvfs **sintéticos**, sem montagem real, para testar limites, ausência de montagem, tipo errado, submount, troca de identidade/inode, bytes inválidos, modo PLAN sem I/O, recusa root e proibição de sinais de aprovação. Esses testes rodam na CI Ubuntu e Arch userspace em contêiner. **Nenhuma CI deste projeto demonstra a configuração real de armazenamento em VM Arch nativa independente**.

**Dependência externa:** [issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) e [procedimento PE-S2.24](PE-S2.24-EXTERNAL-REVIEWER-EXECUTION-HANDOFF-HOLD.md). Mesmo com montagem local íntegra, as sete lacunas S2.23 permanecem sem homologação externa.
