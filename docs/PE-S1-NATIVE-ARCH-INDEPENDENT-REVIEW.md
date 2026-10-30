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
