# PE-S2.60 | Igualdade de confiança do virsh nos coletores de telemetria do host (HOLD)

## Divergência de execução identificada

PE-S2.55 e PE-S2.56 passaram a exigir `host._trusted_virsh_executable()`, que confere o caminho literal `/usr/bin/virsh` ou `/bin/virsh`, propriedade root, permissões seguras e ausência de symlinks/ancestrais inseguros. Porém, duas rotas posteriores de coleta real ainda usavam apenas `shutil.which("virsh", path="/usr/bin:/bin")` e uma condição de caminho absoluto:

- S2.15 `capture_host_domstats()` para o sidecar de estatísticas do domínio;
- S2.17 `_live_sample()` para as observações BEFORE/AFTER.

Encontrar um caminho absoluto no PATH restrito **não** comprova confiança nos metadados do executável. Essas rotas poderiam consultar um binário que S1.70/S1.71 e o preflight S2.21 rejeitam.

Além disso, `S2.15._read_live()` tolerava `stderr` com apenas espaços/quebras de linha via `.strip()` e herdava o `HOME` do operador na execução do `virsh`, ao contrário da regra recente do S1.70.

## Medidas

- S2.15 e S2.17 agora exigem o **mesmo resolvedor** de `virsh` já utilizado pela captura original e pelo preflight, sem fallback e antes de qualquer consulta real.
- S2.15 rejeita `stderr != b""`, mesmo que contenha apenas espaços, e fixa `HOME=/nonexistent` juntamente com `PATH=/usr/bin:/bin` e `LANG=LC_ALL=C`.
- Os comandos continuam no `qemu:///system`, `--readonly`, sem shell, sem `guest-exec`, sem executar PE, sem criação de novos privilégios.
- Validação de proprietário do binário ainda não é atestado da identidade física/administrativa do host. A checagem por caminho tem uma janela entre verificação e execução que requer revisão externa; não alegamos eliminá-la.

## Testes

Quatro novos testes: (1) S2.15 rejeita caminhos suspeitos/metadados reprovados antes de qualquer chamada, (2) falha com `stderr` contendo apenas whitespace, (3) impede a herança de `HOME`, e (4) S2.17 rejeita o mesmo `virsh` inseguro antes do primeiro sample. Fixtures antigas de S2.15/S2.16/S2.17 simulam apenas os metadados necessários para testar as demais condições, preservando a regra ativa na produção.

## CI de integração com montagem somente-leitura

Na primeira execução de Ubuntu, o laboratório de contrato Arch e todos os quatro workflows auxiliares passaram, mas o script de integração `tests/pe_s2_20_real_mount_joint_review_ci.py` ainda simulava somente o retorno de `shutil.which`, sem simular os metadados exigidos na PE-S2.60. A falha `Trusted system virsh required for readonly domstats` ocorreu na **construção do sidecar sintético**, antes de entrar no revisor real.

O script agora simula **somente** a propriedade/permissões do `virsh` fictício durante a montagem do fixture. O resolvedor de produção continua sendo exercitado, e o componente dentro do Bubblewrap segue executando verificações reais de assinaturas Ed25519, Git, recibos, proteção de leitura dos arquivos e pins externos. Nenhuma simulação foi adicionada a essas verificações finais.

## Limite externo

PR #47 Draft/unmerged; Issue #48 OPEN. Nada aqui atesta host QEMU/libvirt independente, guest Arch nativo, PID Ghidra, seccomp+cgroup v2 simultâneos, quotas journald, cleanup ou cronologia testemunhada BEFORE → WORK → AFTER. Nenhuma liberação de merge, PE Windows desconhecido, APK, OTA ou release é autorizada.
