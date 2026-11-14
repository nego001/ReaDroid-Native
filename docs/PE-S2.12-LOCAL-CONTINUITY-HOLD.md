# PE-S2.12 | Continuidade local pré/pós-execução, liberação BLOQUEADA

**Estado:** implementação testável em CI. **Não** existe evidência nova de uma VM Arch independente, controle independente de hipervisor ou aprovação de release.

## O problema concreto

A aceitação nativa já recusava tmpfs ruim, journald mal configurado e `ENOSPC` ausente **antes** de executar o primeiro escopo. Faltava amarrar as mesmas observações locais **depois** do trabalho sintético, para não aceitar um `/work` substituído, `journald` reiniciado ou política alterada durante a execução. Essa continuidade é indispensável, porém não equivale à attestation do host.

## Verificação implementada

`tools/pe_arch_vm_s2_12_session_continuity.py` verifica duas vezes a montagem privada dedicada via `require_bounded_work_mount()`, lê política declarada via `systemd-analyze cat-config`, observa `systemd-journald.service` via `systemctl` + `/proc/<pid>/cgroup`, e exige diretório 0700 não-symlink com mesmo `st_dev`/`st_ino` e capacidade de `statvfs`. Registra um snapshot **somente em memória**, com `independent_vm_attested=false` e `release_authorized=false`. Na aceitação, captura imediatamente antes do primeiro `systemd-run` e refaz tudo depois do Ghidra/seccomp e do encerramento dos escopos. Se qualquer valor pinado mudou, **nega a aceitação antes de publicar recibo**. Não escreve arquivos de política e não reinicia serviços.

A suíte `tests/test_pe_arch_vm_s2_12_session_continuity.py` simula alterações de PID do journal, política, capacidade, inode, dados forjados e falha de leitura; sem montar volume no host. O ensaio Ubuntu Bubblewrap real da PE-S2.11 continua como prova de `ENOSPC` **somente no runner Ubuntu**. O snapshot S2.12 não é anexado ao recibo v2 para evitar alterar inadvertidamente o contrato assinado/validado; é apenas uma barreira local anterior à aceitação.

## Ainda obrigatório

Revisor independente deve correlacionar SHA de commit e desafio escolhidos fora do guest, domínio/UUID do hypervisor, evidência bruta de inicialização e fim da sessão, cgroups, seccomp, filhos encerrados, journald e volume de trabalho. Confirmar em máquina Arch virtual dedicada, com provas separadamente autenticadas; `systemd-analyze` lê política declarada, **não** demonstra que o daemon carregou essas opções, nem que journal é rigidamente quota-limitado no kernel. Sem isso **PR Draft**, sem merge, sem APK/OTA e sem executar PE Windows desconhecido.
