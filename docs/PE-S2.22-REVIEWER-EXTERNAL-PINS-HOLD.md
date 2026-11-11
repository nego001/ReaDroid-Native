# PE-S2.22 | Pacote de hashes mantido pelo revisor + cadeia assinada, sempre HOLD

**Estado:** Implementação e ensaio de CI com registros sintéticos. **Não existe homologação independente da VM Arch nem captura real de um host QEMU/libvirt externo neste commit.** PR #47 permanece Draft, sem merge, APK, OTA, execução de PE desconhecido ou autorização de lançamento.

## Qual problema resolve

A PE-S2.19 aceita hashes separados por parâmetros. Mesmo quando as assinaturas V1/V2/V3 e o recibo local são consistentes, alguém pode preencher os parâmetros diretamente com hashes fornecidos pelo operador da VM. Isso **não comprova que o revisor reteve os valores fora do ambiente do operador**.

A PE-S2.22 oferece um arquivo **externo, privado, imutável durante a revisão**, com todos os hashes esperados, e exige que o revisor retenha seu SHA-256 separadamente. O novo `tools/pe_arch_vm_s2_22_external_reviewer_pins.py` NÃO cria ou assina chaves, não altera os manifestos V1/V2/V3, não consulta libvirt, nem executa Ghidra ou Windows PE. Ele apenas executa a revisão S2.19 sobre hashes recebidos do revisor e os confere novamente no fim.

**Aviso técnico:** diretórios diferentes e um SHA informado pelo revisor **não atestam a pessoa**, a propriedade física do host ou a origem dos dados. Uma conta mal-intencionada pode fabricar um conjunto autoconsistente. O revisor precisa escolher o SHA e verificar a custódia **fora da máquina do operador**.

## Formato estrito do arquivo do revisor

Criar uma pasta privada 0700 **separada do checkout Git, observador e recibo do guest**, por exemplo `/private/reviewer-pins`. O nome do arquivo é exatamente `reviewer-held-pins.json`, regular, 0600, sem symlinks ou hardlinks. O formato é um JSON **ASCII canônico**, sem campos extras, sem chaves duplicadas, com uma linha final. A estrutura é:

```json
{
  "schema": "negresco_pe_s2_22_external_reviewer_pins_v1",
  "security_classification": "REVIEWER_HELD_HASH_REFERENCES_NOT_VM_ATTESTATION",
  "pins": {
    "...": "Todos os 23 campos expected_* da PE-S2.18, mais os 3 hashes da PE-S2.19"
  },
  "independent_vm_attestation": false,
  "release_authorized": false
}
```

A visualização acima é ilustrativa, não é um arquivo válido. A ordem e espaçamento canônicos são definidos por `_canonical` no módulo S2.22. O revisor deve preencher somente os 26 nomes exatos já definidos em `pe_arch_vm_s2_18_signed_host_pair.PINS` mais `expected_v3_manifest_sha256`, `expected_v3_signature_sha256` e `expected_native_receipt_sha256`. Os valores de autenticação precisam vir da cadeia assinada e dos registros mantidos pelo revisor, **nunca de um arquivo recomposto pelo operador para superar uma recusa**.

O SHA-256 do arquivo precisa ser **retido separadamente** antes da revisão. O arquivo não deve ficar sob as pastas com evidências que o operador possa substituir. Uma cópia em diretório separado no mesmo computador apenas melhora a organização e a detecção de alterações, **não prova independência de custódia**.

## Fluxo real: revisor externo

1. Separadamente e antes da sessão, escolher e registrar o commit, desafio, nonce de sessão, domínio e UUID usando PE-S2.21; manter o desafio e os hashes em custódia controlada pelo revisor.
2. Seguir a sequência host S1.70/S1.71 e domstats S2.15/S2.17; executar somente a análise sintética permitida no guest descartável e registrar o **recibo nativo real** e SHA correspondente. Coletar logs de cgroup v2+seccomp, journald, /work e descendentes. Essa etapa requer o host/VM independentes e **não foi realizada pela CI**.
3. Após autenticar os manifests V1, V2 e V3 com as chaves previstas, construir o JSON S2.22 a partir dos SHA-256 e identidades já fixados *fora de banda*. A própria ferramenta S2.22 **não gera esse arquivo, não coleta pins de fontes não confiáveis e não toca em chaves privadas**.
4. Montar o checkout em modo somente leitura. O recibo deve existir diretamente dentro da pasta 0700 de custódia, e o diretório 0700 dos pins deve estar separado do checkout, observador e recibo. Rodar:

```bash
python3 -B tools/pe_arch_vm_s2_22_external_reviewer_pins.py \
  --pin-file /private/reviewer-pins/reviewer-held-pins.json \
  --observer-dir /private/observer \
  --custody-dir /private/custody \
  --native-receipt /private/custody/acceptance.json \
  --source-root /private/readonly-source \
  --expected-pin-bundle-sha256 "$REVIEWER_OUT_OF_BAND_SHA256" \
  --review-existing
```

5. **Mesmo um sucesso retorna código 2 e `LOCAL_PE_S2_22_SEPARATE_PIN_BUNDLE_AND_SIGNED_CHAIN_REVIEWED_HOLD`**, jamais `RELEASE_AUTHORIZED`. Uma recusa retorna `REJECTED_PE_S2_22_REVIEWER_HELD_PINS_OR_CHAIN`, também código 2. Sem `--review-existing` a ferramenta apresenta apenas um plano, código 0, sem acessar arquivos.
6. Uma validação positiva comprova **consistência local dos bytes** e assinatura válida contra as chaves fornecidas, não autoria/independência física. Exigir ainda o parecer humano e as provas reais do kernel, hipervisor, quotas e encerramento de processos antes de sequer considerar uma revisão de segurança.

## Testes

- `tests/test_pe_arch_vm_s2_22_external_reviewer_pins.py`: 15 testes em Ubuntu e Arch userspace. Assina V1/V2/V3 com chaves Ed25519 descartáveis reais, simula apenas o verificador local Git/recibo nas verificações unitárias, rejeita pins fora da pasta, symlinks, modo 0644, hashes alterados, JSON não canônico/duplicado e falsos flags de release.
- Amplia a CI de Bubblewrap da PE-S2.20: **montagem realmente readonly de um diretório separado de pins**, hash externo passado via argumento, Git real + recibo sintético, assinatura real V1/V2/V3 e verificadores reais sem mocks no subprocesso isolado. Cinco cenários: pacote correto, fonte realmente gravável, fonte readonly adulterada, hash V3 falso com bundle refeito e hash do próprio bundle incorreto. Os resultados só podem sinalizar HOLD.
- Todos os dados de libvirt continuam **SIMULADOS** e o recibo de aceitação é **SINTÉTICO**. O container Arch userspace não é uma VM Arch nativa. Uma CI verde não substitui observação independente.

**Critério pendente:** revisor externo realmente administrando host QEMU/libvirt distinto da VM Arch, coletando dados concretos e autenticando a proveniência, segurança do guest e condições do kernel. Não realizar merge/release antes disso.
