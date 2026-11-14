# PE-S2.15 | Libvirt host-only readonly domstats sidecar, release HOLD

A tarefa PE-S2.15 adiciona uma ferramenta **operacional, opt-in e não destrutiva** para coletar o que o libvirt relata diretamente no host do revisor. Isto NÃO autentica o hipervisor nem transforma estatísticas da VM em prova de cgroup/seccomp/journald internos.

## Por que uma sidecar separada?

O pacote Ed25519 S1.63 tem um **schema de quatro observações**, fixado e revisado como v1. Acrescentar um quinto campo silenciosamente quebraria contratos e poderia dar aparência de atestado. PE-S2.15 portanto produz `reviewer-host-libvirt-domstats.txt` como arquivo **complementar fora do manifesto assinado S1.63**. O verificador offline exige o SHA-256 selecionado por canal externo, mas **não** o chama de assinatura. Em evolução futura, um manifesto v2 explicitamente versionado poderá transportar essa evidência se for formalmente auditado.

## Preparação pelo revisor, fora do guest

O revisor precisa possuir um host QEMU/libvirt separado, com domínio Arch já iniciado, diretório privado 0700, pins de commit, desafio, UUID, hashes exatos das capturas S1.70 e S1.71, e identificador de sessão escolhido externamente (64 hex minúsculos, não zero e não reutilizado). O revisor deve guardar esses valores por canal separado, antes da captura. A ferramenta **não cria VM, não gera segredos, não monta disco nem executa Ghidra**.

Modo padrão: valida entradas e retorna `PE_S2_15_HOST_RUNTIME_CAPTURE_NOT_STARTED`, sem consultar libvirt. Para coleta opt-in no **host independente**, passar `--capture-from-independent-host`. O script só consulta:

```text
virsh --readonly --connect qemu:///system --no-pkttyagent domuuid <domain>
virsh --readonly --connect qemu:///system --no-pkttyagent domstate <domain>
virsh --readonly --connect qemu:///system --no-pkttyagent domstats --raw --state --cpu-total <domain>
virsh --readonly --connect qemu:///system --no-pkttyagent domstate <domain>
virsh --readonly --connect qemu:///system --no-pkttyagent domuuid <domain>
```

O último programa só aparece com `--capture-from-independent-host`; a implementação usa argv fixo, sem shell, tempo e saída limitados. O parser aceita apenas um domínio, `state.state=1`, contador `cpu.time` positivo, campos inteiros canônicos sem repetição e nenhuma saída de outros domínios. Entre as consultas, a identidade UUID e estado devem permanecer estáveis. O arquivo é privado 0600, criado apenas uma vez por função de publicação exclusiva + fsync, com modo de recusa ao encontrar manifesto ou assinatura prévia. Nenhuma configuração do host é alterada.

Na verificação offline, `--review-existing --expected-record-sha256 <SHA pinado externamente>` reavalia todos os campos, SHA do arquivo completo, vínculo aos dois registros anteriores e nonce da sessão; mesmo texto válido retorna status **HOLD e código 2**. Erros também retornam 2, mas com status `REJECTED`.

## Cobertura e não alegações

A CI usa saídas **simuladas** de `virsh` e logs sintéticos S1.70/S1.71. Nunca se conecta a uma VM de usuário; não obtém evidência real de independência. `domstats` relata tempo de CPU do domínio e estado, não demonstra syscall/seccomp de um processo dentro do guest, enforcement do cgroup v2 ou política efetiva do journal. A procedência humana e física do host permanece não autenticada.

**Bloqueios inalterados:** PR #47 Draft, sem merge, APK, OTA ou análise de executáveis Windows desconhecidos. Antes de release, exigir atestado externo e auditável de host/guest, mesma execução, quota real de armazenamento, journald, cgroup v2+seccomp e cleanup.
