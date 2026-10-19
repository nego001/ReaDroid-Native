# NegrescoDroid — General Supremo, CTA e hierarquias locais por SO

**Status:** projeto de arquitetura, não execução de agentes/IAs reais.
**Data:** 19/10/2026. Referências: [governança #7](https://github.com/nego001/ReaDroid-Native/issues/7), [CTA #5](https://github.com/nego001/ReaDroid-Native/issues/5), [explorador multi-GB #2](https://github.com/nego001/ReaDroid-Native/issues/2), [desktop/REA #3](https://github.com/nego001/ReaDroid-Native/issues/3) e [sync E2EE #4](https://github.com/nego001/ReaDroid-Native/issues/4).

## A cadeia de comando completa

```text
                              USUÁRIO
                    (autoridade e autorização)
                                 │
                          GENERAL SUPREMO
                   (política global, supervisão,
                    auditoria e poder de veto)
                                 │
                    CTA — CONTROLE DE ANÁLISE
                  (única IA de orquestração
                   operacional multiplataforma)
                    /            |             \
          GENERAL ANDROID   GENERAL WINDOWS   GENERAL LINUX
           (só Android)     (só Windows)     (só Linux)
                │                │                │
        Coronéis locais   Coronéis locais  Coronéis locais
                │                │                │
        Capitães locais   Capitães locais  Capitães locais
                │                │                │
        Operadores        Operadores       Operadores
        determinísticos   determinísticos determinísticos
```

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

## Modelo de permissões (obrigatório)

1. O usuário determina consentimento e finalidade. Nenhum posto tem permissão para ignorá-lo.
2. O General Supremo supervisiona política, qualidade, segurança e auditoria, mas **não é outro agente operacional multiplataforma**.
3. O CTA pode visualizar **declarações de capacidades**, distribuir missões aprovadas e verificar evidências, mas não pode executar comandos de SO fora da hierarquia local.
4. Cada General de plataforma só conhece ferramentas e permissões do seu SO; um agente Android não assume o papel de agente Windows ou Linux.
5. Coronéis distribuem tarefas; capitães propõem planos para ações concretas; **operadores executam somente escopo autorizado** e devem recusar ampliação inesperada.
6. Toda missão deverá exigir identificador, OS, projeto/arquivo, hash quando aplicável, objetivo, modo, prazo, orçamento de memória/disco, permissões e confirmação em operações sensíveis.
7. **Falhar de forma segura:** negar ordens falsificadas, hierarquia alterada, consentimento ausente, transferência remota implícita, execução de binários não confiáveis e ação fora de capacidade.
8. Trilhas de auditoria registram decisão, executante, resultado e evidência sem segredos. A sincronização E2EE poderá transportar apenas conteúdo autorizado, **nunca ordens de execução automática**.

## Capacidade adaptativa: arquivos de 1 GB a 500 GB

O General Supremo define **política e tetos**; o CTA planeja **por operação**; o General do SO consulta o **motor realmente disponível**. O operador executa somente após verificações determinísticas:

- **Metadados:** leitura mínima sempre que segura e autorizada.
- **Hash por streaming:** se houver motor comprovado, RAM mínima e acesso contínuo.
- **Índice ZIP64:** requer seek/ranges e indexador paginado funcional.
- **Análise profunda:** requer parser da tecnologia e orçamento validado.
- **Edição/exportação:** exige capacidade de engine e espaço seguro para saída separada; preserva original.

**500 GB é meta condicionada a recursos e suporte**, não promessa de que qualquer celular terá RAM/espaço suficientes. O limite de importação Android atual de **1 GiB** permanece até implementação real do explorador e homologação.

## Ordem de execução do projeto

1. Estabilizar base Android e a infraestrutura de arquivos grandes.
2. Implantar autorização, auditoria e hierarquia do **General Android** em modo seguro/testável.
3. Implementar CTA apenas após contrato de capacidades e isolamento, sem conceder permissão por prompts de IA.
4. Depois da homologação Android: comandos Windows/Linux, REA, importação PE/ELF.
5. Sincronização E2EE opt-in entre workspaces e agentes, com versão e resolução de conflitos.
6. Redesenho visual separado conforme a issue #1.

**Nenhum General, CTA ou agente local descrito acima está funcionando hoje como IA autônoma.**
