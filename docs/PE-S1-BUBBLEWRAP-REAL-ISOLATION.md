# NegrescoDroid | PE-S1: teste de isolamento real Bubblewrap com Ghidra

## Escopo

Este ramo empilha-se sobre a PE-A4.4 (PR #46) para sair dos antigos **testes apenas de construção de argumentos** do Bubblewrap. O novo workflow `pe-ghidra-sandbox-real.yml` executa um probe dentro do namespace e tenta a análise Ghidra Headless **sem a opção que desativa isolamento**, com PE Windows sintético e inofensivo compilado na CI. O executável Windows é analisado como dados, nunca executado.

## Perfil com JDK fixado

`tools/pe_ghidra_sandbox.py` trata duas instalações confiáveis de Java: um `JAVA_HOME` sob `/usr` fica disponível pelo runtime já montado somente leitura; quando Java está instalado fora de `/usr` (por exemplo JDK 25 do GitHub Actions), apenas o diretório apontado por `JAVA_HOME` é montado em `/opt/negresco-jdk` **somente leitura**, sem disponibilizar todo `/opt`, `HOME` ou a árvore do runner. O `PATH` dentro do namespace privilegia `JAVA_HOME/bin`. Instalações ausentes ou sobrepostas ao Ghidra são rejeitadas.

## Provas funcionais incluídas

O arquivo `tests/pe_sandbox_probe.py`, executado **dentro** do exato prefixo Bubblewrap usado para Ghidra, verifica:

- namespace de rede diferente daquele do processo host;
- arquivo-sentinela previamente criado no `$HOME` do runner ausente dentro do namespace;
- ausência de `/etc/passwd` do host e diretório `/home` isolado;
- montagem do runtime `/usr` em modo somente leitura;
- acesso somente ao Ghidra e ao JDK fixados, com `HOME` redirecionado para `/work`;
- capacidade de escrita **apenas no workspace temporário permitido**.

O teste compara o namespace de rede e visibilidade, sem tentar acessar serviços externos. Depois a CI faz uma análise real PE no Ghidra dentro do mesmo perfil padrão e exige metadados, pseudocódigo, string-sentinela e hipótese estática WinAPI. Se Bubblewrap não conseguir estabelecer o namespace, **o teste falha sem desativar AppArmor, mudar sysctl, usar root no analisador ou executar Ghidra sem sandbox**.

## Ambiente e limites

A primeira matriz usa um runner Ubuntu 22.04 efêmero, Bubblewrap do sistema, Ghidra 12.2 oficial com SHA-256 fixado e JDK 25. **Isso não comprova Arch Linux + Hyprland, KDE ou GNOME**, nem representa uma VM. O isolamento de diretórios e rede por namespaces não substitui limites rígidos de recursos, filtros seccomp, auditoria de vazamento de descritores de arquivo, verificação de kernel/LSM ou revisão de vulnerabilidades do Ghidra. Não declarar seguro para executáveis hostis até uma matriz com kernel/distribuição e política de isolamento adequadas.

Ubuntu 24.04 pode impor restrições AppArmor a namespaces de usuários. Um resultado `Operation not permitted` deve ser relatado como ambiente indisponível, **não como aprovação** ou convite para desabilitar a segurança do host.

Os resultados só podem ser chamados de homologados depois que **o probe funcional e o Ghidra real** passarem no mesmo SHA da PR, juntamente com Source checks/OTA/PE. O IObit Uninstaller real segue não analisado; fluxo de selecionar `.exe` na interface ainda não existe. PR em Draft, sem merge em `main` nem APK/OTA publicados.
## PE-S1.1: modo de recursos cgroup v2 (implementado, homologação real pendente)

O executável `tools/pe_auto_ghidra.py` agora aceita `--require-cgroup-limits`.
Esse modo não permite `--allow-unisolated-synthetic-fixture` e envolve o mesmo
comando Bubblewrap em um `systemd-run --user --scope` síncrono, com:

- `MemoryMax=4294967296` (4 GiB de memória no cgroup, incluindo processos filhos);
- `TasksMax=128` (processos **e threads**, não 128 processos garantidos);
- `CPUQuota=200%` (limite agregado equivalente a duas CPUs).

Se `systemd-run` não existir, se cgroup v2 não estiver visível ou se o
gerenciador de usuário não aceitar as propriedades/escopo, o modo estrito recusa
a análise **sem executar Ghidra diretamente**. Não pede `sudo`, não altera
sysctl e não desativa AppArmor. O relatório registra
`resource_scope=systemd_user_cgroup_v2_requested` quando requisitado, e
**não** registra que a aplicação efetiva das quotas foi verificada no host.
O perfil também passou a injetar explicitamente
`GHIDRA_HEADLESS_MAXMEM=2G` dentro do Bubblewrap (`--clearenv` não
preserva variáveis herdadas). Esse limite da JVM **não substitui** MemoryMax.

Exemplo em Arch Linux, sob sessão de usuário normal com systemd user manager:

```sh
python3 tools/pe_auto_ghidra.py /caminho/fixture-sintetica.exe \
  --ghidra-home /caminho/ghidra \
  --output /caminho/relatorio.json \
  --deep-preview --timeout-seconds 420 --require-cgroup-limits
```

Somente usar executável sintético de laboratório nesta etapa. Antes de
analisar software desconhecido, falta verificar **o cgroup real da árvore
Ghidra** (`memory.max`, `pids.max`, `cpu.max`), encerramento de filhos no
timeout, caso de OOM, esgotamento de tarefas, descritores herdados, seccomp,
limites de arquivo e resistência à fuga de sandbox. Bubblewrap + cgroup **não é
equivalente a uma VM**.

### Teste de compatibilidade Arch Linux (escopo limitado)

O novo job `arch-userspace-contract` usa imagem oficial `archlinux:latest`
sobre runner Ubuntu e executa testes de construção de argumentos como usuário
`nobody` (não-root). Ele verifica compatibilidade de runtime/caminhos, não
executa Ghidra real nem comprova os namespaces/cgroups do kernel Arch. Uma
homologação específica exige runner/VM **Arch Linux real, sem privilégios
relaxados**, probe no mesmo perfil, Ghidra real e teste ativo dos limites.
Até essa etapa, manter a PR Draft.

### Verificação antes da execução (PE-S1.1)

O modo estrito agora chama `tools/pe_cgroup_guard.py` **dentro do escopo**
e **antes** do Bubblewrap. O verificador lê a associação do próprio processo
em `/proc/self/cgroup` e os controles de seu escopo em
`/sys/fs/cgroup/.../{memory.max,pids.max,cpu.max}`. Rejeita um escopo
ausente, quotas ilimitadas (`max`), valores superiores à política e
erros de leitura. Só então usa `execvpe` para iniciar o Bubblewrap
com argv original, sem shell nem fallback.

Os testes são com sistema de arquivos cgroup **sintético**, tanto no Ubuntu
quanto no contêiner Arch. O teste de aplicação efetiva no host Arch real
continua pendente. Nenhum desses testes tenta disparar OOM nem saturar
processos no runner compartilhado.

## PE-S1.2 | Ciclo de vida e diagnóstico Arch nativo (sem homologação do host)

O modo estrito agora gera um `negresco-pe-<token>.scope` imprevisível por análise.
Solicita `RuntimeMaxSec=timeout+20s` e `TimeoutStopSec=5s` ao
gerenciador de usuário systemd. Ao encerrar a análise, com sucesso,
falha ou timeout, o executor tenta `systemctl --user stop` **somente**
naquele escopo, em vez de depender exclusivamente do grupo de processos
do lançador. Caso o gerenciador pare de responder, o `RuntimeMaxSec` é
uma proteção independente **quando o próprio systemd segue funcional**;
não existe garantia absoluta de eliminação de processos em um host
comprometido.

Antes de executar o Ghidra, o verificador exige que o processo esteja
no **exato escopo aleatório requisitado**, além de comparar
`memory.max`, `pids.max` e `cpu.max`. Ele escreve uma prova JSON
`cgroup_verification=passed` no stdout do *scope* para diagnósticos
(é suprimida no executor normal, que usa stdout DEVNULL).

### Rodar o probe em um Arch Linux físico/VM instalado

Em uma sessão comum do seu usuário (sem sudo), com systemd como PID 1,
cgroup v2, `systemd-run`, `systemctl` e Python disponíveis:

```sh
python3 tools/pe_arch_cgroup_smoke.py
```

A saída `PASS_NATIVE_ARCH_CGROUP` contém os valores efetivos de
`memory_max`, `pids_max`, `cpu_quota` e `cpu_period`.
`REJECTED_NOT_HOMOLOGATED` é uma recusa segura, não uma instrução
para desativar proteções. O teste recusa root, Ubuntu, contêineres
com marcas usuais e hosts sem systemd como PID 1. **Não analisa
binários Windows** e não muda políticas do host.

O probe **não** comprova que o Ghidra real roda no Arch nem
que todo processo filho morre sob qualquer falha: esses testes ainda
precisam de execução e observação no Arch instalado, inclusive
com janela do gerenciador do usuário e CPU/memória sob pressão
controlada. CI continua usando Ubuntu e userspace Arch sobre Ubuntu.
A PR continua em Draft, sem APK, OTA nem merge.

## PE-S1.3 | Teste nativo de encerramento de descendentes (implementado; execução Arch pendente)

O modo `--require-cgroup-limits` agora solicita explicitamente
`KillMode=control-group` e `SendSIGKILL=yes` no escopo systemd. Isso
pretende atingir todos os processos pertencentes ao cgroup, inclusive
descendentes que criaram sua própria sessão, em vez de depender apenas
de `killpg`. Esses valores são parte do contrato de CI; seu comportamento
real **ainda exige confirmação no host Arch**.

O teste de laboratório `tools/pe_arch_descendant_smoke.py` pode ser
executado no **Arch Linux instalado** como usuário normal:

```sh
python3 tools/pe_arch_cgroup_smoke.py
python3 tools/pe_arch_descendant_smoke.py
```

O segundo teste inicia **somente processos Python controlados**. Um deles
cria uma nova sessão e ignora SIGTERM; ambos permanecem dentro do cgroup
dessa análise. O diagnóstico verifica quotas de memória/processos/CPU,
a identidade do escopo, a vida do descendente, e só aprova se
`systemctl --user stop` eliminar esse descendente. Usa um diretório
temporário privado, protege contra PID reutilizado comparando o tempo de
início do processo e recusa execução fora de host Arch. Em falhas,
tenta limpeza adicional, mas essa limpeza **não conta como aprovação**.
O teste tem teto de duração e nenhum executável Windows é iniciado.

O workflow GitHub Actions testa os casos de aprovação e rejeição por mocks
no Ubuntu e no contêiner Arch, **sem fingir que executou esse teste nativo**.

Seguem pendentes: executar os dois diagnósticos em Arch real ou VM Arch,
repetir o Ghidra real com quotas sobre o mesmo kernel, observar OOM,
verificar limpeza de projetos temporários, testar seccomp e resistência
a fuga de sandbox. **Não usar binários hostis em uma estação pessoal
apenas com estes testes.** A PR segue Draft.

## PE-S1.4 | Atestação privada de quotas e limpeza obrigatória

O modo `--require-cgroup-limits` agora usa um segundo diretório temporário
(`negresco-pe-proof-*`, 0700) **fora** do diretório `/work` disponibilizado
ao Ghidra. O verificador de cgroup escreve um JSON exclusivo (O_EXCL,
O_NOFOLLOW quando disponível, modo 0600 e fsync) **antes** de executar
o Bubblewrap. O arquivo contém identidade do escopo e limites efetivos
`memory.max`, `pids.max` e `cpu.max`, além de um identificador de
esquema. O verificador não sobrescreve evidência preexistente.

O executor confere que a prova é um arquivo regular privado, pertence ao
usuário, tem tamanho limitado, corresponde exatamente ao escopo requisitado
e contém quotas dentro da política. **Sem essa prova, o modo estrito não
publica relatório**, mesmo que um subprocesso retorne zero. O relatório
estrito passa a usar
`resource_scope=systemd_user_cgroup_v2_verified_at_start` e fornece um
resumo dos limites verificados. Essa indicação descreve apenas a verificação
na inicialização, **não** uma garantia contra alterações posteriores nem
isolamento de qualidade equivalente a uma VM.

O executor também exige que `systemctl --user stop <escopo>` retorne
sucesso para aceitar o resultado da análise estrita; se a solicitação
de parada falhar, descarta o relatório. **O retorno zero do systemctl
não comprova por si só que todos os descendentes terminaram.** Essa
hipótese deve ser testada com `pe_arch_descendant_smoke.py` em Arch
instalado; a matriz CI cobre somente testes simulados para esse caso.
O fluxo não solicita root, não desativa segurança do host, não analisa
software hostil nem publica APK/OTA.
