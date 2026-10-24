# NegrecoDroid — visão de produto: análise modular, multiplataforma e multiagente

**Situação:** visão de longo prazo, **PLANEJADA**. Não descreve recursos já implementados.
**Registro de produto:** [issue #17](https://github.com/nego001/ReaDroid-Native/issues/17).
**Trabalho em curso:** [issue #11](https://github.com/nego001/ReaDroid-Native/issues/11) e [PR #13](https://github.com/nego001/ReaDroid-Native/pull/13), etapa visual/funcional P7.
**Nome oficial:** NegrecoDroid. “NegoDroid” e “Nego Droid” são apelidos informais.

## 1. Ideia lapidada

**Uma plataforma em que a pessoa escolhe um aplicativo ou arquivo autorizado e recebe, com mínimo trabalho manual, um estudo técnico aprofundado, rastreável e reutilizável.** O NegrecoDroid coordena uma equipe de módulos e agentes especializados, combina métodos determinísticos com raciocínio de IA opcional, expõe progresso e limitações e entrega um ZIP organizado para consulta por humanos ou por qualquer assistente de IA.

O objetivo não é apenas “descompilar”; é **entender a estrutura e o comportamento observável** de maneira reproduzível: formatos, componentes, dependências, recursos, símbolos, fluxos, funções, dados e hipóteses verificadas. Não é possível prometer reconstituir com exatidão o código-fonte original de todo executável, nem garantir análise completa quando há ofuscação, criptografia, empacotamento ou incompatibilidade de plataforma.

### Experiência ideal

1. Selecionar arquivo ou projeto, sem precisar digitar uma sequência de comandos no CMD.
2. Reconhecer o formato por **assinatura do conteúdo** e metadados, em vez de confiar na extensão.
3. Avaliar riscos, permissões, recursos disponíveis, suporte real ao formato e plano de investigação.
4. Coordenar módulos de análise em uma fila de tarefas, paralelizando o que é seguro e independente.
5. Mostrar o que já foi observado, o que é hipótese, o que está incompleto e o que exige consentimento.
6. Entregar um **ZIP autocontido com relatórios, evidências, hashes e instruções**, dividido em blocos legíveis por Claude, Gemini, ChatGPT ou outra ferramenta, sem dependência obrigatória de um modelo específico.
7. Sincronizar o projeto entre computador e celular, mantendo no celular só os recursos adequados à plataforma.

**Exemplo abstrato:** um instalador desktop comercial pode ser classificado, ter metadados/dependências inventariados e ser estudado onde houver autorização. Isso **não autoriza** burlar DRM, licenças, autenticação, anti-cheat ou copiar/distribuir o programa. O software de origem não precisa ser executado para produzir a primeira versão do relatório.

## 2. Princípios do produto

- **Modularidade integral da arquitetura:** motor, UI, formatos, análise, agentes, relatórios, sincronização e ferramentas externas em pacotes separados, com interfaces versionadas. Um módulo pode falhar, ser desativado ou substituído sem corromper o projeto.
- **Equipe de agentes, não um modelo único:** coordenação, especialização, revisão cruzada, distribuição de tarefas e responsabilização por evidência. “Time humano” significa fluxo cooperativo e auditoria, não fingir que agentes são pessoas.
- **Determinismo primeiro:** classificadores, parsers e validações reproduzíveis; agentes de IA ajudam a escolher estratégias, correlacionar evidências e explicar descobertas, mas não podem inventar fatos.
- **Precisão verificável:** cada achado referencia offsets, caminhos, símbolos, versões e hashes; confiança, suposições, erro e cobertura aparecem no relatório. “Não sei” é resultado válido.
- **Velocidade responsável:** cache por hash, etapas incrementais, indexação, checkpoints, concorrência limitada, timeout, tratamento de falhas e orçamento configurável de CPU/RAM/disco.
- **Sem lock-in:** relatórios abertos em Markdown, JSON e formatos comuns; modelos de IA locais, remotos ou nenhum. Nunca exigir uma IA específica.
- **Privacidade e autorização:** arquivos próprios ou legitimamente autorizados; processamento local por padrão; envio para IA externa e sincronização sempre explícitos; não executar binários suspeitos por padrão.
- **Uma visão sincronizada, capacidades diferentes:** sincronizar estado, trabalhos, decisões e achados **não** significa rodar todos os motores no Android ou iOS.

## 3. Plataformas e divisão de responsabilidades

| Plataforma | Papel pretendido | Limite intencional |
|---|---|---|
| Windows desktop | Orquestração, formatos PE/EXE/DLL, pipelines pesados e laboratório isolado opcional | Análise dinâmica somente em ambiente isolado/autorizado |
| Linux desktop | Orquestração, ELF/SO, pipelines de análise estática e laboratórios Linux | Formato Windows não implica executá-lo no Linux |
| macOS desktop (alvo) | Cliente/worker desktop e análise de formatos suportados | Capacidades Mach-O/iOS dependem de ambiente, ferramentas e permissões |
| Android | Seleção/triagem leve de APK/ZIP, navegador de evidências, fila, notificações, aprovações e sincronização | Sem portar todo o motor pesado para o telefone |
| iOS | Cliente leve de projetos, relatórios, decisões e arquivos acessíveis | Restrições de sandbox/App Store; não presumir execução de ferramentas arbitrárias |
| Worker remoto opcional | Executa tarefas pesadas **em um PC controlado/autorizado pelo usuário** | Não iniciar infraestrutura remota, upload ou execução sem consentimento |

**Sincronização esperada:** projeto consistente entre dispositivos conectados, fila de operações offline, resolução de conflitos e hashes para garantir integridade. A expressão “100% sincronizado” é meta de experiência; nenhuma solução pode garantir sincronização instantânea quando um dispositivo está offline.

## 4. Formatos tratados por capacidade, não por marketing

**Candidatos:** APK/AAB/DEX/ZIP/JAR; PE/EXE/DLL; ELF/SO; Mach-O/IPA; WASM; imagens e formatos de arquivo/firmware identificáveis. Uma extensão desconhecida como **.ima** é um caso para identificação por assinatura e seleção de plugin, **não garantia** de que o conteúdo será decodificado.

Registrar para cada formato: identificação, leitura de metadados, inspeção estática, reconstrução aproximada quando tecnicamente suportada, análise dinâmica opcional, edição e exportação. Cada capacidade terá estado **suportada / parcial / não disponível**, verificado por testes e ambiente.

Não executar arquivos suspeitos automaticamente, não elevar privilégios e não prometer converter binários em código-fonte original perfeito.

## 5. Time de agentes previsto

O coordenador não precisa ser uma IA: ele deve operar com tarefas e regras de dependência. Agentes podem usar algoritmos determinísticos, modelos opcionais ou ambos.

1. **Coordenador:** divide etapas, delega, aplica políticas, decide prioridades e evita retrabalho.
2. **Identificador:** classifica arquivo, formato, arquitetura, assinatura, hashes e necessidade de parsers.
3. **Extrator:** inventaria contêineres, recursos, metadados e dependências preservando bytes de origem.
4. **Especialista por formato:** PE/ELF/Mach-O/DEX/etc., com adaptadores independentes.
5. **Analista estático:** procura referências, símbolos, funções, chamadas, permissões e fluxos relevantes.
6. **Analista dinâmico opcional:** só mediante autorização e sandbox; registra observações sem afetar a máquina hospedeira.
7. **Correlacionador:** associa descobertas e distingue hipóteses de fatos.
8. **Revisor cético:** tenta reproduzir achados, aponta contradições, reduz falsos positivos e pede evidência faltante.
9. **Redator técnico:** cria um resumo para leitura humana e versões estruturadas para IA externa.
10. **Empacotador/auditor:** verifica manifestos, privacidade, integridade e monta o ZIP.

Cada agente recebe **entrada limitada, escopo, orçamento, permissão, versão do analisador e critérios de saída**, e devolve evidências e erros. Agentes não podem modificar o material original ou conceder permissões uns aos outros por conta própria.

### Leitura distribuída em equipe

**Ideia do proprietário:** vários leitores **trabalham em paralelo sobre partes diferentes e estruturais de um mesmo arquivo**, em vez de um leitor monolítico processar tudo numa sequência. Um planejador organiza `shards` com dependências, um índice compartilhado evita retrabalho, a store de evidências recebe resultados e o revisor cruza contradições antes do ZIP. O desktop executa trabalhos pesados; mobile acompanha sem sobrecarga. Contrato técnico e testes planejados: [RFC de leitura distribuída](NEGRECODROID-RFC-LEITURA-DISTRIBUIDA.md). **Ainda não implementado.**

## 6. O ZIP é um produto de primeira classe

Um ZIP de estudo deve ser autocontido e auditável, sem exigir abrir uma interface proprietária. Estrutura inicial proposta:

    negreco-study/
      README.md
      manifest.json
      summary.md
      scope-and-limitations.md
      input/
        hashes.json
        identification.json
      inventory/
        files.json
        dependencies.json
        symbols.json
      findings/
        findings.json
        functions.json
        observations.md
      evidence/
        evidence-index.json
        relevant-extracts/
      graphs/
        calls.json
        dependencies.json
      agents/
        decisions.jsonl
        review.json
      ai/
        start-here.md
        context-index.json
        chunks/
      logs/
        errors.jsonl
        execution.jsonl

O ZIP deve declarar **versão de esquema, proveniência, ferramentas/versões, hashes, horários, parâmetros, cobertura, grau de confiança, avisos e arquivos omitidos**. Partes sensíveis ficam mascaradas ou fora do pacote por padrão. Não exportar segredos, tokens, dados privados ou cópias integrais desnecessárias de material protegido.

A pasta **ai/** deve conter blocos pequenos indexados por tema e IDs de evidência, para que outra IA possa estudar o conjunto **sem precisar de todo o contexto de uma vez**. Uma IA nunca recebe “100% decodificado” quando as ferramentas não puderam comprovar isso.

## 7. Etapas futuras, sem perder a etapa presente

**P7 (atual):** concluir visual/responsividade, validação das referências e teste físico; não transformar PR #13 em lançamento prematuro.

**Trilha futura A — núcleo desktop:** classificação por assinatura, inventário determinístico de um formato inicial autorizado, cache, rastreabilidade, relatório ZIP offline e testes com fixtures.

**Trilha futura B — módulos/contratos:** SDK de plugins, motor de jobs, capabilities por dispositivo, controle de recursos, checkpoint/retry e isolamento.

**Trilha futura C — equipe multiagente:** especialista + revisor independentes, qualidade quantificável, relatório unificado e seleção opcional de modelos de IA.

**Trilha futura D — sincronização e clientes:** worker desktop com Android/iOS enxutos, envio aprovado pelo usuário, funcionamento offline e acesso móvel ao progresso/ZIP.

**Trilha futura E — múltiplos formatos:** ampliar suporte um módulo por vez, com matriz de testes e limitações honestas.

**Trilha futura F — análise dinâmica:** somente depois de sandbox, proteção contra amostras nocivas, autorização e validação de privacidade.

## 8. Definição de sucesso

A ferramenta será considerada útil quando uma amostra de teste autorizada puder ser selecionada numa UI, identificada corretamente, processada sem passos manuais rotineiros, analisada por módulos auditáveis e exportada como ZIP que **outra IA consegue interpretar com referências verificáveis**.

Medir: cobertura por formato, taxa de erro, falso positivo, tempo total, memória máxima, tarefas recuperadas após falha, concordância da revisão, completude do ZIP e facilidade de retomar o projeto no celular.

**Não confundir** uma arquitetura planejada com implementação concluída. Toda etapa terá critérios de aceite e CI próprios antes de aparecer como funcional no aplicativo.

## 9. Guardrails do repositório

Esta visão **não muda a implementação corrente**, não executa engenharia reversa em programas de terceiros, não faz merge na main, não gera APK distribuível e não liga OTA. A P7 da [PR #13](https://github.com/nego001/ReaDroid-Native/pull/13) mantém suas aprovações e bloqueios independentes.
