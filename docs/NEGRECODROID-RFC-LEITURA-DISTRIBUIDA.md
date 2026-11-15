# NegrecoDroid — RFC: leitura distribuída e análise colaborativa de arquivos

**Estado:** proposta de arquitetura, não implementada.  
**Origem:** ideia do proprietário de distribuir a leitura de um mod/aplicativo por vários módulos especializados, **em paralelo**, e juntar as conclusões como uma equipe.  
**Iniciativa:** [visão multiagente #17](https://github.com/nego001/ReaDroid-Native/issues/17).  
**Etapa atual separada:** P7 / PR #13; não altera app nem libera APK/OTA.

## 1. A experiência esperada

Ao abrir um APK, EXE, biblioteca ou pacote de mod suportado, o usuário **não precisa mandar dezenas de comandos**. O sistema faz uma identificação inicial do formato e organiza a análise numa equipe de leitores especializados:

- leitor de cabeçalhos, arquitetura e assinaturas;
- leitor da árvore de arquivos, manifestos e recursos;
- leitor de código, metadados, símbolos e funções disponíveis;
- leitor de dependências, chamadas e referências cruzadas;
- leitor de configuração, assets e arquivos específicos do formato;
- verificador de integridade, cobertura e contradições.

**Eles não devem apenas ler o arquivo todo um após o outro.** Quando as partes são independentes e há recursos, executam *simultaneamente* sobre fatias/índices seguros do mesmo material. Uma tarefa que depende de outra espera pelo resultado necessário, enquanto as demais continuam. O coordenador registra o progresso de todos e consolida os achados. Os analistas podem ser processos determinísticos e/ou agentes de IA, sem que seja necessário iniciar um LLM por fatia.

## 2. Divisão inteligente: primeiro a estrutura, depois as fatias

**Não cortar um binário aleatoriamente em blocos de bytes para descompilar.** Primeiro detectar formato por assinatura e construir um **índice estrutural imutável** (seções, tabelas, entradas do ZIP, classes DEX, símbolos, offsets, dependências). A partir dele, o planejador cria unidades com limites conhecidos:

| Material | Divisão preferencial |
| --- | --- |
| APK/ZIP/mod de jogo | Arquivos e diretórios, manifestos, recursos, DEX, bibliotecas, scripts/configurações |
| DEX/JAR | Pacotes, classes e métodos; índice global para resolver referências |
| EXE/PE | Headers, seções, import/export, recursos e faixas de funções identificadas |
| ELF/SO/Mach-O | Seções, símbolos, relocations, imports e unidades de código reconhecidas |
| Arquivo gigante sem estrutura confiável | Leitura em faixas limitadas para hashing, triagem e extração com sobreposição de contexto quando apropriado; **sem afirmar descompilação de fragmentos brutos** |

Cada `shard` deve conter: `job_id`, `shard_id`, caminho/tipo do input, **SHA-256 original**, origem, limites de bytes ou IDs semânticos, dependências, analisador + versão, permissões, orçamento e estado. O arquivo original é somente leitura.

## 3. Execução coordenada e rápida

1. **Triagem única:** calcular hash e formato; detectar conteúdo malformado, compressão em camadas, tamanho, permissões e plugins disponíveis.
2. **Índice compartilhado:** construir uma tabela de entradas, offsets, símbolos e dependências de forma persistente para evitar leituras redundantes.
3. **Planejador/DAG:** gerar as fatias independentes e dependentes, ordenar por custo e utilidade; compartilhar apenas fatos validados, não palpites.
4. **Escalonador:** rodar tarefas paralelas **dentro de limites configuráveis** de CPU, RAM, disco, I/O, bateria e temperatura. Não criar um processo/IA para cada função se isso custar mais do que agrupar as tarefas.
5. **Consolidação incremental:** gravar os resultados numa store com IDs de evidência, resolvendo referências entre módulos. Exibir progresso e resultados parciais válidos sem confundi-los com conclusão.
6. **Revisão cruzada:** um verificador independente reavalia os achados mais relevantes, detecta duplicatas, divergências e lacunas.
7. **Exportação:** gerar ZIP com o mapa de tarefas, evidências verificadas, cobertura, limitações e relatório técnico amigável para outras IAs.

O desktop é o **worker principal** dos módulos pesados. Android/iOS podem fazer triagem leve e visualizar os resultados, mas **não devem carregar todo o motor**; com autorização, encaminham tarefas ao desktop vinculado.

## 4. Precisão: unir resultados sem inventar respostas

- **Proveniência obrigatória:** cada afirmação cita `input_hash`, caminho/offset ou símbolo, `shard_id`, versão da ferramenta e evidências.
- **Cobertura verificável:** o planejador registra as unidades esperadas; cada unidade termina como `complete`, `partial`, `unsupported`, `failed`, `cancelled` ou `not_applicable`. Lacunas **não** contam como analisadas.
- **Referências cruzadas:** classes, funções, imports e recursos compartilhados são resolvidos numa fase de integração; um resultado local **não** pode declarar que conhece todo o programa.
- **Conflitos explícitos:** se dois módulos discordarem, o relatório mostra ambas as hipóteses e o motivo, sem escolher a versão mais convincente pela escrita.
- **Deduplicação e cache:** `input_sha256 + shard_scope + plugin_version + options + policy_version`; mudar qualquer elemento relevante invalida o cache.
- **Parcial honesto:** falha em uma fatia não apaga resultados das outras; exportar erros, cobertura incompleta e avisos, com retomada idempotente.
- **Segurança:** não executar a amostra por padrão, não contornar licenças/DRM/proteções ou extrair segredos; módulos estáticos isolados, análise dinâmica apenas com autorização explícita e sandbox.

### Exemplo conceitual

```text
Arquivo autorizado
        |
 [Identificador + índice estrutural]
        |
  [Coordenador de tarefas e orçamento]
        |
        +---- Leitor de metadados ---------+
        +---- Leitor de recursos ----------+
        +---- Leitor de código/símbolos ---+--> [Store de evidências]
        +---- Leitor de dependências ------+            |
        +---- Leitor de configurações -----+     [Correlação + revisor]
                                                     |
                                             [Relatório + ZIP]
```

**Paralelo onde possível, sincronizado onde necessário**: o objetivo não é dispersar a informação, e sim distribuir o esforço de leitura.

## 5. Entrega ZIP independente de fornecedor de IA

Propor os artefatos adicionais:
- `planning/shards.json`: mapa das unidades, ranges, dependências, estados e orçamentos;
- `planning/coverage.json`: unidades previstas/analisadas/não suportadas, lacunas e justificativas;
- `agents/dispatch.jsonl`: quem analisou o quê, custo, tempo, cancelamentos e retries;
- `evidence/cross-references.json`: IDs unificados entre achados de leitores diferentes;
- `findings/conflicts.json`: desacordos e revisão;
- `ai/context-index.json` e `ai/chunks/`: resumos compactos com links para evidência por unidade.

Exportar relatórios em Markdown/JSON, manifesto dos arquivos e SHA-256; excluir dados privados e bytes protegidos desnecessários por padrão. Claude, Gemini, ChatGPT e leitores humanos devem conseguir usar o pacote sem protocolo privado obrigatório.

## 6. Critérios de aceite para futura implementação

- [ ] Mesma amostra de teste autorizada: execução serial vs paralela gera **achados equivalentes e os mesmos IDs estáveis**, salvo métricas/ordem de término.
- [ ] Combinações de shards cobrem todas as unidades **compatíveis** planejadas, sem duplicação nem lacunas silenciosas.
- [ ] Dependências cruzadas entre métodos/arquivos são resolvidas ou explicitamente marcadas `unresolved`.
- [ ] Uma fatia que falha não bloqueia relatórios parciais válidos das demais; retomar após parada não perde nem duplica achados.
- [ ] Limites de RAM/CPU/I/O configurados são respeitados; benchmark usa tempo total, pico de memória e qualidade, não apenas número de agentes.
- [ ] Dois leitores divergentes geram registro de conflito auditável, nunca um consenso inventado.
- [ ] Progresso e cancelamento funcionam com worker desktop e cliente móvel leve offline.
- [ ] ZIP é legível sem NegrecoDroid e passa validação de schema/hashes/privacidade.
- [ ] Sem execução automática de amostra desconhecida, upload silencioso ou claims de decodificação universal.

**Próxima implementação futura:** protótipo determinístico com um formato e fixtures próprios antes de adicionar muitos agentes de IA. Primeiro acertar distribuição, cobertura e integridade; depois ampliar a equipe.
