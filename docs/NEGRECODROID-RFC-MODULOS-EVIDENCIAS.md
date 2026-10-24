# NegrecoDroid — RFC de arquitetura: core, plugins, agentes e evidências

**Status:** PROPOSTA / não implementada. Relacionada à [issue #17](https://github.com/nego001/ReaDroid-Native/issues/17).
**Referência de produto:** [Visão multiplataforma e multiagente](NEGRECODROID-VISAO-PLATAFORMA-MULTIAGENTE.md).
**Compatibilidade:** a base atual é nativa Android; Rust, IPC e desktop worker abaixo são **opções de design**, não componentes que já existem no repositório.

## 1. Domínios separados

| Domínio | Responsabilidade | Não deve fazer |
|---|---|---|
| UI/cliente | Selecionar projeto, exibir status e aprovar operações | Parse pesado ou execução arbitrária embutida |
| Core de jobs | Estado, filas, DAG, cancelamento, checkpoints, persistência | Decidir achados sem evidências |
| Registro de plugins | Discover, versão, capabilities, contratos e dependências | Carregar plugin desconhecido com permissão irrestrita |
| Analisadores determinísticos | Identificar tipos e extrair estrutura/metadados | Alucinar código-fonte ou atribuir autoria |
| Runtime de agentes | Estratégias, correlação, revisão e recomendações | Exfiltrar amostras, promover hipóteses a fatos |
| Sandbox de análise dinâmica | Observação autorizada em ambiente isolado | Rodar arquivo host diretamente por conveniência |
| Store de evidências | Hashes, proveniência, retenção e deduplicação | Alterar input original |
| Exportador | Pacote ZIP e índice para IA/humano | Incluir segredos/arquivos protegidos sem revisão |
| Sincronização | Estado de projeto, progresso, artefatos autorizados | Transferir bytes silenciosamente ou obrigar cloud |

Dependências seguem **interfaces/contratos**, nunca imports internos atravessando domínios. Plugins devem ser testáveis individualmente e desativáveis sem destruir dados.

## 2. Contrato mínimo para plugins

Todo plugin declara um manifesto versionado, independentemente da linguagem:

- id, version, schema_version, publisher, integrity_sha256
- input_kinds: formatos detectados (não somente extensões)
- operations: identify, inventory, static, dynamic-opt-in, summarize, export
- platforms: windows, linux, macos, android, ios, remote
- requirements: memória, CPU, disco, runtime, ferramentas, permissões
- risk: sem execução, leitura local, sandbox necessária, acesso à rede opcional
- emitted_artifacts e evidence_schema
- cancellation, timeout, retry_policy, deterministic_output
- license e regras de distribuição

Assinatura de alto nível (não implementação):

    probe(input_metadata) -> capability_result
    plan(input_manifest, policy, budget) -> tasks
    execute(task, evidence_store, cancellation) -> result
    verify(result, evidence_store) -> verification

A execução de plugins de terceiros ocorre em **processo isolado com permissões mínimas**, quando disponível. Cada saída usa esquema validado e hashes. Nada é carregado só porque um arquivo tem extensão conhecida.

## 3. Orquestração de agentes

Jobs são uma **DAG** de estágios. Estados explícitos: queued, running, partial, blocked, failed, cancelled, completed. Falha local deve registrar causa e permitir retomada sem repetir tarefas já válidas.

**Ordem sugerida:**

1. Intake (hash, consentimento, tipo, limitações, tamanho)
2. Inventory (árvore/recursos/dependências)
3. Analysis (plugins independentes compatíveis)
4. Cross-check (comparação de evidências, contradições, revisor)
5. Redaction (saneamento de dados/segredos)
6. Packaging (validar índice, ZIP, integridade)
7. Optional sync (autorizada por projeto)

Coordenador decide o que rodar conforme custo, risco e plataforma. Revisor recebe os achados **com IDs de evidência**, e não apenas uma narrativa convincente. Uma divergência não é escondida: vira finding de conflito ou limitações.

Tarefas de custo elevado só são despachadas ao desktop/worker selecionado pelo usuário; celular pode enfileirar pedido e receber resultados. **Conectividade ausente não autoriza ações fora do consentimento.**

### Subetapa de distribuição da leitura (proposta)

A etapa de `Analysis` não é um único analisador monolítico: após identificação e indexação, o coordenador **particiona semanticamente** o input em unidades de trabalho e despacha leitores independentes em paralelo com limitação de recursos. A integração resolve referências entre unidades e um revisor procura conflitos e lacunas. Ver [RFC de leitura distribuída](NEGRECODROID-RFC-LEITURA-DISTRIBUIDA.md) para regras de divisão por formato, cache, proveniência, cobertura e testes serial/paralelo. **Conceito, não recurso do aplicativo atual.**

## 4. Identidade de achado e confiança

Cada achado estruturado deve registrar, no mínimo:

    finding_id
    category / severity / confidence
    claim
    evidence_refs[]
    source_offsets_or_paths[]
    analyzers[] with versions
    assumptions[]
    limitations[]
    reviewer_verdict
    status: observed | inferred | inconclusive | contradicted

Valores de confiança não podem ser apresentados como certeza sem calibração. A severidade de um risco não é sinônimo de probabilidade. Achados que não podem ser reproduzidos são marcados como inconclusivos.

## 5. Qualidade, velocidade e falhas

- **Cache endereçado por SHA-256** do input e versões do parser/política; invalidar quando parâmetros mudam.
- **Filas com prioridade e cotas:** limites CPU/RAM/disco, subprocessos supervisionados, memória por plugin, cancelamento real.
- **Sem execução automática:** intake de binário desconhecido executa apenas parsers estáticos com limites de tamanho, profundidade e tempo.
- **Retries com backoff**, só onde operações forem idempotentes; evitar loops infinitos em amostras inválidas.
- **Resiliência:** resultados parciais devem chegar ao ZIP com erros completos, jamais mudar falhas para sucesso.
- **Teste de integração:** fixtures próprios/autorizados com resultados esperados para cada formato; fuzz dos parsers e detecção de arquivos malformados.
- **Medição:** tempo por estágio, pico de memória, cobertura de símbolos, falhas por plugin, false positives, validação do ZIP.

## 6. Segurança, ética e interoperabilidade

O produto serve para investigação técnica, manutenção, interoperabilidade, pesquisa autorizada e estudo. A matriz de capacidades e suas permissões devem refletir leis e contratos aplicáveis. Não criar fluxo para contornar DRM, quebrar autenticação, extrair credenciais, invadir sistemas ou distribuir executáveis de terceiros.

O envio a LLMs externos é **opt-in por projeto**, com confirmação do que será compartilhado. A exportação padrão é privada e local, com redaction de segredos e dados pessoais, nomes de arquivos seguros, proteção contra zip-slip, limitação de tamanho e manifesto de SHA. Relatórios abertos devem usar versões estáveis de esquema.

O software nunca deve afirmar “decompilação 100% fiel” quando otimizações e strip impedem reconstrução. Repetibilidade e evidência são mais importantes que quantidade aparente de texto gerado.

## 7. Esqueleto conceitual de repositórios/pacotes

A organização abaixo é **proposta**, não diretórios que já existam:

    core/
      contracts/
      jobs/
      evidence/
      policy/
    plugins/
      apk-dex/
      pe/
      elf/
      macho/
      wasm/
      archives/
    agents/
      coordinator/
      correlator/
      skeptic-reviewer/
      report-writer/
    clients/
      android/
      ios/
      desktop/
    workers/
      local-desktop/
      remote-opt-in/
    exporters/
      portable-study-zip/
    tests/
      fixtures/
      contracts/
      cross-platform/
      security/

O core pode ser implementado em linguagem portátil como **Rust (opção a avaliar)** e ter UIs nativas/plataforma, preservando o app Android atual. Não migrar código funcional de forma prematura só para satisfazer um desenho novo.

## 8. Gates de implementação

- **Gate A:** contratos versionados e primeira amostra de teste autorizada.
- **Gate B:** parser determinístico, inventário e ZIP completo + checksum.
- **Gate C:** plugin adicional intercambiável e falha isolada/retry.
- **Gate D:** coordenador multiagente, revisor cético, rastro de decisões.
- **Gate E:** worker desktop + cliente móvel leve com sincronização autorizada.
- **Gate F:** formato extra / análise dinâmica somente com testbed e sandbox.

**Gate atual separado:** concluir P7 visual, CI, referências e ensaio físico Galaxy A55 antes de qualquer release. Esta RFC não é autorização para publicar ou integrar.
