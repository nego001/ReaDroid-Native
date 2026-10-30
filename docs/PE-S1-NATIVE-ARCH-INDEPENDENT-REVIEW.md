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


## PE-S1.53 | Revisão estruturada das observações PE-S1.52

O inventário PE-S1.48 verifica o SHA-256 de arquivos privados, mas
trata os logs do guest como **dados opacos**. Isso é intencional
para manter compatibilidade com pacotes mais antigos. A PE-S1.53
adiciona um **verificador offline opcional e mais rigoroso**:
`tools/pe_arch_vm_observation_review.py`. Ele exige o formato
JSON estruturado que o coletor PE-S1.52 produz.

O revisor prepara uma cópia privada dos quatro arquivos do
pacote PE-S1.48, recalcula os hashes dos arquivos recebidos,
cria seu índice privado e guarda **fora do pacote** o SHA-256
do índice, commit Git completo e challenge estabelecidos antes
da execução. A revisão deve ocorrer num checkout readonly
verificado independentemente:

```bash
python3 -B tools/pe_arch_vm_observation_review.py \
  --private-dir "/caminho/privado/do-revisor" \
  --source-root "/mnt/checkout-readonly" \
  --expected-custody-sha256 "$PIN_SHA256_DO_INDICE" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --expected-challenge "$REVIEWER_CHALLENGE" \
  --require-readonly-source-view
```

O comando exige campos exatos, sem chaves JSON duplicadas,
NaN ou claims adicionais. Confere o mesmo commit, challenge,
classificação de autodeclaração e **mesmo timestamp declarado**
nos dois registros; exige `pid1_comm=systemd`, formato de
metadados bounded, controladores cgroup disponíveis
`cpu/memory/pids`, ausência de duplicatas e que os
controladores habilitados sejam um subconjunto dos disponíveis.
Um `cgroup_v2_root_subtree_control` vazio continua válido.

Uma divergência de lote ou uma alegação
`independent_vm_attestation=true` é rejeitada **mesmo que um
operador recalcule os hashes locais**. Após examinar esses
campos, o verificador exige o resultado integral PE-S1.48,
que por sua vez verifica o recibo PE-S1.47, challenge, fontes
e checkout Git. Relê índice e observações para detectar
mudanças persistentes ocorridas durante a revisão.

Sucesso: `LOCAL_GUEST_OBSERVATION_CUSTODY_CORRELATED_NOT_ATTESTED`,
com os SHA-256 e
`observation_pins_and_structure_correlated=true`,
mas **obrigatoriamente**
`operator_logs_authenticated=false`,
`native_kernel_execution_independently_verified=false` e
`independent_vm_attestation=false`.

Essa validação **não** compara cgroups efetivos no host nem
atesta uma VM. Uma mesma pessoa pode criar logs e inventário
aparentemente coerentes. Um horário coincidente entre dois
arquivos é só uma igualdade de strings, não carimbo de tempo
confiável. O operador deve passar pela validação nativa
independente PE-S1.45 e por uma testemunha externa real para
fundamentar qualquer homologação posterior.

A CI realiza **17 testes de regressão** com dados sintéticos,
mais três verificações no **Bubblewrap readonly real do Ubuntu**:
lote correto, pin externo errado e lote inconsistente mesmo
com inventário refeito. A CI não executa VM Arch nativa nem
Windows PE de terceiros. A PR segue Draft e sem publicação
APK/OTA ou execução conjunta de arquivos externos.


## PE-S1.54 | Revisão ponta a ponta assinada + observações estruturadas

A PE-S1.53 exige coerência estrutural dos dois logs autodeclarados
do guest. A PE-S1.51 exige assinaturas Ed25519 distintas da
testemunha (sobre custódia) e do revisor (sobre política de
chaves). **As duas verificações isoladas não eram uma aprovação
única do mesmo pacote.**

O novo `tools/pe_arch_vm_end_to_end_review.py` exige **ambas**
com exatamente os mesmos pins externos, commit e challenge,
revalidando a cadeia de recibos/fontes PE-S1.47/48 e a política
ativa PE-S1.50. Também confere a **cronologia declarada**:
a hora autodeclarada da coleta dos logs não pode anteceder a
hora autodeclarada de emissão do recibo de aceitação. Isso
é somente comparação de relógios informados pelo operador;
não prova hora real, identidade da VM ou sua procedência.

### Uso pelo revisor

O revisor deve obter todos os SHA-256, identidades de chaves,
revisão atual da política e challenge por **canal externo**
aos arquivos do operador e **antes** da revisão. A pasta privada
0700 contém os arquivos protegidos 0600 exigidos pelas etapas
PE-S1.48 a 51. A fonte deve estar em montagem readonly real:

```bash
python3 -B tools/pe_arch_vm_end_to_end_review.py \
  --private-dir "/caminho/privado/do-revisor" \
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

O programa abre somente os dez arquivos privados previamente
nomeados, exige hashes externos e campos sem claims indevidos,
valida o lote do guest e então verifica as duas assinaturas
com namespaces distintos. Depois lê novamente os arquivos
privados para detectar alterações persistentes. Não cria
assinaturas, não carrega chaves privadas, não executa PE e
não contata servidores externos. A comparação de revisões
de confiança só detecta rollback se o revisor conhecer os
pins mais recentes previamente.

Sucesso: `LOCAL_SIGNED_CUSTODY_AND_GUEST_LOGS_CORRELATED_NOT_VM_ATTESTED`
com `structured_guest_logs_consistent_with_custody=true`
e `separate_reviewer_and_witness_signatures_verified=true`.
Mesmo assim, `operator_clock_independently_verified=false`,
`witness_identity_independently_verified=false`,
`operator_logs_authenticated=false`,
`native_kernel_execution_independently_verified=false`
e `independent_vm_attestation=false`.

**Segurança:** o operador pode produzir dados sintéticos
internamente coerentes e controlar um relógio falso. Os
dois signatários podem não ser pessoas distintas se alguém
controlar suas duas chaves. A verificação é de **consistência
criptográfica e estrutural local**, não uma atestação independente
de hardware, hipervisor, kernel ou quotas/cgroups realmente
executados. Não há liberação de execução de PE externo,
merge, APK ou OTA.

A CI testa 13 cenários próprios, com chaves Ed25519 temporárias
reais **somente no Ubuntu** e testes de lógica no Arch userspace.
Nenhum deles comprova uma VM Arch independente.


## PE-S1.55 | Verificador completo dentro de montagem Bubblewrap somente leitura

A CI Ubuntu executa tests/pe_signed_readonly_real_ci.py como usuário
não-root, com o **mesmo perfil Bubblewrap** já usado pelo Ghidra. Ela monta
um checkout Git de teste e uma pasta privada de evidências em /audit/source
e /audit/private com --ro-bind; monta os módulos do revisor em
/audit/code também com --ro-bind. O verificador integral PE-S1.54 é
invocado **dentro** do namespace, com --require-readonly-source-view,
checagens reais do Git e duas verificações criptográficas com OpenSSH real.
A montagem readonly é conferida pelos flags efetivos do kernel, e não
inferida de permissões chmod ou de mocks.

O operador do teste constrói **apenas dados sintéticos** de supostos
eventos no guest e cria duas chaves Ed25519 novas e descartáveis. As
chaves privadas ficam fora de qualquer montagem da sandbox; somente
os arquivos de assinaturas e chaves **públicas** são montados. Os pins
SHA-256 de teste são calculados no processo externo antes de invocar a
sandbox. Isso não substitui um canal confiável de distribuição de pins
em uma auditoria real.

Cinco casos obrigatórios:

- Pacote íntegro, cronologia declarada coerente, ambas as assinaturas
  válidas, checkout limpo e todas as fontes readonly: **aceitar**.
- SHA-256 externo do índice errado: **recusar**.
- Log estruturado modificado, índice atualizado e declaração da
  testemunha não reassinada: **recusar**.
- Assinatura do aprovador modificada e seu SHA-256 atualizado:
  **recusar criptograficamente**.
- Fonte efetivamente montada com --bind de escrita, apesar do restante
  do pacote readonly: **recusar**.

O workflow exige cinco registros de caso e um resumo final, em JSON,
sem aceitar skip, ausência de OpenSSH, fallback fora do Bubblewrap
ou testes de assinatura mockados. Os testes de contrato PE-S1.54 continuam
na matriz Ubuntu/Arch userspace, separados dessa integração real.

**Limites:** este teste observa mounts e OpenSSH no runner **Ubuntu**;
o Git local de teste é produzido no próprio runner e as observações do
guest são sintéticas. Não há atestação de hardware, do kernel ou
hipervisor Arch, do horário real, da independência humana dos
signatários ou dos limites combinados seccomp+cgroups na VM Arch.
Não executar PE externo, não promover PR Draft, não mesclar na
main, não publicar APK ou OTA.


## PE-S1.56 | Resistencia a confusao de papeis e vazamento de chaves privadas

O mesmo smoke PE-S1.55 executa tres testes negativos adicionais no
Bubblewrap real, com OpenSSH e Git reais (sem mocks de assinatura ou
checkout). Nao sao avaliados executaveis Windows externos.

1. **Namespace errado com assinatura valida:** o aprovador assina novamente
   a politica usando o namespace reservado a testemunha, e o SHA-256
   externo da assinatura e atualizado. A verificacao deve recusar.
2. **Politica suspensa mas validamente assinada:** o campo `decision`
   vira `SUSPENDED`, o aprovador assina os novos bytes no namespace
   correto e os dois pins sao atualizados. Assinatura correta nao pode
   suplantar o ciclo de vida da politica.
3. **Uma chave para dois papeis:** os nomes do aprovador/testemunha
   continuam diferentes e cada objeto recebe uma assinatura Ed25519
   valida no namespace adequado, mas a chave publica e a mesma. A
   verificacao deve recusar a duplicacao binaria da chave.

Todos os oito cenarios (cinco anteriores e tres novos) exercitam ainda
uma **prova de isolamento real da sandbox**: as duas chaves privadas
descartaveis sao criadas no host de CI fora de qualquer montagem visivel
ao processo filho. O filho tenta abrir seus caminhos absolutos e exige
`FileNotFoundError`. A biblioteca de contas do processo deve identificar
exclusivamente um usuario sintético local; `/etc/passwd` e
`/etc/group` sinteticos sao montados readonly. Os caminhos
`/etc/shadow` e `/etc/ssh` do host nao devem estar presentes.

A verificacao exige que todas essas assercoes acontecam **dentro do
Bubblewrap** e que a CI rejeite qualquer registro ausente, sinal de
mock ou alteracao das garantias da montagem. A identidade sintetica
permite o funcionamento do OpenSSH sem revelar a base de usuarios do
runner.

**Escopo estrito:** trata-se de teste de isolamento no Ubuntu CI e
consistencia criptografica/estrutural de dados sinteticos. A ausencia
de dois arquivos de chave observada na sandbox nao prova resistencia
a fuga de kernel nem impossibilidade de exfiltracao por outros canais.
Duas chaves diferentes nao provam dois seres humanos distintos.
A VM Arch real independente, identidade do hipervisor, tempo confiavel,
seccomp+cgroups simultaneos e o comportamento de binarios hostis
continuam sem homologacao.


## PE-S1.57 | Release HOLD obrigatorio apos pacote assinado local

A integracao PE-S1.55/56 pode comprovar, no runner Ubuntu, um pacote
localmente consistente com **duas assinaturas reais Ed25519**, Git local
limpo e montagem Bubblewrap readonly real. Essa verificacao nao comprova
que algum kernel Arch nativo rodou numa VM independente.

O novo `tools/pe_arch_vm_s1_57_release_guard.py` exige que o revisor
apresente o **JSON de resultado local** gerado pelo PE-S1.54, armazenado
num arquivo privado 0600 de diretorio privado 0700, e os seguintes pins
externamente retidos: SHA256 desse resultado, SHA256 da custodia, commit
fonte completo, revisao da politica e os dois IDs distintos. O arquivo
nao pode ser symlink ou ter hardlinks. JSON duplicado, campos extras,
marcas de elevacao indevida, revisao incorreta e pins divergentes sao
recusados.

Mesmo o documento valido retorna **exit code 2** e:
`HOLD_PE_S1_57_INDEPENDENT_ARCH_VM_PROOF_MISSING`.
Nenhum objeto JSON fornecido pelo operador possui caminho para autorizar
execucao de Windows PE desconhecido ou publicar APK/OTA. O resultado
compara claims locais e registra as **faltas de prova independentes**;
ele NAO cria atestacao de kernel, assinatura de hardware ou um revisor.

### Exemplo de decisao no host do revisor

O resultado assinado deve primeiro ser gerado pelo verificador completo
PE-S1.54 **com as chaves publicas e SHA256 obtidos por canal externo**.
Guardar o JSON gerado em um arquivo privado; obter o hash por um canal
do revisor controlado separadamente. O comando abaixo **sempre recusa
promocao a homologacao nativa** (codigo 2), inclusive no caso local
consistente:

```bash
python3 -B tools/pe_arch_vm_s1_57_release_guard.py \
  --review-result "/privado/signed-review-result.json" \
  --expected-review-sha256 "$REVIEW_RESULT_SHA256" \
  --expected-source-commit "$REVIEWER_COMMIT" \
  --expected-custody-sha256 "$CUSTODY_SHA256" \
  --expected-policy-revision "$POLICY_REVISION" \
  --expected-reviewer-id "$REVIEWER_ID" \
  --expected-witness-id "$WITNESS_ID"
```

A CI Ubuntu testa o gate em 17 cenarios adversariais de contrato e,
adicionalmente, entrega ao gate o JSON emitido dentro do Bubblewrap
pelo teste real de duas assinaturas e exige `HOLD`. Depois falsifica
`independent_vm_attestation=true`, atualiza o hash externo de teste e
exige rejeicao estrutural mesmo com o pin recalculado.

### Prova ainda necessaria para uma homologacao futura

1. Revisao de um **operador independente** de uma VM Arch Linux descartavel,
   com hipervisor, configuracao e cadeia de origem observados fora da
   maquina controlada pelo operador dos logs.
2. Execucao manual e autenticada de
   `tools/pe_arch_vm_validation.py --reviewer-pinned-checkout` no
   guest, utilizando checkout/commit e challenge fixados antes por
   revisor externo, Ghidra 12.2 e ZIP previamente verificados e
   somente a fixture PE sintetica incluida no repositorio.
3. Observacao independente dos controles **simultaneos** no mesmo
   cgroup/scope: cotas efetivas, seccomp mode 2 no processo Ghidra,
   isolamento de rede e filesystem, limpeza de descendentes apos stop.
   O operador nao pode atestar a si proprio somente com JSON ou hashes.
4. Revisao separada do recibo e da cadeia de custodia assinada
   mantendo o escopo exato de quem/onde/quando mediu, sem inferir
   identidade humana a partir da simples posse de duas chaves.
5. Somente depois: projeto/revisao de um *novo* gate de atestacao
   com raizes de confianca externas explicitamente configuradas.
   O guard PE-S1.57 **nao** e esse gate.

**Politica:** a PR #47 continua Draft; nao mesclar nem liberar
execucao de PEs hostis, APK ou OTA com a evidência atual.


## PE-S1.58 | Preflight nativo seguro antes dos testes com cgroups

O novo `tools/pe_arch_vm_s1_58_preflight.py` é uma verificação
**exclusivamente local e de leitura**, a executar manualmente numa VM
Arch Linux **descartável e provida separadamente**. Ela não provisiona
uma VM, não inicializa Ghidra, não cria scope/cgroup, não gera
recibo, não analisa PE externo e não autoriza APK/OTA.

Antes de sequer validar o ambiente, exige commit completo e challenge
64-hex não-zero **obtidos previamente do revisor externo**. Também
exige o destino novo de recibo, fora do checkout e da instalação
Ghidra, num diretório existente 0700 do usuário. Não segue symlinks,
não sobrescreve um nome existente e verifica novamente o destino
após os checks de integridade.

O pré-voo chama os verificadores existentes para:
- confirmar Arch Linux com systemd e usuário não-root, rejeitando
  containers e runners Ubuntu; **isto é apenas uma observação local**;
- confirmar o checkout exato do próprio código, o commit externo,
  o manifesto rastreado, a ausência de alterações e de arquivos
  ignorados inesperados, antes e depois dos demais checks;
- confirmar Java 25 operacional e Ghidra 12.2 conforme o **ZIP oficial
  SHA-256 pinado**, comparando todos os arquivos extraídos e recusando
  symlinks e arquivos imprevistos.

### Execução manual: somente na VM descartável

O revisor precisa obter commit/challenge **por canal externo**, não
copiar valores de um recibo produzido pelo próprio operador. Use um
checkout dedicado de exato commit, um arquivo ZIP oficial do Ghidra
12.2 com hash pinado e um destino novo de recibo.

```bash
cd /caminho/do/checkout/rea-droid
install -d -m 700 "$HOME/negresco-arch-private"

python3 -B tools/pe_arch_vm_s1_58_preflight.py \
  --source-root "$PWD" \
  --ghidra-home "/opt/ghidra_12.2_PUBLIC" \
  --ghidra-archive "/opt/ghidra_12.2.zip" \
  --evidence-output "$HOME/negresco-arch-private/acceptance.json" \
  --expected-source-commit "$COMMIT_FIXADO_PELO_REVISOR" \
  --reviewer-challenge "$CHALLENGE_FIXADO_PELO_REVISOR"
```

Somente um resultado
`READY_LOCAL_PE_S1_58_NATIVE_ARCH_VM_PREFLIGHT_NOT_ATTESTED`
com **exit code 0** confirma a adequação dos *insumos locais*.
Não significa que cgroups/seccomp foram executados, que a VM é
autêntica ou que os signatários são independentes. Se falhar,
não execute as próximas fases; preserve o erro e investigue a
configuração da VM sem enfraquecer os gates.

Após o pré-voo e **somente com supervisão independente**, o teste
nativo já implementado pode ser invocado separadamente:

```bash
python3 -B tools/pe_arch_vm_validation.py \
  --ghidra-home "/opt/ghidra_12.2_PUBLIC" \
  --ghidra-archive "/opt/ghidra_12.2.zip" \
  --reviewer-pinned-checkout \
  --expected-source-commit "$COMMIT_FIXADO_PELO_REVISOR" \
  --reviewer-challenge "$CHALLENGE_FIXADO_PELO_REVISOR" \
  --evidence-output "$HOME/negresco-arch-private/acceptance.json"
```

Essa segunda operação já executa probes nativos e gera recibo, e
**não faz parte da PE-S1.58**. Ela deve ser realizada somente em
VM isolada, descartável e autorizada, nunca na máquina pessoal.
Se a execução nativa terminar localmente em PASS, o revisor ainda
precisa validar a origem da VM, os controles no kernel e a custódia
por um canal realmente independente.

A CI só executa os **18 testes de contrato** com mocks controlados
e um teste **real de rejeição do Ubuntu** com saída 2 e nenhum
recibo. Não há sucesso positivo de VM Arch no GitHub Actions
desta etapa. O gate de liberação PE-S1.57 permanece HOLD.
