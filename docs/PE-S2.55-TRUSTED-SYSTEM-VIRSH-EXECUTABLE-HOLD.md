# PE-S2.55 | Exigência de binário `virsh` confiável também na captura (HOLD)

## Falha de fronteira

O preflight S2.21 já exige binários do sistema com propriedade root, permissões não graváveis por grupo/outros e caminho de diretórios sem symlinks. Porém, os produtores de registros S1.70 e S1.71 apenas consultavam `shutil.which("virsh", path="/usr/bin:/bin")`. Encontrar o arquivo num diretório de sistema não equivale a verificar seus metadados. Um binário trocado, permissões relaxadas ou link malicioso poderia passar pelo lookup simples sem repetir os controles usados no preflight.

A análise não alega comprometimento real do host. É correção preventiva de divergência entre o preflight e o ponto de execução.

## Medida de segurança

- `host._trusted_virsh_executable()` consulta apenas `/usr/bin:/bin`, admite somente o caminho canônico exato `/usr/bin/virsh` ou `/bin/virsh` e exige a política reutilizada `pe_resource_limits._trusted_discovered_systemd_binary()`: arquivo executável regular root-owned, sem gravação para grupo/outros, ancestrais root-owned, não graváveis e não-symlinked.
- S1.70 revalida o executável **imediatamente antes** das consultas read-only; S1.71 compartilha a mesma função e falha antes de consultar o guest agent. Não faz fallback para diretório de usuário nem invoca shell.
- O ambiente dos subprocessos read-only mantém `LANG=LC_ALL=C`, `PATH=/usr/bin:/bin` e agora fixa `HOME=/nonexistent`, evitando consumir configuração libvirt específica do usuário apenas por herdar `HOME`.
- Dependências de autenticação que exijam configuração específica do `HOME` devem falhar fechado; não elevar privilégios, mudar URI `qemu:///system` ou relaxar a política sem revisão.
- Esses metadados do binário são **pré-condições locais**. Não provam controle independente da máquina, origem do hipervisor nem uma VM Arch autêntica. Uma substituição por root ou mudança entre a verificação e a execução requer auditoria externa.

## Correção de regressões na CI

A primeira execução encontrou um teste de CLI S1.70 que ainda simulava somente o caminho do `virsh`, sem simular o novo verificador de propriedade root e permissões. O simulador foi atualizado. O mesmo ajuste preventivo foi aplicado ao teste de CLI S1.71. Essa correção modifica **apenas os mocks dos testes**: não diminui os critérios de confiança da captura real.

## Testes

Quatro métodos novos cobrem caminhos forjados, o caminho canônico com metadados reprovados, recusa antes de quaisquer consultas S1.70/S1.71 e isolamento de `HOME` para host e guestinfo, preservando os cinco comandos de leitura quando o binário é confiável por contrato. Os testes usam simuladores e não ligam uma VM.

## Ajuste da suíte com subprocessos reais (S1.72)

A segunda execução de CI detectou cinco erros na suíte S1.72: o teste legítimo usa um script `virsh` temporário, pertencente ao usuário, para simular uma resposta e comprovar o comportamento de `subprocess` real. O novo resolvedor corretamente recusou executar esse script fora do diretório de sistema confiável.

A suíte S1.72 passa a **simular apenas a decisão do resolvedor `_trusted_virsh_executable`** para os testes com o stub. Todos os subprocessos com pipes, limites, códigos de saída e gravação dos recibos continuam reais. Um novo teste separado, sem esse mock, confirma que o script temporário é recusado antes de lançar qualquer processo. A política de produção não foi relaxada.

## HOLD

A PR #47 permanece Draft/unmerged e a Issue #48 OPEN. Sem prova externa de host QEMU/libvirt sob revisor independente, VM Arch nativa, Ghidra PID sob cgroup v2 e seccomp, journald, limpeza e cronologia BEFORE → WORK → AFTER, nenhuma análise de Windows PE desconhecido, merge, APK, OTA ou release é autorizada.
