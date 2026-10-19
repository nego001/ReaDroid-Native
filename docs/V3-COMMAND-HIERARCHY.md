# NegrescoDroid — General Supremo, CTA e hierarquias locais por SO

**Status:** projeto de arquitetura, não execução de agentes/IAs reais.
**Data:** 19/10/2026. Referências: [governança #7](https://github.com/nego001/ReaDroid-Native/issues/7), [CTA #5](https://github.com/nego001/ReaDroid-Native/issues/5), [explorador multi-GB #2](https://github.com/nego001/ReaDroid-Native/issues/2), [desktop/REA #3](https://github.com/nego001/ReaDroid-Native/issues/3) e [sync E2EE #4](https://github.com/nego001/ReaDroid-Native/issues/4).

## A cadeia de comando completa

```text
                         USUÁRIO
               (autoridade para aprovar/vetar)
                            │
                      GENERAL SUPREMO
                 política, auditoria e veto
                            │
                  CTA — CONTROLE DE ANÁLISE
           única IA operacional multiplataforma
              diagnóstico, análise e estratégia
                            │
                  CTO — CONTROLE OPERACIONAL
         organiza filas, prioridades e setores
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
  GENERAL ANDROID    GENERAL WINDOWS     GENERAL LINUX
         │                  │                  │
    Coronéis de         Coronéis de         Coronéis de
   APK/Segurança          PE/REA              ELF/REA
         │                  │                  │
   Capitães locais    Capitães locais    Capitães locais
         │                  │                  │
  Operadores locais  Operadores locais  Operadores locais
```

**Separação de responsabilidades:** o CTA determina o plano e as capacidades; o CTO converte missões aprovadas em ordens operacionais, acompanha a fila e roteia por setor; cada General local decide a alocação dentro do próprio SO. O CTO **não é uma segunda IA compartilhada**: será um serviço/scheduler determinístico, sem capacidade de elevar privilégios ou criar ferramentas inexistentes. Os agentes especialistas ficam exclusivos a Android, Windows ou Linux.

### Android: hierarquia exclusiva

- **General Android:** coordena prioridades, segurança, orçamento de RAM/disco e tarefas relacionadas ao APK no próprio Android.
- **Coronel APK/Manifesto:** capitães DEX, manifesto, assets e inventário de recursos.
- **Coronel Explorador:** capitães SAF, indexação, ZIP64, leitura de faixas, busca e streaming.
- **Coronel Construção:** capitães plano de edição, comparação, reconstrução unsigned e verificação SAF.
- **Coronel Segurança:** capitães Keystore, criptografia, verificação de integridade, risco e permissões.

### Windows: hierarquia exclusiva

- **General Windows:** coordena análise de PE e executáveis nativos, com limites e permissões do Windows.
- **Coronel PE/EXE:** capitães cabeçalhos, seções, imports/exports, recursos e arquitetura.
- **Coronel REA:** capitães integração REA/CLI/MCP e provedores instalados, com análise estática isolada.
- **Coronel Tecnologias:** capitães .NET/CIL, Electron e outros formatos reconhecidos.
- **Coronel Segurança:** capitães WinTrust/AuthentiCode, integridade, sandbox e política de execução.

### Linux: hierarquia exclusiva

- **General Linux:** coordena operações de binários ELF, PE somente leitura e sistemas de arquivos Linux.
- **Coronel ELF:** capitães símbolos, linking, loaders, bibliotecas `.so` e recursos.
- **Coronel PE/REA:** capitães identificação PE e análise offline (sem executar .exe).
- **Coronel Explorador:** capitães permissões, arquivos, mounts, symlinks, ZIP64 e streaming.
- **Coronel Segurança:** capitães isolamento, integridade, permissões e política de execução.

## CTO — Controle Operacional: organização por setores

- **Entrada:** somente ordens validadas pelo CTA e autorizadas dentro da política do General Supremo e pelo usuário.
- **Missões:** cada ordem identifica projeto/hash, sistema operacional, setor, ação, cargo de origem, permissões, prazo, orçamento de memória/disco/CPU, dependências e regra de cancelamento.
- **Planejamento:** construir fila com etapas dependentes, priorizar operações seguras, evitar trabalhos concorrentes pesados, agrupar tarefas por projeto e registrar progresso sem expor segredos.
- **Encaminhamento:** selecionar o General do SO exato; **não** enviar comandos do Windows para Android ou Linux, nem ultrapassar General → Coronel → Capitão → executor local.
- **Garantia:** validar capacidade anunciada pelo motor, autorização, assinatura/contexto e recursos antes do despacho; na ausência de evidência, bloquear em vez de inventar suporte.
- **Retorno:** reunir métricas, erros, hashes e resultados auditáveis e enviar ao CTA, que apresenta status e recomendações ao usuário.
- **Conflito de ordens:** prioridades não removem vetos de segurança, consentimento, regras de criptografia, isolamento local, nem limites reais de leitura multi-GB.
- **Multiplataforma:** mesmo contrato de missão CTO poderá funcionar em todas as plataformas, mas chaves, permissões e tarefas permanecem específicas do SO. Sincronizar projetos nunca dispara execução remota automática.

**Exemplo, Android:** CTA solicita leitura de um APK grande e define modo suportado → CTO separa Preflight → Índice ZIP64 (se existir motor homologado) → Inspeção de segurança → Relatório → General Android designa os coronéis do explorador, APK e segurança. Sem engine/seek/espaço/autorização, o CTO recusa e devolve ao CTA para novo plano. Os limites atuais do Android não são alterados.

**Máquina de estados futura:** PLANNED → AUTHORIZED → QUEUED → RUNNING → SUCCEEDED / FAILED / CANCELLED, com PAUSED apenas se retomada segura. Testes incluirão autenticação de ordem, OS errado, cargo falsificado, ausência de consentimento, replay, prazo vencido, dependências incompletas, falta de recursos e cancelamento.

**Tarefa de implementação:** [#8 CTO](https://github.com/nego001/ReaDroid-Native/issues/8), dependente de [#5 CTA](https://github.com/nego001/ReaDroid-Native/issues/5) e [#7 Governança](https://github.com/nego001/ReaDroid-Native/issues/7). **Este documento não torna o CTO funcional nem cria outra IA.**
## Modelo de permissões (obrigatório)

1. O usuário determina consentimento e finalidade. Nenhum posto tem permissão para ignorá-lo.
2. O General Supremo supervisiona política, qualidade, segurança e auditoria, mas **não é outro agente operacional multiplataforma**.
3. O CTA pode visualizar **declarações de capacidades**, estabelecer o plano e verificar evidências; **o CTO distribui somente missões autorizadas**, controla a fila e devolve relatório. Nenhum dos dois executa comandos do SO fora da hierarquia local.
4. O CTO não concede autorização ampla, não executa ferramentas e não pula o General do SO. Cada General de plataforma só conhece ferramentas e permissões do seu SO; um agente Android não assume o papel de agente Windows ou Linux.
5. Coronéis distribuem tarefas; capitães propõem planos para ações concretas; **operadores executam somente escopo autorizado** e devem recusar ampliação inesperada.
6. Toda missão deverá exigir identificador, OS, projeto/arquivo, hash quando aplicável, objetivo, modo, prazo, orçamento de memória/disco, permissões e confirmação em operações sensíveis.
7. **Falhar de forma segura:** negar ordens falsificadas, hierarquia alterada, consentimento ausente, transferência remota implícita, execução de binários não confiáveis e ação fora de capacidade.
8. Trilhas de auditoria registram decisão, executante, resultado e evidência sem segredos. A sincronização E2EE poderá transportar apenas conteúdo autorizado, **nunca ordens de execução automática**.

## Capacidade adaptativa: arquivos de 1 GB a 500 GB

O General Supremo define **política e tetos**; o CTA planeja **por operação**; o CTO organiza o despacho e verifica dependências; o General do SO consulta o **motor realmente disponível**. O operador executa somente após verificações determinísticas:

- **Metadados:** leitura mínima sempre que segura e autorizada.
- **Hash por streaming:** se houver motor comprovado, RAM mínima e acesso contínuo.
- **Índice ZIP64:** requer seek/ranges e indexador paginado funcional.
- **Análise profunda:** requer parser da tecnologia e orçamento validado.
- **Edição/exportação:** exige capacidade de engine e espaço seguro para saída separada; preserva original.

**500 GB é meta condicionada a recursos e suporte**, não promessa de que qualquer celular terá RAM/espaço suficientes. O limite de importação Android atual de **1 GiB** permanece até implementação real do explorador e homologação.

## Ordem de execução do projeto

1. Estabilizar base Android e a infraestrutura de arquivos grandes.
2. Implantar autorização, auditoria e hierarquia do **General Android** em modo seguro/testável.
3. Implantar o CTO como fila/roteador determinístico local com testes de permissões, dependências, cancelamento e segurança. Em seguida, conectar o CTA ao contrato de capacidades e CTO, sem conceder permissões por prompts de IA.
4. Depois da homologação Android: comandos Windows/Linux, REA, importação PE/ELF.
5. Sincronização E2EE opt-in entre workspaces e agentes, com versão e resolução de conflitos.
6. Redesenho visual separado conforme a issue #1.

**Nenhum General, CTA, CTO ou agente local descrito acima está funcionando hoje como sistema autônomo.**
