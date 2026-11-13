# PE-S2.24 | Handoff executável ao revisor externo (HOLD)

**STATUS:** roteiro de transferência, não homologação. Não foi disponibilizado, acessado ou validado qualquer host QEMU/libvirt independente nem VM Arch nativa. Não é um novo protocolo de assinaturas e não adiciona um caminho de PASS. PR #47 deve continuar Draft, sem merge, APK, OTA, execução de Windows PE desconhecido ou release.

## Objetivo e propriedade da prova

A PE-S2.23 já distingue consistência local do pacote assinado (V1/V2/V3, recibo e pins externos) de **sete fatos físicos/operacionais ainda não provados**. O que falta não se resolve com um novo JSON ou teste mockado: uma pessoa independente precisa controlar um host QEMU/libvirt, assistir ao boot da VM Arch descartável e coletar observações do kernel e do processo real durante a mesma sessão.

Este documento é um **ticket operacional para um revisor humano**, que deve primeiro ler [PE-S1-NATIVE-ARCH-INDEPENDENT-REVIEW.md](PE-S1-NATIVE-ARCH-INDEPENDENT-REVIEW.md), [PE-S2.21-REVIEWER-HOST-READINESS-HOLD.md](PE-S2.21-REVIEWER-HOST-READINESS-HOLD.md), [PE-S2.22-REVIEWER-EXTERNAL-PINS-HOLD.md](PE-S2.22-REVIEWER-EXTERNAL-PINS-HOLD.md) e [PE-S2.23-EXTERNAL-HOMOLOGATION-GAP-HOLD.md](PE-S2.23-EXTERNAL-HOMOLOGATION-GAP-HOLD.md). O protocolo longo S1 é a referência para os comandos S1.70/S1.71/S2.15/S2.17/V1-V3; este resumo não os substitui.

## Condições inegociáveis antes de iniciar

- O revisor controla e identifica o **host físico/virtualizado com KVM real**, a conta libvirt e o checkout confiável; sua independência é estabelecida **fora de banda**, não por flags do programa, SHA-256 ou saída de `virsh`.
- O revisor escolhe antecipadamente e guarda **fora do guest e fora do controle do operador**: SHA completo de 40 hex, domínio e UUID conferidos, challenge de 64 hex e session nonce de 64 hex **distintos**. Gerar cada valor aleatório localmente com `python3 -c 'import secrets; print(secrets.token_hex(32))'`. Não publicar esses valores nos comentários da PR.
- Utilizar VM Arch Linux **nativa, descartável, sem dados pessoais**, com systemd PID 1, cgroup v2, seccomp, Bubblewrap, JDK 25 e ZIP Ghidra 12.2 oficial autenticado. O PE Windows deve ser **sintético e tratado unicamente como entrada de análise, nunca executado**.
- Quatro locais separados e protegidos: `observer` 0700 vazio no início; `custody` 0700; `reviewer-pins` 0700 com JSON canônico 0600; checkout Git pinado sob montagem **realmente somente leitura** no momento da revisão. Pastas separadas não demonstram controle independente por si sós.
- Qualquer falha, ambiguidade, tentativa de relaxar isolamento, ausência de quota ou impossibilidade de provar identidade/custódia implica **STOP/HOLD**, sem ajustar a evidência para fazê-la passar.

## Sequência testemunhada pelo revisor

| Passo | Ambiente e ação | Saída aceitável e limite |
| --- | --- | --- |
| 0 | **Fora da VM:** revisor registra identidade, autorização, domínio/UUID, commit, challenge e nonce em custódia independente. Examina a procedência do host, VM e software. | Condição humana prévia; não há atestado automático. |
| 1 | **Host:** rodar o preflight S2.21 com `--probe-reviewer-host` na pasta `observer` vazia e pins do passo 0. Somente `virsh --readonly`; não executar guest agent, modificar VM ou produzir coleta. | `LOCAL_PE_S2_21_READONLY_LIBVIRT_HOST_CANDIDATE_HOLD`, **exit 2** mesmo quando consistente. Se `REJECTED_...`, parar. |
| 2 | **Host:** iniciar as capturas de provenance S1.70/S1.71, coleta S2.15 e amostra `before` S2.17; fixar hashes originais em custódia do revisor antes de liberar o trabalho. | Original e ordem documentados pelo revisor, não apenas counters crescentes. |
| 3 | **Guest:** verificar SHA Git limpo, VM gate e integridade byte a byte do ZIP Ghidra; executar `pe_arch_vm_validation.py` com checkout pinado, challenge, recibo exclusivo e trabalho **sintético**. | Observar efetivamente o PID do Ghidra, seu cgroup v2 e seccomp modo 2 **durante a mesma execução**; preservar kernel/systemd/journald/quota e `/work` limitados. |
| 4 | **Host + guest:** testemunhar encerramento do escopo e todos os descendentes; coletar `after` S2.17 com SHA de `before`. | Comprovar término independente, sem processo sobrevivente; vincular `before`/Ghidra/`after` à mesma sessão/UUID/challenge. |
| 5 | **Revisor:** autenticar pacote V1/V2/V3 e recibo pelo fluxo S2.19/S2.22, com pins gerados e SHA retido separadamente. Em seguida rodar S2.23 `--inspect-existing`. | Assinaturas/hashes válidos produzem **HOLD**, nunca PASS de VM. Falha local rejeita. |
| 6 | **Fora do software:** revisor compara e documenta as sete provas e seus limites, mantendo originais/recibos no seu próprio armazenamento privado. | Parecer humano separado; nenhuma flag de release é alterada pelo projeto. |

### Entrada exata do preflight do host

Executar **no host independente**, a partir do checkout pinado, como usuário sem root, após criar `observer` novo, vazio e 0700. Todos os valores devem ser escolhidos e conferidos pelo revisor:

```bash
umask 077
mkdir -m 700 -p "$HOME/pe-review/observer"
python3 -B tools/pe_arch_vm_s2_21_reviewer_host_readiness.py --observer-dir "$HOME/pe-review/observer" --domain "$REVIEWER_DOMAIN" --expected-domain-uuid "$REVIEWER_DOMAIN_UUID" --expected-source-commit "$REVIEWER_COMMIT" --reviewer-challenge "$REVIEWER_CHALLENGE" --reviewer-session-id "$REVIEWER_SESSION_ID" --probe-reviewer-host
```

**Atenção:** `exit 2` aqui é esperado tanto para `CANDIDATE_HOLD` como para `REJECTED`. Não automatizar continuação por código de saída. O revisor precisa ler o JSON e diferenciar os `status`. Uma identificação de candidato não autoriza executar a análise.

### Entrada exata do gate offline final

Apenas **depois de realmente coletar** o pacote em host/guest independentes, preservá-lo nas quatro pastas separadas e fixar o hash do JSON S2.22 fora de banda, executar no checkout do revisor:

```bash
python3 -B tools/pe_arch_vm_s2_23_external_gap_register.py --pin-file /private/reviewer-pins/reviewer-held-pins.json --observer-dir /private/observer --custody-dir /private/custody --native-receipt /private/custody/acceptance.json --source-root /private/readonly-source --expected-pin-bundle-sha256 "$REVIEWER_OUT_OF_BAND_SHA256" --inspect-existing
```

Mesmo em revisão local integralmente válida, o status é `HOLD_PE_S2_23_SIGNED_CUSTODY_VALID_EXTERNAL_VM_PROOFS_PENDING`, **exit 2**, e as sete classes continuam pendentes no software. `REJECTED_PE_S2_23_LOCAL_PACKAGE_INVALID_EXTERNAL_VM_HOLD` também retorna 2 e não deve ser confundido com HOLD de pacote válido.

## Complemento PE-S2.25: leitura do PID vivo durante Ghidra

A [observação local de PID/cgroup v2/seccomp PE-S2.25](PE-S2.25-READONLY-GUEST-PID-SNAPSHOT-HOLD.md) oferece uma leitura **opt-in e somente leitura** de um mesmo PID, antes/depois de consultar as quotas do kernel. Um revisor pode testemunhar esse diagnóstico **durante** a execução sintética, mas a saída permanece `HOLD`: não autentica que o processo é Ghidra, nem a VM, host, cronologia ou identidade do revisor. Não executar essa ferramenta depois que o processo terminou nem aceitá-la como evidência de journald ou cleanup. A issue #48 continua o bloqueio externo.

## Complemento PE-S2.26: armazenamento de journal sob limite real

O diagnóstico [PE-S2.26](PE-S2.26-JOURNALD-KERNEL-MOUNT-CAP-HOLD.md) inspeciona a capacidade do filesystem de uma montagem **tmpfs dedicada** em `/run/log/journal` (máximo 32 MiB) com leitura somente local. Ele **não valida** sozinho a política efetivamente carregada pelo serviço ou que o daemon gravou ali. A prova externa da lacuna de journald exige correlação humana de montagem real, daemon em execução e destino efetivo dos logs durante a sessão; a CI não tem essa VM. Um resultado local `HOLD` não conclui a homologação.

## Complemento PE-S2.27: namespace do processo journald

A PE-S2.26 observa `/proc/self/mountinfo`, o que não determina automaticamente a visão de montagem do daemon. O diagnóstico [PE-S2.27](PE-S2.27-JOURNALD-LIVE-MOUNT-NAMESPACE-HOLD.md) compara **o PID vivo do journald**, identidade do mount namespace, raiz e a montagem dedicada com o observador, com releitura para detectar trocas. Mesmo um resultado local consistente continua `HOLD`: não comprova escrita efetiva no tmpfs nem custódia independente do host/guest. O revisor deve testemunhar a sessão e confrontar a saída com logs e políticas efetivos, sem expor dados privados.

## Complemento PE-S2.31: leituras inteiras de PID e cotas

O observador local [PE-S2.25, reforçado pela PE-S2.31](PE-S2.31-PID-CGROUP-PROCFS-EOF-HOLD.md) exige EOF nas leituras limitadas de `/proc/PID/stat`, `status`, `cgroup` e de `memory.max`/`pids.max`/`cpu.max` para evitar prefixos aparentemente válidos que escondam dados contraditórios. **Esse diagnóstico local não prova origem da VM nem vínculo independente do PID com Ghidra**: o revisor deve testemunhar e correlacionar o processo real, cgroup e seccomp na mesma sessão sob custódia externa.

## Complemento PE-S2.32: consistência das cotas cgroup

O [snapshot local do PID PE-S2.32](PE-S2.32-CGROUP-QUOTA-CONSISTENCY-HOLD.md) agora lê duas vezes `memory.max`, `pids.max` e `cpu.max`, rejeitando valores diferentes, relaxamento de cotas ou mudança da identidade do processo. **Duas leituras locais não atestam a política durante toda a execução**. O revisor independente ainda deve verificar o PID Ghidra e os limites cgroup v2/seccomp simultaneamente, com evidência externa do início ao fim da sessão.

## Complemento PE-S2.33: caminhos de evidência sem symlinks intermediários

As leituras S2.25 de PID, seccomp e cotas cgroup v2 passaram a usar uma [travessia ancorada em descritores PE-S2.33](PE-S2.33-PID-CGROUP-ANCESTOR-NOFOLLOW-HOLD.md) para recusar links simbólicos tanto no arquivo final quanto em **todos os diretórios ancestrais**. Isso reforça o diagnóstico local, sem substituir a verificação independente da VM Arch, do PID real Ghidra, das cotas e da custódia externa.

## Complemento PE-S2.34: última identidade do PID após as cotas

O diagnóstico [PE-S2.34](PE-S2.34-FINAL-PID-IDENTITY-AFTER-QUOTA-HOLD.md) relê PID/starttime, UID/seccomp e cgroup após a **segunda** observação de `memory.max`, `pids.max` e `cpu.max`, evitando um resultado local favorável caso a identidade tenha mudado durante a última passagem de cotas. **Não é prova de continuidade ao longo da análise**; o revisor independente ainda precisa correlacionar PID e limites efetivos durante o Ghidra real com evidências BEFORE → WORK → AFTER.

## Complemento PE-S2.35: PID realmente vivo no momento observado

O diagnóstico [PE-S2.35](PE-S2.35-LIVE-PID-STATE-HOLD.md) recusa `/proc/PID/stat` com estado zumbi (`Z`), morto (`X/x`), parado (`T/t`) ou estado inesperado em qualquer uma das três verificações. Apenas `R/S/D` são aceitos como observações locais de tarefa ativa ou dormindo. Isso **não prova** que o PID pertence a Ghidra ou continua ativo durante toda a análise. O revisor deve testemunhar a identidade/executável e o estado do PID em simultâneo com as cotas cgroup v2 e o seccomp dentro da VM nativa, preservando a cadeia BEFORE→WORK→AFTER.

## Complemento PE-S2.36: identidade de processo fixada com pidfd

O diagnóstico local [PE-S2.36](PE-S2.36-PIDFD-IDENTITY-GUARD-HOLD.md) mantém `pidfd_open` fixado durante todas as leituras `/proc` e cotas cgroup, recusando saída do processo ou falta de suporte do kernel. Isso reduz corridas de reutilização de PID, mas **não valida a identidade do executável Ghidra** nem prova imposição contínua das cotas/seccomp. O revisor independente ainda deve testemunhar o PID e o processo real em conjunto com os controles no guest Arch nativo durante toda a sessão, sob cadeia BEFORE→WORK→AFTER.

## Complemento PE-S2.37: tipo do arquivo de evidência

O [diagnóstico local PE-S2.37](PE-S2.37-KERNEL-EVIDENCE-FILE-TYPE-HOLD.md) abre os arquivos de `/proc` e cotas cgroup com `O_NONBLOCK` e exige `fstat(...)` de **arquivo regular** antes da primeira leitura. A medida recusa FIFOs potencialmente bloqueantes e inodes inesperados. Isso **não autentica** o kernel/guest, o executável Ghidra ou a permanência do isolamento; a verificação independente de host/VM e execução correlacionada continua obrigatória.

## Complemento PE-S2.38: identidade do dispositivo KVM do host

O [preflight S2.21 endurecido PE-S2.38](PE-S2.38-KVM-DEVICE-IDENTITY-HOLD.md) recusa symlink no `/dev/kvm` e exige dispositivo de caractere major `10`, minor `232`. Esse teste negativo de falsos dispositivos é **apenas requisito local**, incapaz de comprovar propriedade do host, guest nativo, hipervisor real independente ou custódia do revisor.

## Matriz de entrega externa (todos os itens devem ter provas originais)

1. **Revisor independente:** autorização/identidade e custódia estabelecidas em canal distinto do operador, sem expor dados pessoais no repositório.
2. **Host e domínio:** administração efetiva do host QEMU/libvirt, identificação da máquina, KVM, UUID e consultas originais de domínio obtidas pelo revisor.
3. **Guest Arch real:** boot/console testemunhados, kernel e systemd reais, dispositivo VM separado de contêiner/CI, commit e ZIP Ghidra autenticados.
4. **Cgroup + seccomp simultâneos:** observar o mesmo PID/sessão do Ghidra com limites kernel efetivos cgroup v2 e `Seccomp: 2` durante análise do PE inerte.
5. **Quotas journald:** comprovar limites efetivos de filesystem/montagem e journald, não somente política declarada no arquivo de configuração.
6. **Cleanup:** registrar parada de unidade e ausência verificável de descendentes e processos sobreviventes após o trabalho, observada independentemente.
7. **Cronologia independente:** verificar `before` → execução Ghidra → `after` com domínio/UUID/challenge/nonce fixados e observação direta, não apenas contadores crescentes.

Cada prova deve mencionar **origem, horário/ordem, coletor, correlação da sessão, hash externo e limitações**. Não incluir credenciais, chaves privadas, arquivos Windows hostis, arquivos pessoais, nem logs indiscriminados no GitHub. Dados sensíveis permanecem na custódia do revisor; na issue pública registrar somente status, classes completas/incompletas e referências saneadas.

## Critério de encerramento e decisão

Este handoff está **preparado**, mas a tarefa de homologação **não está executada**. Para considerar uma revisão independente, o revisor precisa entregar um parecer separado, com as sete classes sustentadas e com evidências originais auditáveis. Mesmo isso exige avaliação técnica e decisão formal distinta para qualquer mudança de política; os verificadores atuais **nunca** autorizam merge, APK/OTA, PE externo ou lançamento automaticamente.

Até existir revisor, host e guest reais: **PE-S2.24 HANDOFF READY / EXTERNAL EXECUTION BLOCKED / PR #47 DRAFT / RELEASE HOLD**.
