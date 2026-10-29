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

## PE-S1.5 | Aceitação nativa do Arch em VM descartável (pronta, NÃO executada)

**Esta etapa não está homologada no Arch real.** A CI Ubuntu + contêiner Arch
pode testar somente o contrato do validador; não consegue comprovar o
kernel Arch ou um gerenciador `systemd --user` de uma VM separada.

### Ambiente exigido

- VM Arch Linux independente, descartável e com snapshot, com systemd PID 1,
  cgroup v2 e sessão de usuário comum. **Não usar contêiner, PC principal
  ou root**. Não compartilhar HOME, chaves SSH, pastas sensíveis nem tokens
  da máquina hospedeira com essa VM.
- `python3`, `bubblewrap`, `systemd-run`, `systemctl`,
  `systemd-detect-virt` e `x86_64-w64-mingw32-gcc`, já instalados.
- Ghidra **12.2** previamente extraído de uma origem confiável. Validar
  separadamente o SHA-256 do arquivo oficial antes da extração. A versão
  informada em `Ghidra/application.properties` é conferida, mas **não
  constitui validação criptográfica** de toda a instalação.
- `JAVA_HOME` absoluto apontando para JDK **25** validado. Sem sudo,
  relaxamento de AppArmor, sysctl, nem bypass dos namespaces.

A execução de referência Ubuntu havia usado o ZIP
`ghidra_12.2_PUBLIC_20261016.zip` com SHA-256
`2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67`.
Reverificar o arquivo correto e sua proveniência antes de confiar nele.

### Comandos dentro da VM Arch

```bash
# Em uma sessão de usuário comum, com o repositório já clonado:
export JAVA_HOME=/caminho/do/jdk25
python3 tools/pe_arch_vm_gate.py
python3 tools/pe_arch_vm_validation.py \
  --ghidra-home /caminho/ghidra_12.2_PUBLIC \
  --ghidra-archive /caminho/ghidra_12.2_PUBLIC_20261016.zip \
  --timeout-seconds 420
```

A validação em cadeia, nesta ordem:

1. **VM gate:** exige Arch nativo, systemd PID 1, VM real (via
   `systemd-detect-virt --vm`), ausência de contêiner, usuário não-root,
   bus systemd de usuário, runtime próprio e ferramentas disponíveis.
2. **Cgroup smoke:** cria um escopo systemd e comprova na inicialização
   `memory.max`, `pids.max` e `cpu.max` com processo Python sintético.
3. **Descendant smoke:** cria um filho Python em sessão separada que
   ignora SIGTERM, e exige seu encerramento pelo cgroup após parada da
   unidade. Não conta o fallback de limpeza como sucesso.
4. **Probe Bubblewrap no próprio Arch:** compila primeiro o PE sintético
   inofensivo e executa `tests/pe_sandbox_probe.py` no exato perfil
   Bubblewrap usado pelo Ghidra. Exige namespace de rede separado,
   sentinela privada do host oculta, `/usr` somente leitura, acesso ao
   JDK configurado e escrita apenas no workspace permitido.
5. **Ghidra real:** analisa o mesmo PE sintético sem executá-lo com
   Bubblewrap obrigatório **e `--require-cgroup-limits`**. Exige prova
   privada de quotas, prévia de funções e pelo menos uma decompilação válida.

Todos os testes devem passar, na mesma VM, para retornar
`PASS_PE_S1_5_ARCH_VM`. Em qualquer falha, a saída será
`REJECTED_NOT_HOMOLOGATED` e o código de saída diferente de zero;
**não** desativar isolamentos para forçar aprovação. Arquivos PE e
relatórios intermediários são mantidos em diretórios temporários e
descartados; o resultado final contém apenas metadados da prova.

### Escopo da prova e próximos bloqueios

Mesmo uma aprovação real só confirma esse conjunto de operações na VM
e kernel específicos. Ela não prova resistência a exploit do kernel,
fuga de sandbox, seccomp nem segurança universal contra executáveis
hostis. A integração em uma interface gráfica, o IObit real, APK e OTA
continuam fora do escopo. PR Draft; `main` não alterada.

### Integridade obrigatória da instalação do Ghidra

Para a aceitação nativa a PE-S1.5 passou a exigir **o ZIP oficial
original** via `--ghidra-archive`. Antes de executar qualquer arquivo da
instalação, o validador verifica o SHA-256 fixado do ZIP inteiro, confirma
todos os arquivos descompactados comparando seus SHA-256 com as entradas
correspondentes do ZIP, rejeita links simbólicos, caminhos malformados,
duplicatas e arquivos adicionais no diretório do Ghidra. Não aceita apenas
`application.version=12.2` como prova de origem. Essa verificação é
intencionalmente rígida: use uma extração nova da release original. Isso
**não impede** que um administrador mal-intencionado modifique o host
durante a execução e tampouco substitui uma VM descartável.

## PE-S1.7 | Prova de descritores do host e adulteração real do Ghidra

O workflow Ubuntu agora executa duas verificações negativas adicionais:

- Depois de conferir o ZIP oficial Ghidra 12.2 e **cada arquivo**
  extraído, injeta um arquivo inofensivo inesperado na pasta do Ghidra.
  O verificador de integridade **precisa recusar** essa instalação.
  O pipeline remove o arquivo e só continua depois de conferir
  novamente a árvore oficial sem diferenças. Isso exercita a detecção
  com a instalação real, não apenas fixtures ZIP.
- O teste de isolamento cria uma sentinela privada do host, abre um
  descritor para ela e marca esse descritor como herdável no processo
  pai. Executa o Bubblewrap real com `close_fds=True`, e o Python
  dentro da sandbox verifica que nenhum descritor em
  `/proc/self/fd` expõe o par `st_dev/st_ino` da sentinela.
  A prova `inherited_host_fd_hidden=true` é obrigatória. O mesmo
  teste foi adicionado ao roteiro manual da VM Arch.

Essa prova é limitada **ao processo de teste dentro do Bubblewrap**
naquele sistema. Não demonstra ausência universal de vazamentos em
outros códigos, não substitui seccomp e não resolve exploits de kernel.
A etapa nativa em VM Arch segue pendente até haver registro de execução
no kernel Arch separado. Manter a PR Draft e não analisar software
suspeito no host principal.

## PE-S1.8 | Seccomp experimental com BPF do libseccomp

Uma camada adicional de teste foi introduzida, **ainda não habilitada
no executor de produção**. O módulo `tools/pe_seccomp_filter.py`
gera um cBPF usando `libseccomp` instalada no sistema Linux x86_64,
com política `SCMP_ACT_ALLOW` e recusa `EPERM` para chamadas
específicas: `ptrace`, `process_vm_readv/writev`, `bpf`,
`perf_event_open`, `userfaultfd`, carregamento de módulos,
`kexec`, `mount`, `setns`, `unshare` e outras operações
de administração do kernel. Chamadas necessárias ao Java como `mmap`,
`clone`, `futex`, `openat` e `execve` continuam permitidas.
**Isto é uma denylist parcial, não um perfil de permissões mínimas.**

A política é compilada num `memfd` com `CLOEXEC`, tamanho limitado
e **selos contra alteração**; passa apenas ao Bubblewrap por
`--seccomp FD` e `pass_fds=(fd,)`, e o processo pai fecha esse
descritor depois do lançamento. O próprio Bubblewrap precisa carregar
o cBPF dentro da sandbox. Não se instala seccomp no processo pai nem
se altera configuração de segurança do host.

O novo passo GitHub Actions usa um PE sintético e o Bubblewrap real.
Compara o número de filtros em `/proc/self/status` antes e dentro,
confere que `ptrace(PTRACE_TRACEME)` retorna `EPERM`,
e simultaneamente exige isolamento de rede, filesystem e descritor
privado do host. Testes de contrato verificam geração real do cBPF
e selagem do memfd em Ubuntu e Arch userspace. **Esperar o CI deste
commit terminar antes de declarar aprovado.**

Por cautela, Ghidra ainda usa o perfil Bubblewrap existente, **sem
seccomp obrigatório**. A política será integrada ao Ghidra só depois
de provar compatibilidade da análise real e o encaminhamento seguro
do descritor também através de `systemd-run --scope` no Arch nativo.
Ainda não há autorização para usar amostras hostis no host principal.

### PE-S1.8.1 | Compatibilidade do Ghidra 12.2 com seccomp real

O experimento passou a conter um segundo *smoke* separado:
`tools/pe_seccomp_ghidra_smoke.py`. Ele exige
`--ghidra-home` e `--ghidra-archive`, **reconfere o ZIP SHA-256
fixado e a árvore extraída**, compila a fixture PE do próprio repositório
e executa o Ghidra 12.2 real em Bubblewrap com o mesmo filtro seccomp
selado. A verificação exige retorno zero e inventário de pelo menos
uma função real, com validação de esquema e limites de tamanho. O PE
Windows é **lido**, nunca executado.

A CI Ubuntu agora testa a política primeiro com
`PTRACE_TRACEME=EPERM` e depois com Ghidra 12.2 de verdade. A suíte
de testes simulados verifica que o filtro via FD é obrigatório, que
falhas e inventário ausente são rejeitados, e que o FD é fechado.
**Aprovação depende da nova execução do workflow.**

Esta etapa **não** abrange o transporte do FD pelo
`systemd-run --user --scope` do caminho de cgroup estrito; logo o filtro
não se tornou obrigatório no fluxo principal. Também não substitui
a homologação do kernel Arch em VM separada.

### PE-S1.8.2 | Seccomp opcional no executor Negresco PE

Após o teste do Ghidra real com filtro, o runner
`tools/pe_auto_ghidra.py` recebeu a **opção explícita**
`--require-seccomp`. O padrão atual continua sendo apenas Bubblewrap,
sem ativação automática. A opção exige Linux x86_64, libseccomp e
um cBPF compilado/selado; anexa o `memfd` somente ao Bubblewrap com
`Popen(pass_fds=(fd,), close_fds=True)`, fechando o FD no pai mesmo
quando o lançamento falha. O relatório passa a distinguir
`seccomp_policy=bwrap_narrow_cBPF_requested` do estado
`not_enforced`. O campo indica a política solicitada, **não**
uma prova independente de todas as regras em toda execução.

**Combinação não homologada:** o runner rejeita
`--require-seccomp --require-cgroup-limits` por enquanto.
O encaminhamento do FD pelo `systemd-run --scope` ainda não recebeu
teste real na VM Arch; não existe fallback silencioso para o modo sem
seccomp nem para o modo sem quotas.

A CI ganhou um teste **ponta a ponta**: executa esse runner com
`--require-seccomp` e o Ghidra 12.2 real lendo o PE sintético,
e exige um relatório válido sem execução do PE.
Não usar isto como autorização para analisar amostras hostis no
computador pessoal; a integração com cgroup estrito e a homologação
nativa Arch seguem pendentes.

## PE-S1.9 | Ponte seccomp + cgroup criada dentro do escopo systemd

O impedimento anterior da passagem do filtro BPF por `systemd-run`
foi abordado por outra arquitetura, **ainda experimental**:

1. `wrap_in_cgroup_scope` cria um escopo systemd de usuário com ID
   aleatório, limites `MemoryMax=4GiB`, `TasksMax=128`,
   `CPUQuota=200%`, duração limitada e limpeza por cgroup.
2. `pe_cgroup_guard.py` inicia **dentro do escopo**, valida membership
   e quotas efetivas, registra uma prova JSON privada **fora do /work**
   e só então executa com `exec` o lançador
   `pe_scoped_seccomp_launcher.py`.
3. O novo lançador revalida membership e quotas, compila o cBPF
   usando a libseccomp **de dentro do próprio escopo** e passa
   exclusivamente seu descritor ao Bubblewrap via
   `Popen(close_fds=True, pass_fds=(fd,))`.
   O pai fecha o FD, propaga o exit code, encerra por timeout
   com limites e não usa shell, root ou bypass.
   **O filtro não atravessa `systemd-run`, nem é transmitido por D-Bus.**
4. O diagnóstico `pe_arch_scoped_seccomp_smoke.py` exige o
   `pe_arch_vm_gate.py` antes de executar a prova, cria apenas
   processos Python/PE sintéticos e comprova simultaneamente
   cgroup válido, prova privada, filtro aplicado (ptrace negado
   e número de filtros), namespace de rede, filesystem e FD privado
   do host. Qualquer ausência recusa o resultado.
5. A aceitação `pe_arch_vm_validation.py` exige essa nova prova
   conjunta **antes de iniciar** o teste de Ghidra real com cgroup.
   Ela também continua exigindo que o ZIP e a árvore do Ghidra
   correspondam à release oficial pinada.

Os testes em `tests/test_pe_scoped_seccomp_launcher.py` e
`tests/test_pe_arch_scoped_seccomp_smoke.py` cobrem o contrato nos
ambientes Ubuntu e Arch userspace do CI, **sem criar cgroup real**.
O passo de prova em VM Arch nativa só será homologado depois de uma
execução registrada nesse ambiente. A combinação `--require-seccomp
--require-cgroup-limits` no runner principal **permanece bloqueada**
até teste real da compatibilidade completa do Ghidra + seccomp + cgroup.
Não introduzir bypass, nem ativar esse modo automaticamente para
amostras desconhecidas.

O comando da VM continua:
```bash
python3 tools/pe_arch_vm_validation.py \
  --ghidra-home /caminho/ghidra_12.2_PUBLIC \
  --ghidra-archive /caminho/ghidra_12.2_PUBLIC_20261016.zip \
  --timeout-seconds 420
```
Instalar `libseccomp` da distribuição Arch antes da validação. A VM
deve ser descartável, sem pastas pessoais do host montadas e com
sistema, JDK e Bubblewrap verificados.

### PE-S1.9.1 | Ponte real testável sem fingir que Ubuntu é Arch

A CI Ubuntu executa `tests/pe_scoped_seccomp_bridge_real_ci.py`
como uma verificação **funcional da ponte**, distinta dos testes
simulados do código. Ela chama o próprio
`pe_scoped_seccomp_launcher.launch_scoped_bwrap`, cria um filtro
libseccomp cBPF real selado, passa seu FD ao Bubblewrap real e
executa dentro da sandbox o probe de rede/filesystem, descritores
do host, incremento de `Seccomp_filters` e `ptrace` recusado.
O pipeline só aceita os campos do probe e
`PASS_REAL_BRIDGE_WITH_MOCKED_CGROUP` com
`cgroup_enforcement_real=false`.

**Exatamente um controle é simulado:** a função
`verify_cgroup_limits` é substituída por mock nesse teste Ubuntu,
porque o runner não possui a sessão de escopo systemd de usuário
de uma VM Arch. Portanto, o teste comprova a criação do BPF
dentro do lançador e a transferência do FD, **não comprova
limites reais de cgroup ou pertencimento a uma unidade**.
Separadamente, o CI também exige que o kernel real recuse um
processo fora do escopo antes de compilar qualquer filtro.

O diagnóstico nativo `pe_arch_scoped_seccomp_smoke.py` agora exige
que a solicitação `systemctl --user stop` do escopo seja aceita.
Uma recusa da parada invalida toda a prova conjunta, mesmo que o
Bubblewrap termine com código zero. O teste original de descendentes
continua necessário, já que aceitar a parada não equivale a provar
a terminação de cada processo.

**Bloqueios mantidos:** nenhum resultado deste CI deve ser rotulado
como homologação Arch VM real, e a combinação
`--require-cgroup-limits --require-seccomp` no runner de
produção continua recusada. Sem mudanças na `main`, APK ou OTA.

## PE-S1.10 | Ghidra real com cgroup e seccomp no MESMO escopo Arch VM

A PE-S1.9 validou o transporte interno do filtro e os controles de
cgroup separadamente. Agora `tools/pe_arch_scoped_ghidra_smoke.py`
foi adicionado **à sequência obrigatória** de
`tools/pe_arch_vm_validation.py` para validar também Ghidra 12.2
executando realmente com ambos os controles no mesmo escopo nativo.

Na VM Arch descartável, depois de verificar a integridade SHA-256 do
Ghidra e compilar um PE sintético pertencente ao repositório:

1. O verificador cria um workspace `0700` e prova cgroup isolada
   em outro diretório privado; só o workspace é vinculado ao Bubblewrap.
2. `systemd-run --user --scope` cria um escopo novo, com limites de
   memória, CPU, tarefas e timeout; `pe_cgroup_guard.py` confirma os
   valores **do kernel** e grava prova privada antes do Ghidra iniciar.
3. Dentro desse escopo, `pe_scoped_seccomp_launcher.py` revalida os
   cgroups, compila o filtro cBPF selado e passa seu único descritor
   via `pass_fds` ao Bubblewrap, que inicia **Ghidra 12.2 real**
   sobre o PE sintético. Nenhum PE Windows é executado.
4. O diagnóstico exige exit code zero, as confirmações JSON de escopo
   e ponte, prova cgroup privada com limites finitos e inventário
   Ghidra validado com pelo menos uma função efetivamente decompilada.
   A solicitação de parada do escopo **também precisa ser aceita**.
5. Apenas com todas essas condições poderá retornar
   `PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP`.
   O `PASS_PE_S1_5_ARCH_VM` global passou a depender igualmente
   desse novo resultado. A prova funcional de `ptrace` negado,
   namespaces e descendent cleanup permanece exigida à parte.

Os testes `tests/test_pe_arch_scoped_ghidra_smoke.py` simulam
somente a infraestrutura indisponível na CI, e rejeitam ausência de
escopo, falta de relatório, nenhuma decompilação, processo com erro
e falha ao solicitar parada do cgroup. Esses testes são **contratos**
e não constituem homologação real do kernel Arch.

**Status:** implementação e roteiro disponíveis na PR Draft.
Até o roteiro ser executado em uma VM Arch independente com
evidência verificável, a CLI principal mantém
`--require-seccomp --require-cgroup-limits` BLOQUEADO. O teste de
aceitação habilita a combinação apenas dentro do harness de VM
restrito a um PE sintético. Sem alterações à main, APK ou OTA.

## PE-S1.10.1 | Ghidra real através da ponte seccomp (CI Ubuntu)

A CI passou a executar `tests/pe_scoped_ghidra_bridge_real_ci.py`,
um teste adicional que usa o **Ghidra 12.2 oficial real** (ZIP original
e árvore verificados contra o SHA-256 fixado), Bubblewrap real e
`pe_scoped_seccomp_launcher.launch_scoped_bwrap` real, incluindo a
compilação e passagem do filtro libseccomp cBPF selado.
O Ghidra lê exclusivamente um PE sintético produzido por
`tests/fixtures/pe_headless_smoke.c`. A evidência real exige
`ghidra-functions.json` com inventário válido e
`ghidra-deep.json` com pelo menos uma função decompilada, validados
pelas rotinas de leitura do próprio NegrescoDroid.

Nesse teste **somente `bridge.verify_cgroup_limits` é mockado**
porque o runner Ubuntu não possui um escopo systemd de usuário
com quotas nativas Arch. A resposta inclui, obrigatoriamente,
`cgroup_verification=MOCK_ONLY_NOT_HOMOLOGATED` e
`native_arch_vm_executed=false`; nunca emite o token reservado
`PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP`.
Os testes negativos rejeitam pacote Ghidra não verificado, erro
do Bubblewrap, falta do recibo da ponte, inventário vazio e
ausência de decompilação.

Isso demonstra compatibilidade da integração real
**lançador → filtro seccomp → Bubblewrap → Ghidra → decompilação**,
mas **NÃO demonstra quotas reais no kernel Arch**. A aceitação
final continua condicionada ao roteiro `pe_arch_vm_validation.py`
executado em VM Arch Linux descartável com systemd/cgroups reais.
Até isso acontecer, a combinação de seccomp+cgroup no analisador
principal segue deliberadamente recusada. Sem merge na main,
publicação APK/OTA ou execução de amostras desconhecidas no host.

## PE-S1.11 | Medição seccomp NA JVM real do Ghidra

O teste anterior provava que um probe Python isolado recebia
`seccomp`, e que o Ghidra decompilava dentro da ponte. Agora há uma
terceira medição feita pelo **próprio processo Java do Ghidra**.

- O lançador `pe_scoped_seccomp_launcher.py` lê, após a validação
  de cgroups e **antes** de compilar/anexar o BPF, a contagem
  `Seccomp_filters` do kernel em `/proc/self/status`. O recibo
  inclui `seccomp_filters_before_bwrap`, ligado ao escopo aleatório.
- O postScript confiável
  `NegrescoSeccompRuntimeProof.java`, rodando **dentro da JVM
  Ghidra headless**, lê o próprio `/proc/self/status` e recusa
  `Seccomp != 2` ou nenhum filtro. Ele só grava
  `ghidra-seccomp-runtime.json` em `/work` se houver programa
  carregado e a análise não tiver expirado.
- `pe_seccomp_runtime_evidence.py` lê o arquivo por FD
  `O_NOFOLLOW`, com limites de tamanho, proprietário, estrutura,
  tipos exatos, sem chaves duplicadas; exige **número de filtros
  na JVM estritamente maior que o baseline do lançador**, evitando
  confundir filtros herdados do host com o novo filtro.
- O teste Ubuntu `pe_scoped_ghidra_bridge_real_ci.py` exige essa
  prova além do inventário e pseudocódigo reais, mas continua
  declarando cgroups como `MOCK_ONLY_NOT_HOMOLOGATED`.
  `pe_arch_scoped_ghidra_smoke.py` exige a mesma prova, junto com
  quotas efetivas do kernel Arch, assim que a VM independente
  executar o roteiro.
- Testes rejeitam caminhos symlink, provas com permissões de
  escrita inseguras, dados alterados, contagem sem aumento,
  declaração de processo diferente da JVM, campos repetidos
  e modo seccomp incorreto.

Isso confirma o **estado registrado pelo kernel da JVM testada**.
Não equivale a provar ausência de todas as possibilidades de
escape do kernel ou que cada syscall de uma denylist seja
impossível; a prova funcional de `ptrace=EPERM` em Python dentro
do Bubblewrap continua exigida separadamente.
A PR permanece Draft; a CLI normal continua recusando a
combinação `--require-seccomp --require-cgroup-limits`.

## PE-S1.12 | VM Arch exigida em cada entrada e recibo de auditoria local

Os métodos `run_scoped_seccomp_probe()` e
`run_native_scoped_ghidra()` passaram a chamar
`verify_arch_vm()` **dentro da própria função**, antes de
criar unidade systemd, compilar filtro seccomp ou iniciar Ghidra.
Antes, ambos pressupunham que o método pai já havia feito isso.
Uma importação direta por engano agora recusa containers, host sem
VM, root e sessão systemd de usuário inadequada. Testes positivos
e negativos exercitam esse contrato em Ubuntu e Arch userspace
**sem executar testes destrutivos de escopo no CI**.

O comando original de aceitação nativa continua suportado. Para
registrar os resultados numa VM Arch descartável com login de
usuário comum e diretório privado já criado:

```bash
mkdir -m 700 -p "$HOME/negresco-arch-proof"
python3 tools/pe_arch_vm_validation.py \
  --ghidra-home /caminho/ghidra_12.2_PUBLIC \
  --ghidra-archive /caminho/ghidra_12.2_PUBLIC_20261016.zip \
  --timeout-seconds 420 \
  --reviewer-challenge "$REVIEWER_CHALLENGE" \
  --evidence-output "$HOME/negresco-arch-proof/acceptance.json"
```

O destino precisa ser **absoluto, novo e dentro de um diretório
pertencente ao usuário e inacessível a grupo/outros (0700)**.
O arquivo é criado com modo `0600`, com `O_EXCL` e
`O_NOFOLLOW`, sem shell, sem privilégios e sem sobrescrever
resultados anteriores. Se já existir, a operação falha em vez
de modificar a prova.

Somente uma aceitação real com `PASS_PE_S1_5_ARCH_VM`,
`ARCH_VM_PREFLIGHT_PASSED`, encerramento de descendentes,
Ghidra verificado, quotas privadas válidas, escopo terminado,
decompilação presente e seccomp comprovado **dentro da JVM**
pode gerar o recibo. O JSON armazena o relatório, SHA-256 canônico
desse relatório e hashes/tamanhos do código de validação, ponte,
exportadores Ghidra e fixture sintética. Isso permite detectar
corrupção acidental e vincular o relato aos arquivos analisados.

**Limitação importante:** o recibo é um autorrelato LOCAL
(`LOCAL_SELF_REPORT_NOT_SIGNED`), não um atestado assinado ou
verificação independente de hipervisor/kernel. Hashes podem ser
recalculados ou forjados por alguém que controle a VM.
Guardar a prova e os logs originais fora da VM é uma etapa manual,
antes de descartar a VM; nenhuma transferência/upload acontece
automaticamente. Não acrescenta autorização para executar
amostras hostis e não ativa `--require-seccomp --require-cgroup-limits`
na aplicação principal.

A PR permanece Draft até homologação nativa independente.

## PE-S1.13 | Encerramento de scopes transitórios, sem falso positivo/negativo

O diagnóstico nativo não usa mais `systemctl --user stop` sozinho como
veredito de limpeza: unidades `*.scope` transitórias podem ser removidas
pelo systemd **entre o fim do último processo e a tentativa de parada**.
Uma chamada `stop` que falha nesse cenário não prova que existam
descendentes sobreviventes. Por outro lado, `stop` com retorno zero
não prova que o cgroup já esteja vazio.

`tools/pe_scope_cleanup_evidence.py` sempre solicita a parada, consulta
separadamente as propriedades exatas `LoadState`, `ActiveState`,
`SubState` e `ControlGroup` via `systemctl --user show` e exige:

- `ActiveState=inactive` e `SubState=dead`, com `LoadState=loaded`
  ou `not-found`. Um scope coletado com `not-found` pode ter
  `stop_request_accepted=false` **sem reprovação automática**.
- Nenhuma referência a cgroup de outro escopo, nem caminho relativo,
  `..`, componente vazio ou symlink escapando de `/sys/fs/cgroup`.
- Se a pasta do cgroup ainda existe, a evidência **do kernel**
  `cgroup.events` deve conter exatamente `populated 0`;
  `populated 1`, falta da informação, erro na consulta e scope
  ainda ativo resultam em rejeição.
- O cgroup pode já ter sido removido. Seu desaparecimento é aceito
  apenas em conjunto com a confirmação estrita de inatividade
  pelo systemd e, para qualquer aprovação final, com a
  **prova cgroup privada anterior** de que aquele mesmo escopo
  foi realmente criado e limitado.

Os scripts nativos do probe Bubblewrap e do Ghidra combinado exigem
`scope_cleanup_evidence` com `verified=true`,
`scope_quiescent=true` e `cgroup_unpopulated=true`. O gate
`pe_arch_vm_validation.py` e o gerador do recibo local SHA-256
exigem as mesmas evidências; o novo script integra o manifesto de
fontes criptografadas do recibo `LOCAL_SELF_REPORT_NOT_SIGNED`.

Os testes `test_pe_scope_cleanup_evidence.py` simulam unidades
`not-found`, escopos ainda ativos, cgroups `populated 0/1`,
saídas malformadas/duplicadas e paths inválidos. Essas simulações,
executadas em Ubuntu e Arch userspace, **não são prova nativa do
kernel Arch**. A homologação ainda requer VM Arch descartável,
prova de limite CPU/RAM/PIDs e teste separado de limpeza de
descendentes com processos reais.

Proteção combinada no runner principal permanece recusada;
PR Draft, `main` intocada, nenhuma publicação APK/OTA.

## PE-S1.14 | Ciclo completo do descendente e vinculação do escopo

A inspeção de riscos encontrou duas lacunas nos contratos anteriores
da homologação Arch VM:

1. `run_native_descendant_smoke()` fazia somente `preflight()`
   de Arch/systemd. Uma chamada direta poderia iniciar um processo
   sintético deliberadamente resistente a SIGTERM em um workstation
   Arch fora de uma VM descartável. Agora o método reexecuta
   `verify_arch_vm()` **antes de criar um novo scope**; recusará
   host físico, container, root ou VM sem user bus. Os modos
   auxiliares `--worker` e `--grandchild` também exigem a VM
   descartável **antes** de entrar no loop resistente a SIGTERM.
2. A confirmação do desaparecimento da identidade PID/starttime
   do descendente não prova por si só que todo o cgroup ficou vazio.
   Após solicitar parada do scope com o filho **ainda ativo**,
   o teste exige tanto a morte do descendente observado quanto
   `stop_and_attest_scope(unit)`: estado systemd
   `inactive/dead` e cgroup v2 `populated 0` ou removido.
   Uma confirmação incerta, populated=1 ou scope divergente recusa
   a homologação, ainda que o PID já não esteja ativo.

O mecanismo de limpeza PE-S1.13 agora inclui `scope` em seu
resultado, de modo que **o relatório de fim e o escopo de início
precisam usar o mesmo identificador**, nos três percursos
(sonda seccomp, Ghidra conjunto e descendente). O gerador
de recibo local `pe_arch_vm_evidence.py` exige o novo campo
`descendant_lifecycle` completo, stop aceito, identidade do
escopo e prova de quiescência. Um JSON ausente ou incompleto
retorna rejeição controlada; os testes negativos impedem a
aceitação de recibos copiados de outro escopo.

Os testes são **contratos mockados** para a parte systemd em
Ubuntu/Arch userspace; nenhum teste do GitHub Actions alega
matar descendentes reais numa VM Arch independente.
A homologação `PASS_PE_S1_5_ARCH_VM` ainda só pode ocorrer
na VM descartável, com cgroups e seccomp reais, Ghidra 12.2
oficial, fixture Windows sintética e relatório SHA-256
`LOCAL_SELF_REPORT_NOT_SIGNED`.

A opção conjunta `--require-seccomp --require-cgroup-limits`
continua **BLOQUEADA** no runner normal. Nenhuma alteração
na main ou publicação APK/OTA.

### Complemento PE-S1.14 | Prova privada de quota e modos internos

A verificação dos descendentes deixou de inferir aplicação dos
limites por procurar um fragmento de JSON em `scope.stdout`.
O `pe_cgroup_guard.py` passa agora a escrever, antes do worker,
uma prova privada `quota.json` em diretório modo 0700
(não compartilhado com o Bubblewrap); o teste lê a prova por
`read_scope_proof(proof_path, scope)` e recusa valores fora
da política (memória até 4 GiB, `pids.max` até 128,
CPU até 200%), arquivo ausente e escopo incorreto.
O stdout ainda exige **exatamente um** registro estruturado
do cgroup guard. A validação conjunta requer confirmação de
stop com o descendente ativo, a morte da identidade PID/starttime,
e a evidência independente systemd/kernel de cgroup vazio.

Além do método principal, a CLI interna `--worker` e
`--grandchild` agora reexecuta `verify_arch_vm()` antes
de iniciar qualquer loop. A ausência do ambiente VM é
recusa obrigatória, também nas chamadas diretas.
O relatório final mantém `descendant_lifecycle` com
`quota_private_proof` e `descendant_cleanup_evidence`,
e o recibo SHA-256 rejeita ambos ausentes ou inconsistentes.

**Limitação:** o GitHub Actions verifica contratos simulados
para o ciclo de vida do systemd e do kernel Arch.
A prova nativa ainda depende da execução em VM Arch
independente. Não há desbloqueio da combinação cgroup+seccomp
no executor habitual nem merge, APK ou OTA.

## PE-S1.15 | Leitura sem corrida da prova cgroup e reconciliação de quotas

A prova privada `quota.json` criada pelo `pe_cgroup_guard.py`
é uma evidência independente do stdout. Em PE-S1.15, o validador
`tools/pe_resource_evidence.py` foi reforçado para **nunca**
aceitar somente uma string `cgroup_verification=passed`.

- A pasta da prova precisa ser privada e de propriedade do usuário;
  é aberta uma única vez com `O_DIRECTORY|O_NOFOLLOW` e mantida
  por um descritor exclusivo durante a leitura. O JSON é aberto
  relativo ao FD dessa pasta com `O_NOFOLLOW`, impedindo que
  uma substituição do caminho entre os testes de metadados e a
  abertura redirecione a leitura.
- `fstat` e leitura limitada a 4096 bytes exigem arquivo regular
  `0600` ou mais restrito, dono correto, tamanho finito,
  e ausência de alteração perceptível durante a leitura.
  O parser JSON recusa chaves duplicadas, campos desconhecidos,
  `NaN`/`Infinity`, tipos incorretos, nomes de scope diferentes
  e orçamento de memória/tarefas/CPU fora da política.
- A função `corroborate_guard_receipt()` exige **exatamente um**
  recibo `cgroup_verification=passed` e compara seus quatro
  números com o arquivo privado: `memory_max`, `pids_max`,
  `cpu_quota`, `cpu_period`. Qualquer diferença ou falta
  de prova resulta em recusa. Ela é exigida nos três caminhos
  de aceitação nativa: descendente, sonda seccomp e Ghidra real
  no mesmo escopo.
- Testes negativos em `test_pe_resource_evidence.py` cobrem
  arquivo ausente, pasta compartilhada ou symlink, JSON duplicado,
  campos adicionais e relatórios com quotas contraditórias.
  Esses são **testes de contrato**, não equivalem a observar
  quotas reais num kernel Arch.

Uma primeira execução detectou falha de implementação ao tentar
tratar um diretório como arquivo binário via `os.fdopen`.
Corrigimos para preservar o descritor cru da pasta num context
manager com `os.close`. O testador PE safe-intake confirmou a
correção; a matriz Sandbox/Ghidra precisa concluir para aprovar
a etapa toda.

A VM Arch descartável com cgroups/seccomp simultâneos continua
o requisito de homologação. CLI normal bloqueada, PR Draft,
sem alteração na main e sem publicar APK/OTA.

## PE-S1.16 | Executor principal: prova de encerramento, não só `stop`

A análise identificou que o executor principal `tools/pe_auto_ghidra.py`
continuava usando exclusivamente o retorno de `stop_scope()` para
autorizar a publicação em modo `--require-cgroup-limits`. O mecanismo
nativo PE-S1.13 já distinguia entre um escopo transitório recolhido
automaticamente pelo systemd e um escopo ainda ativo/com cgroup populado.

Agora `inspect_functions()` reutiliza diretamente
`stop_and_attest_scope(unit)` **sempre** após a execução estrita,
inclusive quando o Ghidra expira e é interrompido. A aceitação exige
recibo com o mesmo nome do escopo, `verified=true`,
`scope_quiescent=true`, `cgroup_unpopulated=true`,
`ActiveState=inactive` e `SubState=dead`.
Uma unidade transitória comprovadamente recolhida (com
`stop_request_accepted=false`) pode ser aceita; `stop` que
retorna zero, mas mantém cgroup ativo/ocupado, não pode.

Em caso de sucesso, a evidência de limpeza também integra
`limitations.resource_cleanup`, além da prova de limites
`limitations.resource_limits` (obtida do arquivo privado
`quota.json` pela leitura segura PE-S1.15).
O campo `resource_scope` segue descrevendo limites medidos
na partida; nenhum resultado afirma que Ghidra foi imune a
escapes de kernel ou que houve VM Arch independente.

Testes negativos em `tests/test_pe_auto_ghidra.py` verificam
rejeição sem estado final, com cgroup ainda ativo, prova de outro
escopo e timeout. Um teste positivo admite o escopo já recolhido
sem relaxar a exigência de cgroup vazio. A combinação conjunta
`--require-seccomp --require-cgroup-limits` **continua
recusada** no caminho principal. A integração simultânea só
poderá ser liberada depois da execução e revisão independente
do roteiro em VM Arch nativa.

PR continua Draft, sem merge na main ou publicação APK/OTA.

## PE-S1.17 | Política numérica para o recibo nativo e stdout

O recibo de aceitação da VM Arch não pode aceitar um relatório
baseado apenas nas strings `PASS_*` e
`verification=guard_verified_before_bwrap`. Isso permitiria
que um resultado incorreto com orçamento numérico ausente,
infinito ou acima da política fosse serializado como se fosse
comprovação de uma execução controlada.

- `pe_arch_vm_evidence.validate_native_acceptance_report` exige
  números **inteiros, finitos e positivos**, sem `bool` e sem
  strings, em **quatro medições independentes**:
  `cgroup` (sonda original), `descendant_lifecycle.quota_private_proof`,
  `ghidra.arch_scoped_seccomp_probe.cgroup_verification` e
  `ghidra.arch_real_ghidra_with_both.quotas_verified_before_bwrap`.
  Todos respeitam o teto definido em `pe_resource_limits`:
  4 GiB de RAM, 128 tarefas e quota de CPU de no máximo 200%,
  com período de CPU positivo. Valores menores são válidos
  porque um escopo pode herdar uma política mais restritiva.
- As três sondas devem ter nomes de scope que obedeçam ao
  padrão de IDs aleatórios do projeto, **distintos entre si**.
  A reutilização de um scope entre sonda de descendente,
  seccomp e Ghidra combinado recusa o recibo, mesmo que
  os documentos individuais aparentem estar corretos.
- O recibo da JVM precisa indicar a origem
  `/proc/self/status`, `Seccomp=2`, contagens inteiras
  entre 0 e 4096, aumento de filtros e delta
  `additional_filters_observed` matematicamente consistente.
- A mesma validação agora é executada em
  `pe_arch_vm_validation.run_acceptance` **antes de anunciar
  `PASS_PE_S1_5_ARCH_VM` no stdout**, mesmo quando o
  usuário não solicita `--evidence-output`. Erros de
  coerência convertem-se em `REJECTED_NOT_HOMOLOGATED`;
  não existe caminho de aprovação mais fraco sem recibo.

Os novos testes de contrato simulam orçamento acima da
política, campos booleanos/string, contagem falsa de filtros,
reuse de ID de scope e ausência de relatório. **Não comprovam
que a VM nativa Arch tenha sido executada.**
Mesmo um recibo local válido é explicitamente classificado
`LOCAL_SELF_REPORT_NOT_SIGNED`, nunca prova criptográfica
externa de kernel, hipervisor ou da autoria dos eventos.

A PR permanece Draft; `main` e APK/OTA intactos. A
combinação `--require-seccomp --require-cgroup-limits`
continua bloqueada para uso normal.

## PE-S1.18 | Verificação de cgroup.events sem follow de links nem leitura ilimitada

A auditoria do encerramento encontrou um ponto ainda frágil da
PE-S1.13: `_cgroup_unpopulated()` lia `cgroup.events` diretamente
via `Path.read_text()`, sem limite de bytes e sem impedir
redirecionamento por symlinks intermediários ou no próprio arquivo.

A leitura foi substituída por um percurso de descritores, sem shell,
que abre `/sys/fs/cgroup` e cada componente da árvore apontada pelo
systemd com `O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`. Abre o arquivo
`cgroup.events` relativo ao diretório da unidade com `O_NOFOLLOW`.
O código só aprova evidência de kernel regular, legível, limitada
a **4096 bytes**, codificada em ASCII e terminada em newline.
Exige exatamente uma chave `populated`, de valor `0`;
recusa duplicatas, dados malformados, valores não numéricos,
`populated=1`, conteúdo truncado, arquivo simbólico e
caminhos com `..`/componente vazio.

A unidade pode desaparecer legitimamente porque o systemd
recolhe scopes transitórios. Um diretório ausente por `ENOENT`
é aceito apenas dentro da rotina que já exige consulta ao
systemd com `LoadState=loaded|not-found`, `ActiveState=inactive`,
`SubState=dead`. Erros de permissão, redirecionamento, ausência
de `cgroup.events` numa unidade ainda existente e resultados
inconclusivos rejeitam a homologação. O recibo privado de quotas
anterior continua obrigatório para provar que o escopo havia
sido criado e limitado.

Os testes negativos novos em
`tests/test_pe_scope_cleanup_evidence.py` usam **somente
uma árvore sintética local**, cobrindo symlink de diretório
final/intermediário, symlink no evento, saída excessiva,
duplicações, truncamento e valores falsos. O teste positivo
aceita campos extras do cgroup v2, mantendo `populated 0`
obrigatório. O GitHub Actions não executa uma unidade
cgroup nativa Arch com processos reais; essa validação ainda
requer uma VM Arch Linux independente.

O executor normal ainda recusa `--require-seccomp`
junto de `--require-cgroup-limits`. PR Draft,
`main` intocada e sem APK ou OTA.

## PE-S1.19 | Quatro ciclos de cgroup completos, incluindo a sonda inicial

A revisão da sequência `run_acceptance()` encontrou uma assimetria:
`run_smoke()`, que roda **antes** do teste com descendente resistente
a SIGTERM, aceitava recibos do stdout e entregava valores de quotas,
mas ainda não comprovava por arquivo privado o estado do cgroup nem
verificava independentemente a limpeza do próprio escopo.

A etapa inicial agora:

- Cria diretório temporário privado, passa um destino `quota.json`
  para o `pe_cgroup_guard` e exige a leitura protegida
  `read_scope_proof(path, unit)`. O guard e o arquivo privado
  precisam concordar em memória, PIDs, quota/período de CPU via
  `corroborate_guard_receipt`.
- Mantém parsing limitado a 32768 bytes de stdout, recusa chaves
  JSON duplicadas, `NaN`, registros de guard duplicados e marcador
  do filho ausente ou repetido. O processo Windows **não é executado**.
- Em todas as saídas da invocação do processo, solicita parada e
  exige `stop_and_attest_scope(unit)`, com estado
  `inactive/dead`, mesmo nome de unidade e ausência de
  processos no cgroup. Falha de cleanup ou scope ainda ativo
  converte qualquer suposto resultado `PASS` em rejeição.
- Anexa `quota_private_proof` e `scope_cleanup_evidence`
  à sonda inicial. O validador principal recusa provas incompletas
  **antes de iniciar** o teste com filho SIGTERM-resistant, e
  preserva a sonda inteira no campo `cgroup_lifecycle`.
- O recibo local agora confirma **quatro scopes diferentes**:
  sonda inicial, descendente, ponte seccomp e Ghidra simultâneo.
  Para o primeiro, exige coincidência exata dos quatro números
  de quota entre `cgroup`, `cgroup_lifecycle` e seu arquivo privado,
  além da prova de limpeza e das flags de não execução PE/Ghidra.

Os testes `test_pe_arch_cgroup_smoke.py`,
`test_pe_arch_vm_validation.py` e
`test_pe_arch_vm_evidence.py` foram ampliados com casos de
falta de arquivo privado, discordância de quotas, falso sucesso,
escopo populado, timeout, recibo reutilizado e bloqueio da
fase perigosa quando a primeira sonda falha. Os jobs
Ubuntu/Arch userspace são **contratos simulados**, não
homologação em VM Arch nativa.

Permanece obrigatória execução independente da VM Arch com
systemd+cgroups reais e seccomp ativo na JVM antes de qualquer
desbloqueio de `--require-seccomp --require-cgroup-limits`.
PR segue Draft; `main`, APK e OTA intactos.

## PE-S1.20 | Revisão independente do recibo local, sem assinatura falsa

Foi criado o verificador **offline** `tools/pe_arch_vm_receipt_verify.py`.
Ele não aceita um arquivo de evidências só porque contém
`PASS_PE_S1_5_ARCH_VM`. Reabre o recibo produzido por
`--evidence-output` em uma pasta privada 0700, por descritores
`O_NOFOLLOW`, com arquivo 0600 e leitura máxima de 1 MiB.
O parser rejeita chaves JSON duplicadas, campos desconhecidos e
constantes não finitas. O verificador compara o SHA-256 do relatório
canônico, roda **novamente** os contratos completos de
`validate_native_acceptance_report`, verifica o manifesto exato
de arquivos-fonte e reabre cada arquivo a partir do checkout de
código fornecido, sem seguir links simbólicos em seus componentes.
Cada hash e tamanho precisa bater exatamente com o manifesto.

O novo script integra `SOURCE_FILES`, portanto o próprio código do
verificador será incluído nos hashes da próxima aceitação. Pode ser
executado por outro revisor, sem privilégios de administrador e sem
executar PE, Ghidra, systemd ou acessar a rede:

```bash
python3 tools/pe_arch_vm_receipt_verify.py \
  --receipt /caminho/privado/acceptance.json \
  --source-root /caminho/do/checkout/exato \
  --expected-challenge "$REVIEWER_CHALLENGE"
```

Um resultado aprovado retorna apenas
`LOCAL_RECEIPT_CONSISTENCY_VALIDATED` com
`native_kernel_execution_independently_verified=false` e
`UNSIGNED_NOT_INDEPENDENT_VM_ATTESTATION`. A ausência de
assinatura ou chave confiável significa que uma pessoa capaz de
alterar simultaneamente recibo e repositório também pode recalcular
esses hashes. **Nenhuma verificação de hash prova que houve uma
VM Arch independente**, nem mede retroativamente quotas ou seccomp
do kernel. A homologação real ainda exige execução acompanhada na
VM e análise externa das evidências originais.

Contratos em `tests/test_pe_arch_vm_evidence.py` cobrem aprovação
somente de consistência local, adulteração do relatório, hash da
fonte, manifestação incorreta, symlinks, permissões abertas,
entrada acima do limite, JSON com chaves duplicadas e status não
assinado. `main` continua intacta; sem merge, APK/OTA ou liberação
de `--require-seccomp --require-cgroup-limits`.

## PE-S1.21 | Proteção contra symlinks em ancestrais de caminhos

A revisão da PE-S1.20 identificou que `O_NOFOLLOW` aplicado ao
diretório final não impede que um componente **anterior** do caminho
seja um link simbólico. A mesma limitação existia na criação do recibo
e no hashing de fontes locais.

`tools/pe_nofollow_paths.py` percorre cada componente de caminhos
absolutos a partir do FD do diretório raiz, usando
`openat` / `dir_fd` e `O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`.
O leitor de recibos, o escritor de recibos e os dois lados do manifesto
de fontes compartilham agora a mesma política, sem `resolve()` sobre
entradas não confiáveis. Os descritores de diretórios pais permanecem
abertos durante a operação; a criação do recibo segue exclusiva,
com arquivo 0600 em diretório 0700 e sem sobrescrita.

O escritor de manifesto também verifica metadados antes e depois da
leitura de cada arquivo, rejeitando trocas detectáveis durante a
aquisição. Testes negativos cobrem link simbólico em **ancestral**
da pasta privada do recibo, em ancestral do checkout e dentro do
diretório de manifesto, tanto na leitura quanto na gravação.

**Escopo:** essa proteção corrige a travessia por symlinks, não é uma
assinatura digital, não garante integridade de um kernel comprometido,
nem autentica a VM Arch. A execução ponta a ponta com systemd,
cgroups e seccomp no mesmo kernel Arch continua pendente. A PR
permanece Draft; `main`, APK/OTA e a combinação bloqueada do
executor principal permanecem inalterados.

## PE-S1.22 | Recibo nativo exige provas integrais de isolamento e identidade do Ghidra

A auditoria do contrato encontrou campos emitidos pelo roteiro
`run_acceptance()` que o validador do recibo não exigia:
`arch_isolation_probe` de Bubblewrap, SHA-256 pinado e propriedades
da instalação Ghidra, resumo de quotas do Ghidra isolado,
`sandbox_checks` de seccomp e negações de execução de PE em estágios
individualizados. Recibos autodeclarados ainda conseguiam passar
sem parte dessas provas ou com valores contraditórios.

O `validate_native_acceptance_report()` agora exige isolamento
de rede, HOME e FDs do host, montagem read-only e workspace
privado; versão atestada pelo digest fixo de Ghidra 12.2, árvore
com arquivos conferidos e sem extras/symlinks; quotas finitas
também no resumo da análise standalone; observações de filtro
seccomp após o guard, probes completos, estado final de escopo,
identidade de VM não-root com bus de systemd e afirmações
consistentes de não execução do Windows PE em todas as etapas.

O inventário de funções e a contagem de descompilações devem
ser positivos e coerentes. Os testes simulam campos ausentes,
falsos, incongruentes, scopes com limpeza não comprovada e
identidade de release adulterada. Todos são **contratos sobre
recibos sintéticos**, não uma execução de VM Arch com kernel
real. O verificador offline continua classificando sua saída
como `LOCAL_RECEIPT_CONSISTENCY_VALIDATED`, nunca como
atestação independente de hipervisor. Nenhuma opção bloqueada
foi desbloqueada, a PR continua Draft, sem alteração da main
nem publicação de APK/OTA.

## PE-S1.23 | Integridade do Ghidra por descritores ancorados

A verificação do Ghidra comparava os arquivos com o ZIP oficial, mas
usava `Path.open()`, `os.walk()` e caminhos completos em algumas leituras.
Isso permitia que diretórios ancestrais simbólicos fossem seguidos e
abria janelas de alteração entre o exame do caminho e sua leitura.

O verificador `pe_ghidra_integrity.py` agora abre o diretório da
instalação, os ancestrais do ZIP e seus arquivos por descritores
ancorados com `O_NOFOLLOW`. O mesmo arquivo aberto é usado para hash
e leitura do ZIP oficial. As leituras de cada arquivo extraído conferem
`fstat` antes e depois, e a listagem completa também percorre
diretórios por FDs, rejeitando links e entradas não regulares.

Foram incluídos testes negativos de symlink em ancestral da instalação,
ancestral do arquivo ZIP, diretório intermediário e entrada tipo FIFO.
A suíte sintética só valida contratos locais; a CI Ubuntu usa o ZIP
oficial e repete o teste de adulteração da árvore extraída.

**Limite**: FDs ancorados comprovam os bytes examinados; não impedem
mudança posterior do diretório antes do lançamento de Ghidra por
um adversário com privilégios suficientes, nem atestam uma VM Arch
independente. A PR permanece Draft; combinação real cgroup+seccomp
não foi liberada, sem merge, publicação APK ou OTA.


## PE-S1.24 | Desafio externo para correlacionar recibos a uma execução

A homologação manual com `--evidence-output` agora **recusa iniciar**
sem um desafio externo válido. O revisor escolhe aleatoriamente 32 bytes
(64 caracteres hexadecimais minúsculos) **fora da VM** antes do teste,
registra esse valor em um local independente e fornece-o à VM pelo
parâmetro `--reviewer-challenge`. A CLI valida o desafio antes de
executar cgroups, descendentes ou Ghidra. O recibo usa o esquema
`negresco_native_arch_vm_local_receipt_v2` e inclui esse valor na
estrutura persistida de modo exclusivo, 0600, sob diretório 0700.

Depois da coleta, o verificador offline recusa arquivos v1 ou que não
correspondam ao `--expected-challenge` **fornecido novamente pelo
revisor**. Não aceita entrada ausente, não-canônica, 0 repetido, JSON
alterado ou desafio usado em outra revisão. Todos os hashes e
contratos anteriores continuam obrigatórios. Os testes sintéticos
cobrem adulterações, replay de desafio diferente, v1 e pré-validação
da CLI antes de iniciar tarefas da VM.

Exemplo de preparação **no equipamento externo do revisor**
(não na VM):

```bash
REVIEWER_CHALLENGE="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
printf 'Desafio da revisão: %s\n' "$REVIEWER_CHALLENGE"
```

Transfira o valor à VM por um canal controlado, forneça-o apenas
na primeira execução nativa de aceitação e preserve o registro original
com o revisor. Use o mesmo valor na revisão offline, fora da VM.
Não reutilize desafios entre aceites.

**Limitação obrigatória:** um desafio de revisão não é assinatura
digital nem atestado do hipervisor ou do kernel. Um executor malicioso
que veja o desafio pode produzir um relatório falso com ele.
O resultado continua `LOCAL_RECEIPT_CONSISTENCY_VALIDATED`, com
`native_kernel_execution_independently_verified=false`. A
homologação real conjunta em VM Arch independente continua
**pendente**. PR permanece Draft; sem `main`, APK, OTA ou
desbloqueio do modo seccomp+cgroups.

## PE-S1.25 | Leitura segura dos comprovantes de kernel e JVM

A revisão dos comprovantes detectou dois pontos fracos: o validador do
arquivo de quotas cgroup `pe_resource_evidence.py` ancorava apenas o
diretório final, permitindo seguir links simbólicos em ancestrais;
e `pe_seccomp_runtime_evidence.py` abria o comprovante da JVM por
caminho global e só conferia seu tamanho depois da leitura.

Agora ambos usam o helper `open_absolute_directory_nofollow()`
para abrir cada ancestral por `dir_fd` + `O_NOFOLLOW`, mantendo
os descritores abertos até o término da leitura. Os comprovantes
também são abertos com `O_NONBLOCK` para não travar em arquivos
especiais (como FIFO), recusando tipos não-regulares antes de
interpretar JSON. O leitor da JVM exige diretório pertencente
ao usuário e não-gravável por grupo/outros.

As duas leituras exigem identidade e estabilidade do inode:
`st_dev`, `st_ino`, `st_size`, `st_mtime_ns` e
`st_ctime_ns` precisam permanecer iguais do início ao fim.
Os testes negativos cobrem ancestrais simbólicos, FIFO,
alteração durante leitura e diretório JVM com escrita pública.

**Limite importante**: esses testes são contratuais e simulam
comprovantes. Os campos de cgroup e /proc não representam
observações independentes até uma VM Arch descartável realmente
executar e preservar suas evidências. O desafio externo da
PE-S1.24 continua obrigatório; o recibo permanece auto-relatado,
sem assinatura de uma autoridade independente. A PR permanece
Draft e o modo conjunto seccomp+cgroup não será desbloqueado.

## PE-S1.26 | Correlação dos quatro recibos de limpeza de escopo

A auditoria do validador `validate_native_acceptance_report()`
identificou que status gerais `verified=true`, `inactive` e
`dead` eram conferidos, mas a relação entre `load_state`,
`scope_collected` e `stop_request_accepted` não era obrigatória
em todos os quatro escopos. Um recibo com campos contraditórios
podia manter aparência de aprovação.

O validador agora verifica, nos escopos **inicial de cgroup**,
**descendente resistente a SIGTERM**, **probe seccomp** e
**Ghidra combinado**, o formato exato emitido pelo leitor systemd:
identidade do escopo, confirmado/inativo/morto/não-populado,
`load_state=not-found` se e somente se `scope_collected=true`,
e `stop_request_accepted` booleano. Aceita tanto `loaded`
inativo quanto `not-found` coletado, sem exigir que os
quatro `stop_request_accepted` sejam iguais: systemd pode
recolher um escopo naturalmente.

A execução combinada em Ghidra também precisa concordar entre
o resumo `scope_stop_accepted` e o comprovante de limpeza
`stop_request_accepted`. Testes sintéticos rejeitam alterações
individuais em todos os estágios, dados faltantes ou adicionais,
além de ambos os estados legítimos de systemd.

**Limites:** são verificações de coerência de evidências locais,
não uma assinatura ou observação independente do hipervisor.
Ainda falta executar os experimentos sob um kernel Arch nativo
em VM descartável. PR Draft; `main` sem merge, APK/OTA sem
publicação e `--require-seccomp --require-cgroup-limits` bloqueado.

## PE-S1.27 | Correlação das duas contagens de funções do Ghidra

A aceitação nativa usa a **mesma amostra PE sintética**, o script
`NegrescoFunctionInventory.java` e a release Ghidra 12.2 pinada
em dois testes independentes: execução standalone em Bubblewrap/cgroup
e execução experimental conjunta Bubblewrap/cgroup/seccomp.

Antes desta revisão, o recibo podia conter
`ghidra.ghidra_functions=18` e
`arch_real_ghidra_with_both.ghidra_functions_discovered=19`
com ambas as etapas alegando `PASS`, pois cada contagem era validada
isoladamente. A execução nativa `validate_real_ghidra()` e o
verificador final `validate_native_acceptance_report()` agora
exigem **contagens iguais e inteiras positivas** para os dois
inventários. Um descompilador pode não conseguir descompilar
todas as funções; exige-se apenas
`1 <= decompiled_functions <= ghidra_functions_discovered`.

Os novos testes verificam adulterações no recibo, ausência,
tipos errados e recusa *antes* de produzir a aprovação nativa.
Aceitam as duas contagens correspondentes com descompilação parcial.
São apenas contratos do relatório sintético: não substituem
a homologação em uma VM Arch descartável com kernel próprio.

PR #47 segue Draft, sem merge na `main`, publicação APK/OTA ou
ativação do executor principal seccomp+cgroups.

## PE-S1.28 | Bloqueio de recibos stdout de kernel contraditórios

A auditoria detectou que dois verificadores selecionavam somente
recibos positivos do stdout: `corroborate_guard_receipt()`
buscava apenas `cgroup_verification=passed` e
`baseline_from_scope_receipts()` apenas
`scope_seccomp_guard=passed` com o escopo esperado. Uma mesma
saída podia conter um registro `PASS` acompanhado de outro
`FAILED` ou de outro escopo e ainda assim ser aceita.

Agora os verificadores exigem **exatamente uma declaração** da
respectiva categoria no conjunto de registros; declarações
contraditórias, duplicadas, de outro escopo, status não-PASS,
campos extras/ausentes e tipos inválidos causam recusa fechada.
Mensagens de diagnóstico que não alegam ser comprovantes de
segurança são permitidas. A prova privada 0600 continua
obrigatória, assim como a concordância exata de quotas e
o aumento dos filtros na própria JVM.

Os testes de regressão cobrem múltiplas declarações contraditórias,
ambas as ordens dos registros e os contratos corretos. **Isto
verifica coerência das declarações locais, não autentica stdout
nem comprova uma VM Arch independente.** PR #47 continua Draft,
sem merge na main, sem APK/OTA publicado e sem ativação do
modo conjunto no executor principal.

## PE-S1.29 | Esquema exato dos campos de prova, sem afirmações extras

O validador `validate_native_acceptance_report()` verificava
conteúdo e tipos de campos conhecidos, mas ainda aceitava
propriedades adicionais em objetos internos do relatório.
Assim era possível acrescentar `independent_kernel_attestation=true`
ou outro status inventado a um relatório local e recalcular
seu hash SHA-256 sem provocar a recusa do revisor offline.

Agora existe um contrato fechado de campos para o relatório
principal, o preflight, as quotas, os resultados de cgroup/
descendentes, Ghidra, integridade da release, isolamento,
probe seccomp, execução combinada e prova da JVM. O sistema
recusa propriedades extras, ausentes e objetos com tipo errado
antes de reconhecer qualquer PASS. O preflight deve declarar
`real_cgroup_test_executed=false`, como faz o emissor real;
a prova concreta de cgroup é avaliada nos estágios posteriores.

Os testes de regressão adulteram cada categoria do relatório,
apresentam declarações extras com hashes recalculados
e tentam forjar o preflight. Não se trata de assinatura
digital nem de execução independente do kernel: continua sendo
apenas validação rigorosa da consistência de um recibo local.

O formato externo do recibo permanece v2 com desafio independente,
sem novas informações pessoais. A PR #47 permanece Draft,
sem merge, publicação APK/OTA ou liberação do executor
principal `--require-seccomp --require-cgroup-limits`.

## PE-S1.30 | Bloqueio de FIFO nos leitores de recibos e fontes

Foram identificados três caminhos em que um arquivo substituído por
FIFO poderia paralisar a validação: leitura offline do recibo
`_read_private_receipt()`, leitura offline de fonte `_read_source()`
e leitura de fonte no momento da geração por `build_receipt()`.
Esses caminhos já usavam descritores ancorados com `O_NOFOLLOW`
e conferiam `S_ISREG`, mas `open(O_RDONLY)` em FIFO pode bloquear
**antes** de `fstat()`, impossibilitando uma recusa rápida.

Agora cada abertura de arquivo de entrada usa também `O_NONBLOCK`.
Isso não altera a semântica de leitura dos arquivos regulares nem o
formato externo do recibo v2, mas permite rejeitar FIFO como tipo não
regular sem depender de alguém abrir sua ponta de escrita. Os três
novos testes criam FIFOs sem escritores e exigem recusa, incluindo
a ausência de recibo parcial pela rotina de gravação.

**Limites:** isso previne uma forma de travamento por arquivo
especial, não substitui timeout geral de operações no filesystem,
não autentica a origem do recibo e não prova medições do kernel em
VM Arch independente. A PR segue Draft; `main`, APK/OTA e
os controles combinados seccomp+cgroup permanecem intocados.

## PE-S1.31 | Limites plausíveis para cpu.max (CFS do kernel)

O parser de cgroup v2 já recusava quotas não inteiras, não positivas,
sem limite ou acima do orçamento de CPU (200%). Porém um comprovante
falso podia anunciar `cpu_period=1000000000000` microssegundos
ou `cpu_quota=1` microssegundo e passar na comparação de razão CPU.

Agora três camadas validam limites físicos do escalonador Linux:
`cpu_quota >= 1000` microssegundos e
`1000 <= cpu_period <= 1000000` microssegundos.
As constantes em `pe_resource_limits.py` são aplicadas à
leitura de `cpu.max` (`pe_cgroup_guard.py`), à prova privada
0600 (`pe_resource_evidence.py`) e à validação nativa/recibo
offline (`pe_arch_vm_evidence.py`). Permanecem limites de
memória, processos e até 200% de CPU, sem forçar os valores a
serem iguais entre escopos independentes.

Testes negativos cobrem números impossíveis em cada etapa.
Testes positivos preservam 1ms e 1s, extremos válidos do
kernel. Referência: https://kernel.org/doc/html/v6.16/scheduler/sched-bwc.html
(CFS: mínimo de quota/período de 1ms; período máximo de 1s).

A regra reforça coerência, mas não autentica o emissor nem
equivale a execução independente da VM Arch. PR Draft, sem
merge na main, sem APK/OTA e sem liberar o modo conjunto.


## PE-S1.32 | Snapshot canônico de recibos nativos

O relatório de aceitação era validado e hasheado, mas `build_receipt()`
embutia uma referência ao **dicionário original do chamador**. Como
estruturas aninhadas são mutáveis, alterações subsequentes poderiam
mudar os dados que seriam serializados para o recibo sem repetir a
validação nem atualizar o SHA-256. Isso causaria contradição entre
o conteúdo e a prova de integridade.

Agora o gerador serializa canonicamente o relatório **uma única vez**,
aplica o limite de tamanho, faz uma cópia JSON independente e valida
essa mesma cópia, que passa a ser usada no campo
`native_acceptance_report`. O hash continua comprometendo os bytes
da cópia canônica. Falhas de serialização recursiva e mutações durante
a serialização são recusadas com `AcceptanceReceiptError`; a revisão
offline converte `RecursionError` em `ReceiptReviewError` controlado.

Três testes exercitam a mutação do objeto original depois da geração,
a mutação durante a validação da cópia e um objeto com referência cíclica.
O formato de recibo v2, as quotas do CFS da PE-S1.31, o desafio externo
e os limites de privacidade continuam os mesmos.

**Importante:** esta cópia independente não torna o recibo assinado
ou imune a qualquer alteração por quem o controla; impede a mutação
**indireta pelo objeto de entrada** após a validação. Não prova
homologação independente do kernel em VM Arch descartável.
A PR continua Draft, sem merge na main, sem APK/OTA publicados
e sem liberar `--require-seccomp --require-cgroup-limits`.

## PE-S1.33 | Publicação atômica e durável de recibos locais

A gravação anterior criava o nome definitivo com
`O_CREAT|O_EXCL` **antes** de escrever e sincronizar os bytes.
Uma leitura concorrente podia observar o JSON incompleto, e a
falha após gravar podia deixar o nome definitivo visível
durante a limpeza.

O gravador usa agora um nome temporário aleatório e privado
`.negresco-receipt-*.tmp` no **mesmo diretório 0700**. Ele
grava o recibo completo com permissões 0600, faz
`flush + fsync` no arquivo e só então publica o inode pronto
por `os.link` sem sobrescrita. A ligação é atômica em
filesystem local: o nome definitivo aparece completo ou não
existe. O temporário é desvinculado, e o diretório é
sincronizado antes de emitir o comprovante de gravação.

Em erros de escrita, publicação ou `fsync`, o código não
emite sucesso e tenta remover apenas entradas que ainda
referenciem o inode criado por ele, respeitando a possibilidade
de outro escritor ter ocupado o destino. Cinco testes de
regressão cobrem ordem da sincronização, recusa por erro de
`os.link`, falha de `fsync` no arquivo ou diretório, e
corrida entre dois escritores com o mesmo nome definitivo.

**Limites:** interrupções por `SIGKILL`, perda de energia ou
falha do filesystem podem deixar arquivo temporário órfão;
isso não é um recibo concluído e nunca deve ser aceito como
prova final. A gravação atômica não autentica recibos, não
fornece assinatura, nem atesta execução de kernel em VM Arch.
PR segue Draft, sem merge ou publicação APK/OTA, e o modo
conjunto seccomp+cgroup segue bloqueado.

## PE-S1.34 | Inspeção e limpeza manual de estágios órfãos

A PE-S1.33 publica recibos completos de forma atômica, mas
uma interrupção `SIGKILL`/queda de energia ainda pode deixar
`.negresco-receipt-<32hex>.tmp` no diretório privado.

Nova ferramenta **offline, sem limpeza automática**:
`python3 tools/pe_receipt_stage_cleanup.py --private-directory /caminho/privado`
apenas lista os candidatos. Para remover, encerrar **todos os
escritores** e invocar explicitamente `--apply`. A idade mínima
é 24 horas, configurável por `--min-age-hours` (24–8760).
A inspeção exige diretório sem symlinks ancestrais, pertencente
ao usuário e inacessível a grupo/outros; examina até 4096
entradas para evitar varreduras ilimitadas.

A ferramenta considera somente nomes com token hexadecimal
de 128 bits, arquivos regulares `0600`, de proprietário local,
de tamanho limitado e com `st_mtime` e `st_ctime` antigos.
`st_nlink=1` é obrigatório: estágios vinculados a algum
nome definitivo não são removidos. Antes de `unlinkat`,
abre novamente o nome com `O_NOFOLLOW|O_NONBLOCK` e
confere inode e metadados contra os valores da inspeção.
Sincroniza o diretório após exclusões.

A limpeza continua conservadora: não é possível garantir,
com os primitivos expostos pelo Python, um `unlinkat`
condicional à identidade do inode; a mudança de nome por
outro processo **do mesmo UID** no instante entre a
última conferência e o `unlink` continua sendo uma corrida.
Portanto o modo `--apply` é manual, exige escritores parados
e não deve ser executado por tarefa periódica. Resultados
apenas sobre manutenção local, não atestação nativa ou prova
independente. PR permanece Draft, sem merge na main,
sem publicação APK/OTA e sem desbloqueio seccomp+cgroups.

## PE-S1.35 | Bloqueio cooperativo de diretório contra corrida de limpeza

A PE-S1.34 exige limpeza manual de estágios antigos, mas o
gravador e o limpador podiam abrir o mesmo diretório sem
coordenação. Uma limpeza `--apply` poderia examinar arquivos
enquanto um gravador ativo (ou travado) ainda os alterasse.

A PE-S1.35 acrescenta `fcntl.flock()` **não bloqueante** sobre
o descritor do próprio diretório privado, aberto com
`open_absolute_directory_nofollow()` e validado como
pertencente ao usuário e `0700`:

- O gravador de recibos obtém `LOCK_EX|LOCK_NB` antes de
  criar o estágio e o mantém até `fsync` do diretório.
- A limpeza com `--apply` obtém `LOCK_EX|LOCK_NB`
  durante toda a inspeção, revalidação e exclusão.
- A visualização usa `LOCK_SH|LOCK_NB`, permitindo
  consultas simultâneas, mas não durante a gravação.
- Bloqueio ocupado ou indisponível rejeita a operação
  imediatamente, sem ficar aguardando um processo travado.
  O fechamento do FD libera o bloqueio inclusive em erros.

Cinco novos testes verificam exclusão mútua,
prévia compartilhada, recusa sem efeitos colaterais,
e retenção do lock durante a publicação e durante a
remoção. O `flock` é **consultivo**: outro programa do
mesmo UID que o ignore ainda pode renomear/trocar
um arquivo entre verificação e `unlink`. A exigência
operacional de encerrar todos os escritores antes de
usar `--apply` **permanece**, e nenhuma limpeza é
executada automaticamente.

CI Arch testa contratos em contêiner, não em kernel de VM
Arch independente. Recibos continuam auto-relatados, sem
assinatura/atestado independente. PR Draft, sem merge
na `main`, sem publicação APK/OTA ou liberação conjunta
seccomp+cgroup.

## PE-S1.36 | Leitura estável dos recibos definitivos e das fontes

Uma revisão offline podia abrir um recibo enquanto o gravador
ainda aguardava `fsync(directory)` ou tentava reverter uma
publicação falhada, pois o leitor não participava do `flock`
adicionado na PE-S1.35. Um arquivo temporário com JSON completo
também podia ser passado ao revisor sob o nome
`.negresco-receipt-<token>.tmp`, apesar de **nunca** ter
sido efetivamente publicado.

O leitor agora exige `LOCK_SH|LOCK_NB` no mesmo diretório
privado `0700` antes de abrir o nome definitivo. Se o gravador
estiver com `LOCK_EX`, a revisão falha sem aguardar.
Nomes de estágio `.tmp` são recusados mesmo quando os bytes
contêm um JSON aparentemente válido.

Além de comparar `fstat()` do FD antes/depois, o revisor
faz `stat(..., follow_symlinks=False)` ancorado no diretório
para verificar se o nome ainda aponta para o **mesmo inode**
e se identidade, tamanho, permissões, proprietário, contagem
de links e marcas de tempo continuam coerentes. O mesmo
controle de nome estável é exigido de cada arquivo no manifesto
de fontes. Isso fecha o caso em que um arquivo é substituído
por outro inode com **bytes idênticos** durante a leitura,
mas o FD antigo permanece válido.

Cinco novos testes exercitam recusa de `.tmp`, bloqueio de
leitura quando o gravador está ativo, manutenção de lock
durante leitura e troca real de nomes de recibo e fonte
com conteúdo idêntico. Essas verificações continuam locais,
consultivas e não oferecem proteção contra um atacante do
mesmo UID que ignore os locks ou altere arquivos **depois**
da leitura. O recibo não é assinado e não representa
homologação nativa independente em VM Arch.

A PR permanece Draft; `main`, APK/OTA e executor conjunto
seccomp+cgroups permanecem sem alterações de publicação.
