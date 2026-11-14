# PE-S2.64 | Índice de evidências humanas para homologação externa (HOLD)

**Estado inicial: NÃO EXECUTADO.** Esta ficha é um **modelo a ser preenchido pelo revisor independente**, não uma evidência de que a revisão ocorreu. Não cria gate automático, assinatura, veredito PASS, atestado de host ou autorização de release. A Issue #48 continua **OPEN/BLOCKED** e a PR #47, **Draft**, sem merge, APK, OTA, PE desconhecido ou release.

## Por que esta ficha existe

A cadeia PE-S2.17–S2.63 endurece a consistência de amostras, hashes, timestamps *não confiáveis* e respostas offline. Mesmo completamente coerente, o pacote pode ter sido gerado por alguém sem host externo, sem VM Arch nativa ou sem testemunhar Ghidra. Esta ficha permite ao revisor **separar observação humana, dados primários e inferência automatizada**. Não substitui os runbooks [S1 independente](PE-S1-NATIVE-ARCH-INDEPENDENT-REVIEW.md), [S2.24](PE-S2.24-EXTERNAL-REVIEWER-EXECUTION-HANDOFF-HOLD.md), [S2.22](PE-S2.22-REVIEWER-EXTERNAL-PINS-HOLD.md) ou a matriz normativa [S2.23](PE-S2.23-EXTERNAL-HOMOLOGATION-GAP-HOLD.md).

## Regras antes de preencher

1. **Não fazer a revisão no computador/conta/VM administrados pelo operador.** A independência administrativa e a autorização do revisor devem ser conferidas fora de banda e demonstráveis por documentação privada. A ferramenta não consegue autenticar essa separação.
2. **Não usar dados sintéticos de CI como amostras do host real.** Executar a cadeia em host QEMU/libvirt com KVM real e guest Arch nativo descartável, sob custódia do revisor, usando somente um PE *inofensivo, sintético, não executado* como dado para o Ghidra.
3. **Fixar os parâmetros de sessão antes da coleta.** SHA de commit completo, domínio/UUID, challenge e nonce distintos são escolhidos, verificados e guardados pelo revisor. Guardar SHA-256 dos originais e o pacote de pins em ambiente ao qual o operador não tenha acesso de escrita. SHA não comprova origem do processo ou do host.
4. **Preservar os originais privados intactos.** O índice público não deve conter challenge, nonce, chaves privadas, nomes/dados pessoais, captura integral do host, logs sensíveis, identificadores secretos ou caminhos internos exploráveis. Usar IDs opacos e uma versão saneada para qualquer comentário público.
5. **Não confundir retornos.** S2.21 `CANDIDATE_HOLD` é só preflight. S2.22/S2.23 podem retornar código 2 tanto para `HOLD` quanto para `REJECTED`. Ler o campo `status`; jamais converter automaticamente `HOLD` em PASS.
6. **Se não foi testemunhado, escrever NÃO_OBSERVADO.** Se falta cadeia de custódia, a prova é INSUFICIENTE, mesmo com hash válido. A alegação de um autor, a captura de um único PID ou um relógio crescente **não** substituem observação independente.

## Ficha privada de execução (preenchimento manual)

Criar e preservar este registro **fora do repositório**. Os campos abaixo são espaços de preenchimento, não dados reais:

| Campo | Valor a registrar pelo revisor |
| --- | --- |
| Identificador de caso | NÃO_PREENCHIDO |
| Revisor e autorização (referência privada) | NÃO_PREENCHIDO |
| Modo de comprovação de independência (fora de banda) | NÃO_PREENCHIDO |
| Identidade/controle do host QEMU/libvirt (referência privada) | NÃO_PREENCHIDO |
| Checkout Git completo conferido pelo revisor | NÃO_PREENCHIDO |
| Par domínio + UUID (referência privada, não publicar) | NÃO_PREENCHIDO |
| Challenge e nonce (custódia privada, não colar nesta ficha pública) | NÃO_PREENCHIDO |
| Início/fim testemunhados; fonte de tempo e limites de confiança | NÃO_PREENCHIDO |
| IDs de custódia privada de V1/V2/V3, recibo, logs e hashes externos | NÃO_PREENCHIDO |
| Resultado literal do S2.21 | NÃO_EXECUTADO |
| Resultado literal do S2.22 | NÃO_EXECUTADO |
| Resultado literal do S2.23 | NÃO_EXECUTADO |
| Parecer humano e sua referência privada | NÃO_EMITIDO |

Para cada classe, usar **NÃO_OBSERVADO**, **INSUFICIENTE** ou **OBSERVADO_POR_REVISOR**. O último é um rótulo *manual e limitado*, não uma aprovação de release. Registrar em custódia privada o identificador de cada original, SHA-256, local de custódia, método, momento, pessoa que testemunhou, cruzamentos de identidade e ressalvas. Não criar uma coluna automática `independent_vm_attestation=true`.

| Classe obrigatória da S2.23 | Estado inicial | Observação primária que o revisor precisa confrontar |
| --- | --- | --- |
| 1. Independência e autorização do revisor | NÃO_OBSERVADO | Identidade, autorização e separação administrativa confirmadas **fora de banda** |
| 2. Host QEMU/libvirt e domínio/UUID | NÃO_OBSERVADO | Propriedade/controle externo do host, KVM e origem do domínio conferidos independentemente |
| 3. Guest Arch nativo e kernel | NÃO_OBSERVADO | Boot real, kernel e systemd do guest descartável, sem trocar contêiner por VM |
| 4. Mesmo PID Ghidra sob cgroup v2 e seccomp | NÃO_OBSERVADO | PID/executável testemunhado *durante* análise sintética, seccomp modo 2 e cotas efetivas no mesmo processo/sessão |
| 5. Limite efetivo do journald | NÃO_OBSERVADO | Namespace/montagem do daemon, destino efetivo, política ativa e limite do filesystem |
| 6. Encerramento de escopo e descendentes | NÃO_OBSERVADO | Escopo/parada após análise e ausência de filhos sobreviventes, verificados independentemente |
| 7. BEFORE → WORK → AFTER | NÃO_OBSERVADO | Capturas originais e hashes retidos antes do trabalho, execução testemunhada e AFTER correspondente ao mesmo UUID/desafio/sessão |

**Para cada linha**, anexar somente na **cópia privada**: (a) IDs de arquivos primários e seus SHA-256; (b) quem observou e por qual canal; (c) relação verificável com commit, domínio, UUID, sessão e instante da execução; (d) discrepâncias/limitações; (e) veredito manual justificado. Se um item não tiver original verificável, mantê-lo `NÃO_OBSERVADO` ou `INSUFICIENTE`; um print isolado sem proveniência não basta.

## Fechamento humano, não automatizado

O revisor deve assinar/emitir **parecer próprio, separado da saída dos scripts**, com escopo, sete conclusões, testes negativos relevantes, lacunas residuais, limites do modelo de ameaça, referências dos originais e política explícita sobre risco. Um parecer pode continuar desfavorável mesmo que todas as linhas tenham sido observadas. O projeto não deve alterar flags de release a partir do preenchimento desta ficha.

Somente após a cadeia *real*, a revisão offline em checkout efetivamente read-only e o parecer externo deverão os responsáveis reavaliar a **Issue #48**. Não fechar a issue nem retirar Draft automaticamente. Nenhuma execução externa, verificação de KVM nativo, assinatura humana ou evidência independente está implícita no commit que adiciona este arquivo.

## Resumo público permitido (modelo, não preencher com dados fictícios)

- **Caso:** ainda não iniciado.
- **Sete classes S2.23:** 0/7 observadas por revisor independente.
- **Proveniência externa e custódia privada:** não comprovadas.
- **Verificações locais:** resultados CI não equivalem a homologação nativa.
- **Decisão:** **HOLD**; PR #47 Draft; Issue #48 OPEN; sem merge, APK, OTA ou release.
