# PE-S2.21 | Pré-verificação do host do revisor independente (HOLD)

**Estado:** procedimento e testes automatizados preparados; **nenhum host QEMU/libvirt independente ou VM Arch nativa foi acessado nesta CI**. PR #47 permanece Draft, sem merge, APK, OTA ou release.

## Complemento PE-S2.38: /dev/kvm precisa ser o dispositivo KVM

O [preflight endurecido PE-S2.38](PE-S2.38-KVM-DEVICE-IDENTITY-HOLD.md) exige um inode de caráter real de `/dev/kvm` com major `10` e minor `232` e não segue links simbólicos na última componente. Outros dispositivos de caráter, como `/dev/null`, não constituem evidência do KVM. **Essa conferência local não prova controle independente do host.**

## Complemento PE-S2.39: consulta à API KVM sem criar máquinas virtuais

A [PE-S2.39](PE-S2.39-READONLY-KVM-API-PROBE-HOLD.md) acrescenta a verificação do próprio descritor de `/dev/kvm`: abrir somente leitura com `O_NOFOLLOW`, comparar `lstat` e `fstat` para recusar substituição do inode e consultar apenas `KVM_GET_API_VERSION` (resposta inteira 12). Qualquer erro de abertura, metadados ou ioctl impede a consulta ao libvirt. **Não autentica propriedade independente do host** e não chama `KVM_CREATE_VM`.

## O problema prático que esta etapa resolve

A PE-S2.20 já executa a revisão offline real das assinaturas V1/V2/V3, do recibo sintético e do Git sobre montagens realmente somente leitura. Isso **não identifica nem autentica a máquina que criou os registros**. Antes da primeira coleta real, era necessário garantir ao menos que o ambiente local não é um runner conhecido, contêiner, shell root, libvirt errado ou pasta com amostras anteriores.

`tools/pe_arch_vm_s2_21_reviewer_host_readiness.py` oferece uma **pré-verificação local, de leitura apenas e opt-in**, executável pelo revisor diretamente no seu próprio host QEMU/libvirt, **não dentro da VM Arch**.

- Sem `--probe-reviewer-host`: valida somente parâmetros e diretório 0700; **não consulta KVM, executáveis ou libvirt**, não cria arquivos e devolve `PE_S2_21_INDEPENDENT_HOST_PREFLIGHT_NOT_STARTED` (código 0).
- Com `--probe-reviewer-host`: exige Linux sem root; rejeita marcadores conhecidos de CI e contêiner; exige `/dev/kvm` como dispositivo de caractere 10:232 com inode pinado e resposta da API KVM 12; exige diretório do observador **vazio**, exclusivo e 0700; consulta `systemd-detect-virt --container --quiet` via binário confiável; exige um `virsh` de sistema confiável. Usa **somente** o `virsh --readonly --connect qemu:///system --no-pkttyagent` já restringido pela S1.70, com limites de tempo/bytes e comandos `domuuid`, `domstate`, `dominfo`, e repete UUID/estado depois.
- Exige commit Git completo, UUID, domínio simples, desafio e ID da sessão de 64 hex distintos e não obviamente placeholders. **Não confirma que são imprevisíveis**, tampouco a identidade, custódia ou independência do host. Marcadores de CI/contêiner são verificações locais passíveis de falsificação.
- Se todos os testes locais passam: `LOCAL_PE_S2_21_READONLY_LIBVIRT_HOST_CANDIDATE_HOLD`, **código 2**. Isso significa *candidato apto para iniciar a coleta*, jamais homologado. Se falhar: `REJECTED_PE_S2_21_REVIEWER_HOST_NOT_PROVEN`, **código 2**, sem consulta ao guest nem escrita. A decisão depende do **campo status**, não somente do código.

## Procedimento para o revisor real, em host independente

A pessoa responsável deve confirmar **fora de banda** a custódia do host, a origem do checkout, a procedência do hipervisor, a identidade do revisor e a separação entre o host QEMU/libvirt e a VM Arch descartável. O software **não consegue garantir isso por detectar `/dev/kvm` ou executar `virsh`**.

1. Preparar no host do revisor um checkout limpo no SHA exato escolhido previamente; usar somente uma **VM Arch descartável sem dados pessoais** e binários sintéticos. Confirmar previamente o ZIP oficial de Ghidra 12.2 e SHA-256 e os requisitos de kernel, systemd, cgroup v2, seccomp, journald e /work. Não executar Windows PE desconhecido.
2. Em canal que o operador da VM não controla, escolher um commit de 40 hex e dois valores aleatórios **distintos**, um `REVIEWER_CHALLENGE` e um `REVIEWER_SESSION_ID`, ambos de 64 hex. Criar com `python3 -c 'import secrets; print(secrets.token_hex(32))'` **duas vezes** no host do revisor, não em uma execução do GitHub Actions.
3. Num diretório de evidências recém-criado **fora do checkout** (sem arquivos anteriores), executar como usuário comum:

```bash
umask 077
mkdir -m 700 -p "$HOME/pe-review/observer"
python3 -B tools/pe_arch_vm_s2_21_reviewer_host_readiness.py \
  --observer-dir "$HOME/pe-review/observer" \
  --domain "$REVIEWER_DOMAIN" \
  --expected-domain-uuid "$REVIEWER_DOMAIN_UUID" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --reviewer-challenge "$REVIEWER_CHALLENGE" \
  --reviewer-session-id "$REVIEWER_SESSION_ID" \
  --probe-reviewer-host
```

4. O resultado **`LOCAL_PE_S2_21_READONLY_LIBVIRT_HOST_CANDIDATE_HOLD` não inicia a análise**. Só prosseguir após o revisor inspecionar e assumir responsabilidade explícita pela independência real. Se o teste recusar, **não** forçar `virsh` gravável, desabilitar namespaces, adulterar /dev/kvm ou trocar evidências para obter um falso PASS.
5. Com a custódia e segurança estabelecidas externamente, seguir os comandos existentes da [revisão independente](PE-S1-NATIVE-ARCH-INDEPENDENT-REVIEW.md), S1.70 para primeiro registro host, S1.71 para autodeclaração OS do guest, S2.15 para `domstats`, S2.17 para `before`. O revisor preserva cada SHA-256 em canal independente **antes** de iniciar a análise sintética por S1.66 no guest.
6. Apenas após a análise controlada e verificações de cgroup/descendentes/segurança, recolher `after` por S2.17 (exigindo SHA do `before`). Gerar as quatro observações S1.63, autenticar V1, depois V2 e depois V3, sem alterar o formato antigo. Confrontar V3 com o **recibo real** pelo S2.19, usando checkout genuinamente montado como somente leitura e todos os hashes externos. Cada revisão com status positivo permanece **HOLD**.
7. Documentar manualmente se o processo realmente validou, por observação independente, os limites de cgroup v2, seccomp do processo Ghidra, cotas efetivas de journald, continuidade da montagem /work e parada dos descendentes. Qualquer prova ausente ou origem do host não verificável mantém **HOLD**. O software não declara `independent_vm_attestation=true` sozinho.

## Escopo verificável em CI

Testes em `tests/test_pe_arch_vm_s2_21_reviewer_host_readiness.py` usam **virsh simulado**, sem comunicação com hipervisor; verificam modo padrão sem execução, falha para CI, contêiner, root, KVM inexistente, diretório não vazio, UUID/estado trocados, `dominfo` inconsistente e retorno **HOLD**. A CI Ubuntu executa ainda um controle negativo real, com `GITHUB_ACTIONS=true`: o host do runner deve ser recusado **antes de qualquer virsh e sem criar arquivos**. Arch userspace também executa somente os testes simulados, não uma VM física.

**Critério de conclusão externa:** evidências realmente coletadas por pessoa independente, sob host e VM separados, provenientes do mesmo commit/desafio/sessão, com logs de cgroup/seccomp/journald/cleanup e revisão humana. Esta etapa **não** substitui esse trabalho; nenhuma assinatura nem resultado de CI autoriza merge, release, APK ou OTA.
