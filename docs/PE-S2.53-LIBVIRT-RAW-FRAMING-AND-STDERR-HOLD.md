# PE-S2.53 | Preservação do framing stdout e rejeição de stderr em virsh (HOLD)

## Lacuna identificada

O produtor S1.70 e o capturador do guest agent S1.71 chamavam `host._checked_text`, que usava `str.strip()`. Isso **apagava silenciosamente** quebras de linha LF extras e espaços no início/fim do stdout de `virsh`, fazendo um resultado bruto não canônico parecer uma evidência normal. Os dois comandos também verificavam `stderr.strip()`, interpretando stderr contendo só LF, espaços ou TAB como se estivesse completamente vazio.

Exemplo: `b"running\\n\\n"` tornava-se `"running"`, aceito como estado canônico; uma linha em branco extra poderia desaparecer antes do validador. Isso pode esconder respostas de comando com formatação surpreendente. Ainda não autentica a origem do host nem demonstra uma exploração real.

## Correção

- `_checked_text` continua verificando limite de 8192 bytes, UTF-8, ausência de NUL e ASCII imprimível/LF (PE-S2.51).
- Agora **remove no máximo um único LF final opcional**, preservando todo o restante. Rejeita linhas vazias, LF duplicado e espaços nas extremidades, em vez de normalizá-los.
- Uma saída válida com `b"running"` ou `b"running\\n"` continua gerando o mesmo registro `"running"`; valores `dominfo` e `guestinfo --os` válidos com um LF final seguem aceitos.
- S1.70 e S1.71 agora exigem `stderr == b""` exatamente após cada comando `virsh`. Até uma advertência só com espaço ou LF impede a captura. Não concede permissões mais amplas, não executa operações mutáveis e não gera prova artificial.

## Testes adversariais

Cinco novos métodos: três em `tests/test_pe_arch_vm_s1_70_readonly_libvirt_host_capture.py` e dois em `tests/test_pe_arch_vm_s1_71_guestinfo_os_capture.py`. Casos cobrem três comandos de consulta de host, cinco corrupções do stdout, quatro variantes de stderr não vazio, guestinfo malformado, permissão de LF único opcional, e recusa **sem publicar** log privado. Todos os comandos são simulados, sem contato real com QEMU/libvirt.

## Bloqueio permanente até auditoria externa

A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece **Draft/unmerged**. A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) permanece **OPEN**. CI e testes com `virsh` simulado não estabelecem revisor independente, host QEMU/libvirt legítimo, guest Arch nativo, PID Ghidra, enforcement simultâneo cgroup v2/seccomp, journald, cleanup ou cronologia BEFORE → WORK → AFTER. Sem autorização para analisar Windows PE desconhecido, merge, APK, OTA ou release.
