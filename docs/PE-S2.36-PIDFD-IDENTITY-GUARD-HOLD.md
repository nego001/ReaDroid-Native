# PE-S2.36 | Pin de identidade Linux via pidfd durante snapshot (HOLD)

## Lacuna corrigida

A PE-S2.35 recusa tarefas zumbis/mortas/paradas e a PE-S2.34 observa `/proc/PID/{stat,status,cgroup}` três vezes, com cotas cgroup v2 em duas passagens. Entretanto, **o número de PID pode ser reutilizado** após a saída de um processo, e a granularidade em ticks do campo `starttime` não constitui, isoladamente, prova infalível de identidade. O observador ainda podia depender exclusivamente de amostras numéricas.

## Solução implementada

- Abrir `os.pidfd_open(pid, 0)` **antes de acessar /proc** e manter esse descritor aberto **até o retorno completo** da observação.
- Usar `select.poll()` com leitura **não bloqueante** (timeout zero) no início e no fim da coleta. **Qualquer evento** no pidfd (inclusive `POLLIN` de saída e `POLLHUP` após reap) provoca recusa.
- Encerrar o descritor em `finally`, inclusive quando um arquivo de kernel, cota, seccomp ou UID invalida a observação.
- **Falhar fechado** em sistemas sem `pidfd_open`, com erro de abertura/permissão ou problemas ao consultar `poll`. Não existe fallback silencioso para comparar apenas PID/starttime.
- Preservar a leitura até EOF limitada a 16 KiB por arquivo, diretórios ancorados sem symlinks e a verificação de três passes da identidade e dois das cotas.

O pidfd aponta para o processo já presente no kernel e evita trocar silenciosamente de identidade só porque o identificador numérico foi reutilizado. Esta função **não envia sinais, não executa processos, não cria nem configura sandbox e não espera bloqueada a saída** de nenhum processo.

**Referências:** [Linux pidfd_open(2)](https://man7.org/linux/man-pages/man2/pidfd_open.2.html) e [Python os.pidfd_open](https://docs.python.org/3/library/os.html#os.pidfd_open).

## Regressões

`tests/test_pe_arch_vm_s2_25_pid_kernel_snapshot.py` usa um pipe de teste sem dados para simular um descritor ainda não sinalizado nos cenários com /proc sintético. Novos testes verificam:
- a rejeição de um processo que termina **ao final** da coleta e o fechamento do descritor;
- os eventos de saída `POLLIN`, `POLLHUP`, `POLLERR` e `POLLNVAL`;
- a recusa de sistemas sem `pidfd_open` ou com falha de abertura, antes de ler `/proc`;
- quando disponível na CI, uma leitura real de `pidfd_open(os.getpid())` com `poll(0)` e fechamento correto, sem alterar ou sinalizar a tarefa observada.

## Limitações e bloqueio

O pidfd é **apenas evidência local de identidade e saída** da tarefa durante a curta janela do snapshot. Não prova que o PID é o executável Ghidra autêntico, que a tarefa permaneceu sob seccomp/cgroup durante uma análise inteira, que o Linux observado é um guest Arch nativo, que o host pertence a um revisor independente ou que journald realmente impôs sua política.

[PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) deve permanecer Draft, sem merge. [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) **OPEN**: host QEMU/libvirt real sob custódia de revisor independente, guest Arch nativo, PID real de Ghidra, cotas seccomp/cgroup simultâneas, journald e prova BEFORE→WORK→AFTER ainda faltam.

`independent_vm_attestation=false`; `release_authorized=false`. Sem execução de PE desconhecido, publicação APK/OTA ou release.
