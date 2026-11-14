# PE-S2.23 | Dossiê de lacunas para homologação externa da VM Arch

**ESTADO:** protocolo e auditoria offline de prontidão do pacote local. **A homologação externa ainda não aconteceu.** CI Ubuntu e Arch userspace são ensaios, não uma VM nativa independentemente administrada. PR #47 continua Draft, sem merge, APK, OTA, execução de Windows PE desconhecido ou autorização de lançamento.

## 1. Qual é o avanço

As etapas até PE-S2.22 produzem uma cadeia local verificável: quatro observações do host e assinaturas V1, uma amostra de `domstats` V2, capturas antes/depois V3, SHA-256 do recibo e um pacote de pins em diretório privado separado. Os ensaios CI validam assinaturas Ed25519 reais e o verificador do recibo/Git em montagem realmente somente leitura. Mas os dados do host nessa CI são simulados.

O módulo **`tools/pe_arch_vm_s2_23_external_gap_register.py`** chama o verificador offline da S2.22 e gera uma **matriz fechada com 7 classes de provas ainda não verificadas independentemente**. A lista não permite marcar a própria evidência como aprovada, não aceita parâmetros como `--approve` e nunca retorna autorização de release. O novo módulo é somente leitura, não cria uma versão V4 de assinatura, não inicia hipervisor, não acessa rede, não altera a VM nem executa Ghidra.

## 2. Como o revisor consulta o dossiê

Com os arquivos **realmente coletados** no próprio host do revisor, preparar as quatro pastas disjuntas S2.22: observador (0700), custódia (0700), arquivo de pins do revisor (0600 sob pasta 0700) e checkout Git do commit, montado de modo somente leitura. O SHA do JSON dos pins deve ser preservado fora do acesso do operador.

```bash
python3 -B tools/pe_arch_vm_s2_23_external_gap_register.py \
  --pin-file /private/reviewer-pins/reviewer-held-pins.json \
  --observer-dir /private/observer \
  --custody-dir /private/custody \
  --native-receipt /private/custody/acceptance.json \
  --source-root /private/readonly-source \
  --expected-pin-bundle-sha256 "$REVIEWER_OUT_OF_BAND_SHA256" \
  --inspect-existing
```

Sem `--inspect-existing`: saída `PE_S2_23_EXTERNAL_HOMOLOGATION_GAP_PLAN_NOT_STARTED`, código 0, **sem ler os arquivos**. Com a opção e pacote local íntegro: `HOLD_PE_S2_23_SIGNED_CUSTODY_VALID_EXTERNAL_VM_PROOFS_PENDING`, **código 2**. Se os hashes/arquivos/assinaturas falharem: `REJECTED_PE_S2_23_LOCAL_PACKAGE_INVALID_EXTERNAL_VM_HOLD`, **código 2**; não há validação de segurança positiva. Sempre usar o campo `status` em vez de interpretar só o código de saída.

## 3. Matriz obrigatória, só o revisor pode concluir fora do software

| Classe de prova | Evidência externa necessária |
| --- | --- |
| Identidade e independência do revisor | Identidade, autorização e controle do revisor confirmados por canal não controlado pelo operador |
| Origem e administração do hipervisor | Revisor controla o host QEMU/libvirt e confirma origem, domínio KVM e UUID independentemente do guest |
| VM Arch nativa e kernel | Boot/versões/kernel/systemd de VM Arch descartável, não contêiner ou runner GitHub, testemunhados no host |
| Cgroup v2 e seccomp na mesma sessão | Kernel mostra cgroup limitado e seccomp modo 2 no PID do Ghidra durante análise *de PE sintético como dado* |
| Cota efetiva do journald | Limites reais de armazenamento/montagem do journal comprovados no host/guest, não só configuração declarada |
| Encerramento do escopo e descendentes | Observação do host confirma que árvore de processos e escopos foram eliminados após análise |
| Cronologia antes/trabalho/depois | Capturas libvirt originais, challenge, recibo e processo Ghidra ligados à mesma sessão por observação independente, não apenas `cpu.time` crescente |

As sete linhas sempre aparecem no relatório com `state=PENDING_INDEPENDENT_REVIEWER_EVIDENCE`, inclusive se a cadeia V1/V2/V3 e o checkout local forem íntegros. Isso é intencional: **um arquivo assinável não prova que um host independente foi usado**. Não existe campo para o operador atribuir status positivo a essas lacunas.

Um revisor humano deve validar a documentação original, a proveniência do host e a observação do kernel. Qualquer exigência não comprovada deve permanecer `HOLD`; uma revisão humana posterior deve ter sua própria política formal de aprovação e não converter o resultado desse script em `independent_vm_attestation=true`.

## Complemento PE-S2.40: contrato de chaves fechado

A [PE-S2.40](PE-S2.40-EXTERNAL-REVIEW-SCHEMA-STRICT-HOLD.md) fixa o conjunto completo de **13 campos** da saída local S2.22 antes de a S2.23 produzir seu registro de sete lacunas. Qualquer campo novo (inclusive uma alegação falsa de aprovação), faltante ou rebatizado é recusado, assim como valores de controle divergentes. Isso impede a aceitação silenciosa de mudanças de esquema, **não autentica revisor, host ou VM** e não reduz nenhuma lacuna externa.

## 4. Testes e limites

`tests/test_pe_arch_vm_s2_23_external_gap_register.py` usa assinaturas V1/V2/V3 Ed25519 de chaves descartáveis reais em nove testes de contrato, mas o recibo/Git local são **simulados nesses testes unitários**. O ensaio Ubuntu Bubblewrap, herdado da S2.20 e ampliado na S2.22, executa a S2.23 **sem mocks para SHA do pacote, assinaturas V1/V2/V3, recibo, Git, montagem readonly e verificação S2.22**, usando dados de libvirt **sintéticos** e relatório de aceitação **sintético**. A CI exige que todas as 7 classes permaneçam pendentes.

**Próxima ação real:** um terceiro independente deve disponibilizar e operar host QEMU/libvirt e VM Arch nativa descartável, realizar o protocolo documentado em `PE-S1-NATIVE-ARCH-INDEPENDENT-REVIEW.md` e preservar provas originais. Nenhuma etapa desta CI demonstra que isso aconteceu. PR #47 Draft e release HOLD.

## PE-S2.24 | Transferência operacional para revisor independente

O passo seguinte está organizado em [PE-S2.24-EXTERNAL-REVIEWER-EXECUTION-HANDOFF-HOLD.md](PE-S2.24-EXTERNAL-REVIEWER-EXECUTION-HANDOFF-HOLD.md), com sequência host/guest/offline, as sete provas obrigatórias, condições de parada e a distinção entre `CANDIDATE_HOLD`, `REJECTED` e `HOLD` local. **Este documento é um roteiro, não prova de uma VM nativa**. Não há novo protocolo de assinatura, status de aprovação ou execução externa nesta alteração. A PR continua Draft e o release permanece bloqueado.
