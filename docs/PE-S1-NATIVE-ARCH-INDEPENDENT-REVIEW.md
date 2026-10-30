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


## PE-S1.50 | Política externa de chaves, suspensão, revogação e rotação

A PE-S1.49 verifica uma assinatura Ed25519 contra uma chave
previamente aprovada; por si só, esse teste **não conhece revogações
posteriores**. A PE-S1.50 exige uma decisão separada do revisor,
guardada em `reviewer-witness-trust-policy.json` (0600 em diretório
privado 0700). Essa política **não é fornecida como autoridade pelo
operador**: o revisor escolhe e guarda previamente seu SHA-256 e
seu número de revisão **em canal independente**.

O conteúdo exato do arquivo JSON tem estas chaves; os valores
ilustrativos abaixo devem ser substituídos pelos dados reais:

```json
{
  "schema": "negresco_pe_s1_50_reviewer_witness_trust_v1",
  "security_classification": "EXTERNAL_REVIEWER_PINNED_KEY_LIFECYCLE_NOT_VM_ATTESTATION",
  "witness_id": "revisor@example.invalid",
  "signature_namespace": "negresco-pe-s1-49-custody",
  "policy_revision": 1,
  "decision": "ACTIVE",
  "active_public_key_sha256": "SUBSTITUIR_PELO_SHA256_DOS_BYTES_DA_CHAVE_PUBLICA_SSH",
  "revoked_public_key_sha256": []
}
```

O identificador de chave `active_public_key_sha256` é
**SHA-256 dos bytes binários da chave pública Ed25519 em
formato wire SSH**, obtidos decodificando a última parte em
Base64 de `witness-allowed-signers`, **não** é o hash do
arquivo `witness-allowed-signers` completo. O arquivo
`witness-allowed-signers` continua com seu próprio SHA-256
retido externamente conforme PE-S1.49.

A política exige exatamente uma identidade, um namespace fixo,
um número inteiro positivo de revisão e uma lista ordenada,
sem duplicatas, de no máximo 64 chaves revogadas. Somente
`decision = "ACTIVE"` permite a conferência da assinatura.
`SUSPENDED`, `REVOKED` ou a presença da chave ativa na
lista de revogação **recusam** qualquer assinatura, inclusive
uma criptograficamente válida.

Ao realizar uma **rotação**, a testemunha gera **uma nova
chave privada fora da VM** e assina novamente a mesma declaração
de custódia com o namespace da PE-S1.49. O revisor verifica
separadamente a nova chave pública, retém sua identidade e
a cópia dos dados anteriores, eleva `policy_revision`,
coloca a chave antiga na lista de revogadas e atualiza o
SHA-256 externo da política. Nunca copiar ou publicar a
chave privada. Sem pin externo da política atual, **não
prosseguir com a revisão**.

```bash
python3 -B tools/pe_arch_vm_witness_trust_review.py \
  --private-dir "/caminho/privado" \
  --source-root "/mnt/checkout-readonly" \
  --expected-policy-sha256 "$PIN_SHA256_POLITICA_ATUAL" \
  --expected-policy-revision "$REVISAO_POLITICA_ATUAL" \
  --expected-custody-sha256 "$PIN_SHA256_DO_INDICE" \
  --expected-statement-sha256 "$PIN_SHA256_DECLARACAO" \
  --expected-signature-sha256 "$PIN_SHA256_ASSINATURA" \
  --expected-signers-sha256 "$PIN_SHA256_CHAVE_CONFIAVEL" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --expected-challenge "$REVIEWER_CHALLENGE" \
  --expected-witness-id "$WITNESS_ID" \
  --require-readonly-source-view
```

O novo comando realiza **primeiro** a validação da política
externa, inclusive revogação e chave ativa, e **somente
depois** reutiliza a validação criptográfica e o handoff
completo das etapas PE-S1.49/48/47. Relê a política e o
arquivo de chave após a verificação para detectar mudanças
persistentes. Mantém `independent_vm_attestation=false`
e `native_kernel_execution_independently_verified=false`.

**Atenção ao rollback:** o verificador detecta uma revisão
antiga somente se o revisor fornecer o **número e o SHA-256
atuais**. Não existe serviço remoto confiável de revogação,
CRL, OCSP, timestamp independente, prova de atualidade da
política, mecanismo de distribuição de revogação, autenticação
da VM nem detecção de um host malicioso. A PE-S1.49 permanece
como verificador legado de assinatura **sem política de ciclo
de vida**; para decisão de confiança atualizada, o protocolo
deve usar o novo comando PE-S1.50.

**CI:** testes sintéticos de recusa no Arch userspace e testes
reais com OpenSSH Ed25519 no Ubuntu, com chaves temporárias
e cenário de rotação. Nenhum signatário independente real foi
envolvido e nenhuma VM Arch nativa foi homologada. A PR segue
Draft, sem merge na main, APK/OTA ou liberação de binários externos.


## PE-S1.51 | Duplo controle de confiança: testemunha e revisor

A PE-S1.50 impede o uso de chaves de testemunha revogadas, mas
a política de autorização ainda poderia ser alterada por quem
controlasse apenas seus arquivos e pins locais. A PE-S1.51
acrescenta a **assinatura destacada da política exata** por um
**revisor separado**, num namespace SSH exclusivo:

- **Testemunha:** assina `witness-statement.json`, com
  `negresco-pe-s1-49-custody`; sua chave deve estar ativa na
  política PE-S1.50.
- **Revisor responsável pela política:** assina os bytes exatos
  de `reviewer-witness-trust-policy.json`, com o namespace
  `negresco-pe-s1-51-reviewer-trust-policy`. Usa chave privada
  Ed25519 distinta, controlada fora da VM e do operador.

O verificador exige **principal SSH e bytes públicos distintos**,
comparando as chaves binárias em formato SSH, não apenas nomes.
Exige o SHA-256 do arquivo de signatários do revisor,
da assinatura do revisor, da política e o número de revisão,
todos escolhidos/retidos por fonte sob controle independente.
Uma mesma chave com duas identidades é **rejeitada**.
Uma assinatura emitida para o namespace da testemunha também
não autoriza alterações na política.

O revisor cria `reviewer-policy-allowed-signers` em formato
OpenSSH, com **exatamente uma identidade**, e guarda
seu hash por canal próprio. A chave privada correspondente
**não** deve aparecer no pacote, na VM, no Git ou em logs:

```text
aprovador@example.invalid ssh-ed25519 SUBSTITUIR_PELA_CHAVE_PUBLICA_REAL
```

Assina a política corrente com sua chave privada, em máquina
independente e após verificar a lista de revogações:

```bash
ssh-keygen -Y sign \
  -f "/caminho/seguro/chave-privada-do-revisor" \
  -n negresco-pe-s1-51-reviewer-trust-policy \
  "/diretorio/privado/reviewer-witness-trust-policy.json"
```

Guarda a assinatura destacada resultante com nome fixo
`reviewer-witness-trust-policy.sig` e permissão 0600.
O arquivo `reviewer-policy-allowed-signers` também deve ser
0600 dentro do mesmo diretório 0700. Registrar os dois
SHA-256 **antes** da verificação por canal independente.
Os outros pins PE-S1.49/50 continuam obrigatórios.

Com a própria cópia do checkout em montagem real readonly
e os dois conjuntos de chaves autorizados previamente,
o revisor executa:

```bash
python3 -B tools/pe_arch_vm_dual_control_review.py \
  --private-dir "/diretorio/privado" \
  --source-root "/mnt/checkout-readonly" \
  --expected-policy-sha256 "$PIN_SHA256_POLITICA_ATUAL" \
  --expected-policy-revision "$REVISAO_POLITICA_ATUAL" \
  --expected-reviewer-signers-sha256 "$PIN_SHA256_CHAVE_REVISOR" \
  --expected-reviewer-signature-sha256 "$PIN_SHA256_ASSINATURA_REVISOR" \
  --expected-reviewer-id "$REVIEWER_ID" \
  --expected-custody-sha256 "$PIN_SHA256_DO_INDICE" \
  --expected-statement-sha256 "$PIN_SHA256_DECLARACAO_TESTEMUNHA" \
  --expected-signature-sha256 "$PIN_SHA256_ASSINATURA_TESTEMUNHA" \
  --expected-signers-sha256 "$PIN_SHA256_CHAVE_TESTEMUNHA" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --expected-challenge "$REVIEWER_CHALLENGE" \
  --expected-witness-id "$WITNESS_ID" \
  --require-readonly-source-view
```

A ordem é **falhar antes de confiar**: checar hash externo e
duas identidades e chaves distintas, conferir a assinatura real
do revisor sobre a política (namespace próprio), validar
a política ativa e então a assinatura da testemunha e os
recibos/fontes da PE-S1.47/48. Os arquivos relevantes são
relidos após a conferência para detectar substituição persistente.

Um resultado de sucesso,
`DUAL_CONTROL_CUSTODY_AUTHORIZATION_VERIFIED`, demonstra
somente *duas assinaturas de chaves distintas sobre dois
objetos distintos*. É preciso verificar por canais humanos
e institucionais separados quem detém cada chave. Uma
única pessoa ainda poderia controlar duas chaves diferentes
e passar na checagem criptográfica. O resultado mantém
`independent_reviewer_identity_verified=false` e
`independent_vm_attestation=false`.

**Limites:** não existe certificação de identidade de pessoas,
timestamp externo, revogação online, assinatura TPM/vTPM,
oráculo de hipervisor ou prova de kernel Arch. Os testes da
CI usam duas chaves temporárias criadas no runner Ubuntu,
e nenhuma testemunha independente real assina uma VM.
O verificador não executa programas Windows. Não liberar
seccomp+cgroups em arquivos externos, merge, APK ou OTA.

## PE-S1.52 | Coleta local de metadados do guest Arch

`tools/pe_arch_vm_observation.py` publica os arquivos
`guest-kernel-observation.txt` e `guest-cgroup-observation.txt`
necessários ao inventário PE-S1.48. O programa verifica antes de
qualquer coleta o commit completo escolhido pelo revisor, checkout
limpo, challenge externo e preflight de VM Arch nativa. Não inicia
Ghidra, executáveis Windows nem um scope cgroup.

O coletor limita as leituras a versão do kernel sem hostname,
PID 1, indicação local de virtualização, versão systemd, user
ControlGroup e controladores cgroup v2. Não lê variáveis de ambiente,
credenciais ou logs gerais. O diretório de destino deve existir,
pertencer ao usuário e ser 0700; os dois arquivos são 0600 e não
podem sobrescrever arquivos anteriores.

Exemplo, executado no checkout limpo em uma VM Arch descartável:

```bash
umask 077
mkdir -m 700 "$HOME/negresco-arch-observations"
python3 -B tools/pe_arch_vm_observation.py \
  --output-directory "$HOME/negresco-arch-observations" \
  --source-root "$PWD" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --reviewer-challenge "$REVIEWER_CHALLENGE"
```

O operador entrega esses dois arquivos junto ao recibo e à
saída de aceitação. O revisor recolhe os arquivos, calcula os
quatro hashes e cria seu próprio índice PE-S1.48; não usa hashes
fornecidos pelo operador como âncora de confiança. A CI tem
16 testes com dados sintéticos e exige que o host Ubuntu real
**recuse** o preflight, sem produzir arquivos.

O status `LOCAL_PRIVATE_OBSERVATIONS_PUBLISHED_NOT_ATTESTED`
indica **autodeclaração local, não atestação do kernel ou da VM**.
A coleta não verifica quotas efetivas, cleanup de descendentes
ou seccomp+cgroups juntos. A PR continua Draft, sem merge,
APK/OTA ou execução de binários externos.
