# PE-S2.27 | Correlacionar a montagem observada com o processo journald (HOLD)

**STATUS:** implementação de observação local; **nenhum revisor independente, host QEMU/libvirt ou guest Arch nativo foi homologado**. PR #47 Draft; sem merge, APK, OTA, lançamento ou análise de PE Windows desconhecido.

## A falha lógica que esta etapa reduz

A PE-S2.26 obtém `mountinfo` de **`/proc/self`**: isso prova apenas o que o observador local enxerga. Em Linux, um serviço pode estar em outro **mount namespace** ou com outra raiz (`chroot`) e, assim, não usar a montagem visível ao observador. Um `tmpfs` de até 32 MiB no observador, portanto, **não basta para relacionar o limite ao processo vivo do journald**.

O novo `tools/pe_journald_same_namespace.py` lê, **somente após `--inspect-live-journald-mount`**, o PID atual do `systemd-journald` confirmado via verificações S2.09.1 (serviço + cgroup), a identidade inicial desse processo, as identidades da montagem e da raiz vistas por ambos, os `mountinfo` do observador e do `/proc/PID`, além da capacidade da montagem da PE-S2.26. Revalida PID, início do processo, mount namespace, raiz, registro de montagem e capacidade depois da leitura. **Qualquer divergência resulta em REJECTED**, nunca em aprovação externa.

A leitura é conservadora e só aceita o caso em que o processo e observador compartilham a mesma identidade de mount namespace, mesma raiz de filesystem, a mesma montagem dedicada `tmpfs` em `/run/log/journal`, e um limite total de no máximo **32 MiB**. A ferramenta não muda configuração, não executa `mount`, não reinicia o daemon, não lê o conteúdo de logs, não escreve recibos, não usa root e não inicializa Ghidra.

## Uso no guest descartável, com revisor humano

O revisor independente estabelece antes sua custódia real do host e da VM, commit SHA, domínio/UUID, challenge/nonce e acompanha a coleta **na mesma sessão** descrita em [PE-S2.24](PE-S2.24-EXTERNAL-REVIEWER-EXECUTION-HANDOFF-HOLD.md). Dentro do guest Arch, como usuário **não-root**, a partir do checkout já verificado:

```bash
# Nenhuma leitura de processo ou kernel
python3 -B tools/pe_journald_same_namespace.py

# Observar explicitamente o journald ativo e seu namespace de montagem
python3 -B tools/pe_journald_same_namespace.py --inspect-live-journald-mount
```

| Situação | Status | Exit |
| --- | --- | --- |
| Sem opt-in | `PE_S2_27_JOURNALD_PROCESS_MOUNT_VIEW_NOT_STARTED` | 0 |
| Identidade de montagem correlacionada **localmente** | `LOCAL_PE_S2_27_JOURNALD_SAME_MOUNT_VIEW_HOLD` | 2 |
| Identidade, limite ou leitura não demonstrada | `REJECTED_PE_S2_27_JOURNALD_EFFECTIVE_MOUNT_NOT_PROVEN` | 2 |

**Não usar somente o exit code**: observação e recusa têm ambos código 2.

## Reforço PE-S2.28: leitura delimitada de `/proc/PID/cgroup`

O observador S2.09.1, utilizado por esta etapa, deixou de usar `Path.read_bytes()` (que pode carregar um arquivo inteiro antes de checar tamanho) e passou a abrir `/proc/<PID>/cgroup` com `O_RDONLY|O_CLOEXEC|O_NOFOLLOW`, ler **no máximo 8193 bytes**, repetindo leituras curtas até EOF dentro desse teto, e rejeitar conteúdo vazio, NUL, maior que 8192 bytes, symlink final, PID inválido e registros que não coincidam exatamente com o cgroup unificado esperado. A leitura até EOF evita que um prefixo aparentemente correto esconda entradas adicionais contraditórias. O descritor é fechado inclusive quando a leitura falha.

`tests/test_pe_journald_runtime.py` acrescenta verificações negativas de symlink, arquivo superdimensionado, byte NUL, PID incorreto e limite da chamada `os.read`. A implementação não eleva privilégios, não executa serviços nem amplia o escopo de coleta. Permissões insuficientes ou dados inconsistentes continuam sendo **recusa**, sem interpretação como homologação externa.

## Reforço PE-S2.29: evitar prefixos incompletos de mountinfo

A observação tanto do `/proc/self/mountinfo` quanto de `/proc/<PID>/mountinfo` agora usa a mesma leitura **delimitada a 1 MiB**, seguindo leituras curtas até EOF. Isso reduz o risco de aceitar um prefixo aparentemente válido enquanto outra linha posterior descreve montagem aninhada, sobreposta ou divergente. A API não acompanha symlinks finais, recusa conteúdo binário/superdimensionado e fecha os descritores. Os testes sintéticos exercitam essas condições sem executar journald ou qualquer PE. **Uma visão local completa ainda não é atestação independente**.

## Reforço PE-S2.30: saída do systemctl delimitada durante a coleta

A S2.09.1 consulta o daemon por meio de `/usr/bin/systemctl --system show`. Antes, `subprocess.run(..., stdout=PIPE, stderr=PIPE)` acumulava a resposta inteira em memória e só então verificava o tamanho. O componente `tools/pe_journald_runtime.py` agora utiliza `subprocess.Popen` com leitura assíncrona dos dois canais por `selectors`, impondo **8 KiB para stdout e 4 KiB para stderr durante a própria leitura**, além do prazo total de **8 segundos**. Se algum canal exceder o teto, o processo não terminar dentro do prazo ou a consulta for incompatível, o observador recusa; o processo filho é encerrado sem conceder permissões extras. Os campos esperados do `systemctl` continuam verificados exatamente como antes.

Os testes usam produtores **sintéticos em Python**, sem executar PE, e simulam saída excessiva em ambos os canais, prazo expirado, códigos de retorno inválidos e resposta normal limitada. Isso protege apenas a memória do processo observador; não comprova política efetiva do journald, procedência do guest ou atestação de VM independente. A PR #47 e a Issue #48 permanecem HOLD.

## Limites do resultado

Mesmo que a observação local consiga correlacionar mount namespace, raiz e capacidade do filesystem, **ela não prova** que o journald gravou de fato em `/run/log/journal`, que carregou a política declarada, que não encaminhou logs por outro destino, ou que o host/kernel são confiáveis. Um host desonesto pode falsificar suas próprias observações. Permanecem explicitamente falsos todos os campos de atestação independente e autorização de release.

O revisor deve correlacionar **fora da conta do operador** as evidências das PE-S2.09, S2.09.1, S2.26 e S2.27, o destino efetivo dos arquivos, e a cronologia antes/durante/depois do Ghidra **apenas com PE sintético como dado**, sem executar Windows PE. Cotas de /work, cgroup v2+seccomp e descendentes são lacunas separadas. As sete linhas da PE-S2.23 seguem com `PENDING_INDEPENDENT_REVIEWER_EVIDENCE` até testemunho real; nenhum diagnóstico local altera esses campos.

## CI e evidência

`tests/test_pe_journald_same_namespace.py` executa casos sintéticos positivos e negativos para troca do mount namespace, raiz, PID reutilizado, service PID diferente, montagem substituída, capacidade alterada, modo padrão sem leitura, rejeição root e preservação de HOLD. A CI Ubuntu e Arch **userspace em contêiner** não é execução de um host real por revisor independente.

**Próxima dependência externa:** [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48). Não há justificativa para merge, APK, OTA ou release a partir desta etapa.
