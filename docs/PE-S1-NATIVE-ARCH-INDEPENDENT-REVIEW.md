# PE-S1.45 | Protocolo de revisão independente em VM Arch nativa

**ESTADO: PROCEDIMENTO PREPARADO. NENHUMA VM ARCH NATIVA FOI HOMOLOGADA.**
CI Ubuntu/Bubblewrap e Arch userspace em contêiner não demonstram kernel
Arch nem cotas systemd/cgroup v2 num hipervisor independente.

## Papéis separados

**Revisor independente:** escolhe e guarda, *antes* da execução e fora
da VM, o SHA Git completo de 40 hex e um desafio aleatório 64-hex.
O revisor decide independentemente como confiar no commit e no ZIP
oficial Ghidra. Um hash sozinho não autentica um servidor, pessoa ou VM.

**Operador:** prepara VM Arch **descartável**, com systemd, cgroup v2,
sessão de usuário real e sem contas, arquivos ou credenciais pessoais.
Executa exclusivamente o PE inerte de testes como dado para Ghidra.
Nunca usa root, contêiner, notebook pessoal ou VM com dados importantes.
Não desliga proteções do kernel para conseguir passar no teste.

**Revisor (depois):** coleta uma cópia do recibo, hash, stdout, versão
de kernel/systemd e logs; confere de uma máquina separada, com sua
própria fonte do commit previamente escolhido. Mesmo assim não
deve confundir recibo **auto-relatado e sem assinatura** com
atestação externa do kernel/hipervisor.

## 1. Antes da VM: fixar referências (revisor)

1. Inspecionar o commit e escolher o SHA completo de 40 caracteres da
   branch `feature/pe-bubblewrap-real-smoke` em `nego001/ReaDroid-Native`.
   Guardá-lo como `REVIEWER_COMMIT` em canal sob controle do revisor.
2. Gerar um desafio imprevisível em equipamento confiável:
   ```bash
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   ```
   Guardar fora da VM, depois transmitir como `REVIEWER_CHALLENGE`.
   Nunca reutilizar desafios artificiais dos testes automatizados.
3. Escolher Ghidra **12.2** ZIP oficial
   `ghidra_12.2_PUBLIC_20261016.zip`, conferir a origem e pinar SHA-256:
   `2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67`.

## 2. Na VM descartável: checkout e preflight (operador)

Instalar Python 3, Git, Bubblewrap, util-linux, systemd,
libseccomp, compilador mingw-w64 x86_64 e JDK 25, além de
Ghidra 12.2 (do ZIP previamente verificado). Assegurar sessão
user-systemd, runtime de usuário e cgroup v2. Não alterar sysctl
ou desativar isolamento para contornar uma recusa.

Receber `REVIEWER_COMMIT` e `REVIEWER_CHALLENGE` do revisor, depois:

```bash
git clone https://github.com/nego001/ReaDroid-Native.git
cd ReaDroid-Native
git fetch origin "$REVIEWER_COMMIT"
git switch --detach "$REVIEWER_COMMIT"

python3 -B tools/pe_arch_vm_checkout_pin.py \
  --source-root "$PWD" \
  --expected-commit "$REVIEWER_COMMIT"

python3 -B tools/pe_arch_vm_gate.py
```

Usar sempre `python3 -B` ou exportar `PYTHONDONTWRITEBYTECODE=1`
antes dos comandos Python deste checkout. O primeiro preflight
deve ocorrer numa árvore realmente limpa; caches `__pycache__` de
uma execução anterior são recusados, não ignorados. Se a árvore
já estiver suja, descartar a cópia e preparar outra, em vez
de apagar arquivos desconhecidos indiscriminadamente.

É obrigatório obter `LOCAL_GIT_CHECKOUT_PIN_MATCHED` e
`ARCH_VM_PREFLIGHT_PASSED`. Ambos são observações locais, não
atestados independentes. Recusar se o HEAD estiver errado,
arquivos do manifesto não estiverem rastreados ou a árvore
estiver suja. Se a VM gate falhar, **não iniciar** testes
de cgroups, descendentes ou Ghidra.

## 3. Aceitação nativa e publicação atômica (operador)

Depois de consentir explicitamente com testes sintéticos de
lifecycle em VM descartável, executar como **usuário comum**:

```bash
umask 077
mkdir -m 700 "$HOME/negresco-arch-vm-evidence"
export JAVA_HOME="/caminho/real/para/jdk-25"

python3 -B tools/pe_arch_vm_validation.py \
  --ghidra-home "/caminho/absoluto/ghidra_12.2_PUBLIC" \
  --ghidra-archive "/caminho/absoluto/ghidra_12.2_PUBLIC_20261016.zip" \
  --reviewer-pinned-checkout \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --reviewer-challenge "$REVIEWER_CHALLENGE" \
  --evidence-output "$HOME/negresco-arch-vm-evidence/acceptance.json" \
  --timeout-seconds 420 \
  > "$HOME/negresco-arch-vm-evidence/operator-run-output.json"

sha256sum "$HOME/negresco-arch-vm-evidence/acceptance.json"
```

**Fail-closed:** a nova flag `--reviewer-pinned-checkout` exige
também `--expected-source-commit`, `--reviewer-challenge` e
`--evidence-output`, e verifica o Git ANTES de qualquer execução
de Ghidra/cgroup. O recibo privado deve ter diretório 0700 e nome
novo, não sobrescrito. O relatório impresso traz
`local_source_checkout_pin` separado do conteúdo estrito do recibo
`v2` (não adiciona campos que falsificariam atestação).

Exigir evidência de Bubblewrap, seccomp real medido no JVM,
cotas systemd/cgroup privadas verificadas antes da execução,
limpeza de descendentes e escopo desocupado após a análise.
O programa Windows **não** deve ser executado. Falha ou ausência
de um desses itens resulta em **REJECTED_NOT_HOMOLOGATED**.
Não enviar arquivos de contas pessoais; salvar logs e o hash
do recibo numa fonte independente da VM.

## 4. Revisão por outra pessoa, fora da VM

O revisor escolhe seu próprio checkout fixado no commit externo,
em uma máquina separada, e copia o recibo para diretório de
sua propriedade, com permissão 0700 e arquivo 0600. Guardar o
hash calculado logo após recebimento **antes** da revisão e
confrontá-lo ao conteúdo recebido. Para máxima restrição,
revisar a fonte sob montagem *realmente readonly* e verificar
essa condição via `ST_RDONLY`; somente fazer `chmod 0444`
não é suficiente.

```bash
python3 -B tools/pe_arch_vm_checkout_pin.py \
  --source-root "/mnt/checkout-readonly" \
  --expected-commit "$REVIEWER_COMMIT"

python3 -B tools/pe_arch_vm_receipt_verify.py \
  --receipt "/caminho/privado/acceptance.json" \
  --source-root "/mnt/checkout-readonly" \
  --expected-challenge "$REVIEWER_CHALLENGE" \
  --expected-receipt-sha256 "$PIN_SHA256_EXTERNAMENTE_RETIDO" \
  --require-readonly-source-view
```

Conferir `LOCAL_RECEIPT_CONSISTENCY_VALIDATED`,
`external_receipt_sha256_pin_matched = true`,
`readonly_source_view_verified = true`, **e também**
`native_kernel_execution_independently_verified = false` e
`independent_vm_attestation = false`. Os dois últimos devem
continuar false: o recibo não é assinatura ou atestado confiável.

## 5. Decisão e limites

Registrar **PENDENTE/REPROVADO** se faltar fonte pinada,
challenge externo, ZIP Ghidra íntegro, VM descartável real,
seccomp, cotas efetivas cgroup, cleanup, análise sintética,
hash externo, recibo privado e checagem independente em
fonte readonly. **Mesmo com todos os PASS locais**, ainda
não há garantia de origem do hipervisor/kernel sem medição
ou testemunha genuinamente independente.

O Git helper usa Git local com variáveis `GIT_*` filtradas,
`fsmonitor` desativado, HEAD exato, status de arquivos e
checagem de todas as fontes do manifesto. Não valida
assinatura Git, não detecta arquivos ignorados e não protege
contra host adversário capaz de trocar dados após a leitura.
Não converte hash SHA-256 sem chave em prova de autoria.

**Conservar a PR Draft, sem merge na main, sem APK/OTA e sem
liberar seccomp+cgroups combinados para binários externos.**


## PE-S1.46 | Artifacts ignorados, tipos Git e revalidação pós-execução

O Git pode retornar `git status --porcelain=v1` vazio mesmo que
arquivos ignorados pela configuração de `.gitignore` tenham sido
inseridos. Para uma cópia de revisão **descartável e exclusiva**, isso
não comprova uma árvore sem artefatos auxiliares. A partir desta etapa,
o helper PE-S1.45 também consulta `git ls-files --others --ignored
--exclude-standard --directory --no-empty-directory` e **recusa
qualquer arquivo ou diretório ignorado não rastreado**.

Cada entrada de `SOURCE_FILES` também deve ser uma entrada Git
normal `100644` ou `100755` em estágio 0. Entradas `120000`
(symlink), `160000` (gitlink/submódulo), conflitos de índice e
diferenças no conjunto de nomes são recusadas, mesmo quando o HEAD
corresponde ao pin e o worktree parece limpo.

No modo `--reviewer-pinned-checkout`, o gate agora **verifica o
pin novamente após a aceitação nativa e antes de publicar o recibo
privado**. Alteração de fonte, artefato ignorado produzido por testes
ou divergência de identidade observável nesse momento impedem que
seja publicado um PASS. Para prevenir artefatos de bytecode gerados
pelo próprio script, usar `python3 -B` e um checkout novo e limpo
de propósito. Não apagar arquivos ignorados de checkout desconhecido
na tentativa de satisfazer a validação.

Os testes incluem casos de Git real com um arquivo ignorado
oculto ao `status --porcelain` e um symlink rastreado, bem como
recusa simulada de alterações depois da carga nativa. Isso é
uma proteção local contra diferenças **observáveis**; não garante
snapshot atômico, confiança na implementação do Git ou que o
operador/host é honesto. Não é homologação de VM Arch.


## PE-S1.47 | Conferência conjunta do recibo e da saída do operador

O revisor independente deve receber **dois arquivos** em vez de
confiar somente no recibo privado: `acceptance.json` (recibo v2)
e `operator-run-output.json` (saída JSON completa produzida pelo
CLI da aceitação nativa). O operador calcula os dois digests
separadamente:

```bash
sha256sum "$HOME/negresco-arch-vm-evidence/acceptance.json"
sha256sum "$HOME/negresco-arch-vm-evidence/operator-run-output.json"
```

O revisor guarda esses dois valores em um registro **fora da VM e
separado dos arquivos recebidos**, antes de abrir a entrega para
revisão. É essencial não confiar em SHA-256 informado dentro do
próprio JSON sob análise. Para a verificação, guardar os dois
arquivos como regulares de permissões 0600 num diretório privado
0700 sob controle do revisor, sem symlink nem hardlink adicional.

O novo verificador `tools/pe_arch_vm_handoff_review.py` verifica
ambos os digests externos, challenge prévio, commit Git externo,
a igualdade exata entre relatório impresso e relatório incluído
no recibo v2, os metadados de publicação do recibo e o pin de
checkout informado pelo operador. Também verifica o checkout
do revisor **antes e depois** das duas passagens de hashes do
manifesto. Se qualquer parte divergir, a entrega é recusada.

```bash
python3 -B tools/pe_arch_vm_handoff_review.py \
  --operator-output "/caminho/privado/operator-run-output.json" \
  --receipt "/caminho/privado/acceptance.json" \
  --source-root "/mnt/checkout-readonly" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --expected-challenge "$REVIEWER_CHALLENGE" \
  --expected-receipt-sha256 "$PIN_SHA256_RECIBO" \
  --expected-operator-sha256 "$PIN_SHA256_SAIDA_OPERADOR" \
  --require-readonly-source-view
```

O status `LOCAL_OPERATOR_HANDOFF_CORRELATED` significa apenas que
**essas duas observações locais são internamente coerentes**.
O resultado sempre mantém
`native_kernel_execution_independently_verified=false`,
`independent_vm_attestation=false` e
`host_or_git_authenticity_verified=false`. A verificação não
executa um PE Windows nem Ghidra e não prova o ambiente do operador.

A CI PE-S1.47 tem **12 testes de regressão sem VM** e três
cenários de integração com **Git e Bubblewrap reais no runner
Ubuntu** e fonte sintética: entrega coerente aceita, SHA externo
da saída errado recusado e relatório alterado recusado mesmo
quando seu novo SHA externo é informado. Nenhum desses testes
substitui prova de execução do kernel/cgroups numa VM Arch
independente. A PR continua Draft, sem merge/produção/APK/OTA.


## PE-S1.48 | Índice de custódia com quatro artefatos

A PE-S1.47 verifica recibo e saída JSON do operador. Esta etapa
adiciona um **inventário sob controle do revisor**, com SHA-256
de quatro arquivos privados de uma única revisão:

| Chave fixa | Arquivo | Proveniência |
|---|---|---|
| `receipt` | `acceptance.json` | Recibo auto-relatado v2 |
| `operator_output` | `operator-run-output.json` | Saída auto-relatada do operador |
| `guest_kernel_observation` | `guest-kernel-observation.txt` | Observação textual do operador, **não atestada** |
| `guest_cgroup_observation` | `guest-cgroup-observation.txt` | Observação textual do operador, **não atestada** |

O operador pode coletar observações inofensivas dentro da VM,
como `uname -a`, `systemctl --version` e
`systemctl --user show` das unidades usadas em sua execução,
mas os textos devem ser interpretados como **declarações do
operador**, não como prova de origem da VM. Não coletar segredos,
chaves, credenciais, arquivos pessoais, `journalctl` geral ou
registros de terceiros. Os arquivos de teste da CI usam somente
**texto sintético**, e não logs reais.

O revisor copia os quatro arquivos para uma pasta **privada
0700**, com todos os arquivos regulares **0600, sem symlinks,
hardlinks adicionais nem nomes alternativos**. Os arquivos
precisam ser não vazios e ter no máximo 1 MiB cada. Calcula
o SHA-256 de cada um separadamente. Um índice
`reviewer-custody-index.json` (também 0600, na mesma pasta)
é criado pelo **revisor**, com este esquema estrito:

```json
{
  "schema": "negresco_pe_s1_48_local_custody_index_v1",
  "security_classification": "UNSIGNED_REVIEWER_LOCAL_CUSTODY_NOT_VM_ATTESTATION",
  "reviewer_challenge": "DESAFIO_PREVIAMENTE_GUARDADO_64_HEX",
  "source_commit": "COMMIT_PREVIAMENTE_ESCOLHIDO_40_HEX",
  "artifacts": {
    "receipt": {
      "filename": "acceptance.json",
      "sha256": "SHA256_REAL_64_HEX"
    },
    "operator_output": {
      "filename": "operator-run-output.json",
      "sha256": "SHA256_REAL_64_HEX"
    },
    "guest_kernel_observation": {
      "filename": "guest-kernel-observation.txt",
      "sha256": "SHA256_REAL_64_HEX"
    },
    "guest_cgroup_observation": {
      "filename": "guest-cgroup-observation.txt",
      "sha256": "SHA256_REAL_64_HEX"
    }
  }
}
```

Os valores ilustrativos **não funcionam** até serem substituídos
por digests reais e referências do revisor. Depois de escrever o
índice, o revisor guarda seu SHA-256 em um local **separado da
entrega**, antes de rodar a verificação:

```bash
sha256sum "/diretorio/privado/reviewer-custody-index.json"
python3 -B tools/pe_arch_vm_custody_review.py \
  --private-dir "/diretorio/privado" \
  --source-root "/mnt/checkout-readonly" \
  --expected-custody-sha256 "$PIN_SHA256_DO_INDICE" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --expected-challenge "$REVIEWER_CHALLENGE" \
  --require-readonly-source-view
```

O verificador exige cinco arquivos seguros (índice + quatro
artefatos), esquema e digests exatos, invoca **o verificador
completo PE-S1.47**, compara o commit e challenge previamente
fixados e relê os cinco arquivos para detectar alterações
persistentes durante a revisão. Em sucesso, emite
`LOCAL_CUSTODY_PACKAGE_CORRELATED`, os hashes observados,
a hora **local do processo revisor** em UTC e as declarações
obrigatórias:

- `operator_kernel_log_authenticated=false`;
- `operator_cgroup_log_authenticated=false`;
- `external_signature_verified=false`;
- `native_kernel_execution_independently_verified=false`;
- `independent_vm_attestation=false`.

A hora observada não é um timestamp assinado. Os arquivos de
logs não são interpretados nem autenticados. O índice SHA-256
também **não é assinatura**, nem âncora de tempo independente.
A revisão não cria um snapshot atômico de filesystem nem prova
que os logs vieram de um kernel Arch; para isso ainda seria
necessária infraestrutura externa de medição e revisor
independente da VM e do host.

**Teste CI:** doze regressões sem executar VM/PE e três casos
reais com Git/Bubblewrap Ubuntu: pacote coerente, índice com
hash externo incorreto e observação de kernel adulterada após
o pin. Nada libera amostras externas, merge, APK/OTA ou modo
combinado seccomp+cgroups.


## PE-S1.49 | Assinatura destacada de uma testemunha da custódia

A assinatura desta etapa comprova **a posse da chave Ed25519
previamente confiada**, vinculada à declaração de custódia. Não
comprova origem do kernel, hipervisor, cgroups, autenticidade dos
logs do operador nem horário certificado. **A testemunha assina
uma declaração de recebimento/revisão da custódia, e não uma
atestação de VM Arch.**

O revisor deve estabelecer antecipadamente, por canal
independente do operador, a identidade da testemunha
(`WITNESS_ID`) e sua chave pública `ssh-ed25519`. A
testemunha deve guardar a **chave privada fora da VM, fora do
pacote do operador e fora do repositório Git**. Nenhum teste
da CI produz uma assinatura de uma testemunha real; as chaves
de teste são geradas e descartadas na execução do runner.

A testemunha examina os hashes e o inventário da PE-S1.48,
concorda com os limites da declaração e prepara um
`witness-statement.json` UTF-8 com os campos exatos:

```json
{
  "schema": "negresco_pe_s1_49_witness_custody_ack_v1",
  "security_classification": "SIGNED_CUSTODY_ACKNOWLEDGEMENT_NOT_VM_ATTESTATION",
  "witness_id": "revisor@example.invalid",
  "source_commit": "SUBSTITUIR_POR_SHA1_GIT_COMPLETO",
  "reviewer_challenge": "SUBSTITUIR_POR_CHALLENGE_64_HEX",
  "custody_index_sha256": "SUBSTITUIR_POR_SHA256_DO_INDICE",
  "acknowledgement_utc": "2026-10-29T12:00:00Z",
  "vm_attestation_claimed": false
}
```

**A data é exemplo**, não é prova de registro de horário. Todos
os placeholders devem ser substituídos por valores reais e
referências guardadas previamente. A testemunha assina **os
bytes exatos** do arquivo com OpenSSH (`ssh-keygen -Y`),
usando namespace próprio para impedir a reutilização de
assinatura de outra finalidade:

```bash
ssh-keygen -Y sign \
  -f "/caminho/seguro/chave-privada-da-testemunha" \
  -n negresco-pe-s1-49-custody \
  "/caminho/privado/witness-statement.json"
```

A assinatura destacada gerada pode ser copiada, pelo
revisor, para `witness-statement.sig` na pasta privada.
A chave pública aprovada **antes** da entrega fica em
`witness-allowed-signers`, em **uma única linha**:

```text
revisor@example.invalid ssh-ed25519 AAAA_CHAVE_PUBLICA_REAL
```

Esse exemplo **não é chave válida**. O revisor obtém a chave
por canal confiável, não do próprio arquivo do operador.
O formato aceito pela PE-S1.49 é um único principal e uma
única chave pública Ed25519, sem `*`, certificadora wildcard
ou múltiplos signatários. Os três arquivos de testemunha
são regulares 0600, sem symlinks e sem hardlinks adicionais,
numa pasta privada 0700 junto dos cinco arquivos da PE-S1.48.

O revisor conserva separadamente, antes da conferência,
os quatro SHA-256: índice PE-S1.48, declaração assinada,
assinatura destacada e chave de confiança. Executa:

```bash
python3 -B tools/pe_arch_vm_witness_review.py \
  --private-dir "/caminho/privado" \
  --source-root "/mnt/checkout-readonly" \
  --expected-custody-sha256 "$PIN_SHA256_DO_INDICE" \
  --expected-statement-sha256 "$PIN_SHA256_DECLARACAO" \
  --expected-signature-sha256 "$PIN_SHA256_ASSINATURA" \
  --expected-signers-sha256 "$PIN_SHA256_CHAVE_CONFIAVEL" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --expected-challenge "$REVIEWER_CHALLENGE" \
  --expected-witness-id "$WITNESS_ID" \
  --require-readonly-source-view
```

Sem OpenSSH disponível, assinatura inválida, namespace errado,
substituição de chave, alteração de qualquer SHA ou divergência
do índice, o verificador **recusa**, sem fallback silencioso.
O resultado positivo é
`SIGNED_CUSTODY_ACKNOWLEDGEMENT_VERIFIED`, com
`detached_witness_signature_verified=true` e
`trusted_witness_key_pin_matched=true`, mas ainda traz
`guest_logs_authenticated=false`,
`witness_time_independently_verified=false` e
`independent_vm_attestation=false`.

**Limites de ameaça:** a pessoa ou serviço que controla a chave
Ed25519 pode assinar qualquer conteúdo, inclusive um relato
enganoso. Uma assinatura válida prova a chave usada, não
boa-fé ou a realidade dos dados. O pin da chave deve ser
externo e registrado antes de qualquer dado do operador.
Não há prova de tempo, revogação automática, assinatura de
hipervisor, TPM, VTPM ou prova de kernel Arch. A chave
**privada nunca deve ser anexada à PR, à VM ou aos logs**.

A CI executa testes criptográficos reais com chaves Ed25519
**descartáveis e sintéticas** no runner Ubuntu e regressões
de recusa. Não foi coletada uma assinatura de testemunha
independente nem executada uma VM Arch nativa. Sem merge,
APK/OTA e sem liberar o executor combinado.
