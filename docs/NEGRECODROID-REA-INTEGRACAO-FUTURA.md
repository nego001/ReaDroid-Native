# NegrecoDroid + REA: adaptador opcional de análise no desktop

**Decisão do proprietário (23/10/2026):** considerar o arquivo fornecido `rea-main.zip` como uma das bases de integração futura do NegrecoDroid e, em seguida, **retomar a P7 atual**. Este documento é inventário/contrato de integração, **não** implementação nem aprovação de execução de binários.

## Proveniência do ZIP recebido

- Nome do arquivo fornecido: `rea-main.zip`
- SHA-256 dos bytes do ZIP: `935ff7d68df914be31f17b3c9e2c41bddf71c4b4aff123d08b51b0659bbfbff3`
- Projeto declarado por `package.json`: `rea-agents`, versão **6.7.0**, `https://github.com/morluto/rea`.
- Licença raiz: **MIT**, copyright 2026 morluto; **dependências/provedores têm licenças próprias**, descritas em `THIRD_PARTY_NOTICES.md`.
- Documento inspecionado sem executar scripts, baixar dependências, instalar ferramentas nem rodar qualquer amostra.
- Arquivo ZIP **não é código do NegrecoDroid**, **não é um APK** e **não foi incorporado em massa** ao repositório; o SHA acima apenas identifica esta cópia recebida, não comprova correspondência com o HEAD remoto do REA.

## O que é reaproveitável, com restrições explícitas

| Capacidade observada | Dependência | Direção de integração |
| --- | --- | --- |
| Inventário estático, metadados de APK, evidências e bundles | REA CLI/MCP + ambiente compatível | Worker desktop opcional; importar resultados com proveniência e cobertura |
| Inspeção de assinaturas APK v1/v2/v3/v3.1 | REA (ferramenta estática declarada) | Consulta somente leitura; não assinar nem modificar arquivos |
| Manifesto, classes, métodos e relações Android | JDK completo + JADX headless configurado no PC | Tarefas delimitadas por escopo, evidência identificável por hash |
| Binários nativos / bibliotecas ELF, PE etc. | Provedores opcionais externos (Ghidra/Hopper/IDA, conforme plataforma/licença) | Só habilitar na matriz de capacidade realmente validada |
| Análise com vários especialistas | Coordenador futuro do NegrecoDroid | REA é **um provedor opcional**, não o orquestrador central ou substituto dos leitores nativos |

**Requisitos declarados no pacote inspecionado:** Node `^22.23.4 || ^24.22.1 || >=26.12.1`; pacote npm `rea-agents`. O projeto também descreve uso de JDK/JADX para análise Android aprofundada. Dependências de terceiros não devem ser instaladas silenciosamente.

## Contrato proposto: integração isolada e cooperativa

1. **Indexador proprietário do NegrecoDroid:** classifica o arquivo por assinatura, calcula SHA-256, determina estruturas sem executar conteúdo e define unidades semânticas (shards) conforme a RFC de leitura distribuída.
2. **Planejador/capability registry:** só agenda um trabalho REA se o formato/ambiente/provedor realmente estiverem disponíveis; tarefas independentes continuam com os leitores nativos.
3. **Bridge desktop fora do processo Android:** executa uma operação explícita de CLI/MCP com autorização do usuário, paths canonizados, limites de CPU/RAM/tempo/saída e sandbox conforme o risco. Nunca dá shell irrestrito ao APK Android ou a plugins não confiáveis.
4. **Adaptador de evidências:** converte cada resposta REA para o esquema interno com `input_sha256`, `shard_id`, `provider=rea`, `provider_version`, `operation`, `evidence_id`, `source_offsets/identifiers`, `coverage`, `unknowns`, `errors`, `elapsed_ms`. Campos indisponíveis ficam explícitos como desconhecidos, **não** são inventados.
5. **Correlacionador e revisor:** cruza achados do REA com os demais módulos e mantém conclusões contraditórias ou incompletas rastreáveis. Não assume equivalência entre pseudocódigo e fonte original.
6. **ZIP portátil:** exporta índice, mapa de shards, relatório humano, evidências normalizadas, hashes, versões/limites e avisos de privacidade após revisão do usuário. Compatível com processamento independente por outras IAs, sem exigir fornecedor proprietário.

## Portabilidade e segurança

- Windows/Linux/macOS: **somente** executores pesados com ferramentas realmente instaladas e licenciadas; estabelecer matriz de suporte por SO.
- Android/iOS: seleção local de arquivo, triagem, aprovações e visualização/sincronização consentida; **não** embutir Node, JDK, Ghidra/JADX e todas as dependências no APK móvel.
- REA usa várias ferramentas externas e pode possuir capacidades de observação de runtime. **A primeira integração deve ser puramente estática e somente leitura**. Qualquer execução, tracing, ADB, rede ou alteração exige autorização e sandbox apropriada.
- Arquivos de terceiros são entrada não confiável. Evitar extração de ZIP por caminho não validado, ataques de descompressão, exfiltração e divulgação de segredos; não enviar conteúdos a provedores externos sem opt-in.
- Respeitar MIT e avisos dos componentes; dependências de licenças incompatíveis não podem ser copiadas indiscriminadamente.
- Não contornar licenças, DRM ou proteção de apps de terceiros.

## Primeiro experimento de integração, **após homologação P7**

- [ ] Declarar contrato versionado `ReaEvidenceAdapterV1` e tipos de erro/cobertura.
- [ ] Executar um APK **sintético e autorizado** em PC, em modo estático somente leitura, verificando pré-requisitos antes.
- [ ] Receber uma única evidência real REA, comparar SHA-256 da amostra e validar o esquema, inclusive lacunas e falhas.
- [ ] Exercitar concorrência limitada com 2 leitores nativos independentes; comparar sequencial vs paralelo (tempo, RAM, resultados).
- [ ] Correlacionar IDs e emitir ZIP portável com manifestos autenticados por hash; reexecutar a verificação no PC, sem LLM.
- [ ] Revisar licenças, segurança de processos, cancelamento, retentativas e dependência de provedor.
- [ ] Só depois disponibilizar controle remoto via Android, como opção separada e consentida.

## Proteção do escopo da etapa atual

**O trabalho corrente continua a P7 visual** (Home, Explorador, Design Studio, referências oficiais, CI API29/API35 e Galaxy A55). Esta RFC **não altera** código de produção Android, packageId, assinatura, versão, publicação OTA ou a `main`. A [issue #17](https://github.com/nego001/ReaDroid-Native/issues/17) continua registrando o backlog multiagente/distribuído; a [issue #11](https://github.com/nego001/ReaDroid-Native/issues/11) e a PR #13 seguem controlando a P7.
