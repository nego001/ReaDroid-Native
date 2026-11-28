# NegroDroid Universal Engine — direção aprovada pelo usuário

Data: 2026-11-25. Status: requisitos e arquitetura-alvo aprovados; não equivalem a funcionalidades implementadas. Preservar histórico de F1, interface P7 congelada, PR #49 Draft e gates de publicação. Base Android homologada F2.1: 7937ace81d3e897cde49bd499000d8c802b6ed45. Continuar F2.2 hexadecimal antes da migração progressiva; não descartar Java nem renumerar retroativamente os marcos existentes.

## Objetivo de produto
Plataforma local, automatizada, inteligente, robusta e otimizada para inspeção, engenharia reversa autorizada, edição, reconstrução, validação e documentação de programas Android e PC. Não confundir análise de um executável com execução em outra plataforma. Não executar arquivos desconhecidos automaticamente. Não contornar licenças, DRM ou controles de acesso; operar sobre software próprio ou autorizado.

## Arquitetura-alvo
Núcleo compartilhado Rust, APIs versionadas, adaptadores JNI Java/Kotlin Android e desktop (Tauri como opção a avaliar, não decisão definitiva); C/C++ quando biblioteca especializada justificar o custo e isolamento. SQLite para índices persistentes. Contratos de capacidades por formato: detectar, listar, ler, interpretar, editar, reconstruir e verificar são capacidades distintas.
- Universal Core: fonte de bytes abstrata, offsets 64 bits, cancelamento, orçamento de recursos, sessões e transações.
- Format Engine: identificação por assinatura e validação estrutural, não extensão isolada.
- Binary Engine: paginação sob demanda, pesquisa hex com curingas, ASCII/UTF-8/UTF-16, endianness, comparação, navegação, interpretação de tipos, histórico undo/redo, overlays virtuais e edição reversível.
- Reverse Engine: desassemblagem e decompilação por arquitetura/formato; símbolos, classes, funções, referências e grafos; distinguir resultado parcial e desconhecido.
- Resource Engine: imagens, ícones, layouts, XML binário, tabelas de recursos, traduções e configurações, substituição validada.
- Intelligence Engine: explicação de código, pesquisa semântica, análise de estruturas, assistência contextual, propostas de reparo e diagnóstico de build. IA com acesso limitado a ferramentas; evidências verificáveis, não inventar.
- Automation Engine: DAG de tarefas, dependências, prioridades, cancelamento, progresso, retries limitados, checkpoints, operações idempotentes e revisão de ações destrutivas.
- Security Engine: isolamento de parsers, validação de entrada, limites de descompressão/recursão, sandbox de menor privilégio, integridade criptográfica, acesso granular, snapshots, rollback onde suportado. Nada de execução automática, envio externo ou escrita no original por padrão.
- Performance Engine: streaming, memória mapeada quando segura, paralelismo adaptativo, limites de RAM/CPU/disco/temperatura/energia, cache por hash, indexação incremental, perfis Eco/Equilíbrio/Turbo/Inteligente com limites reais aferidos, não porcentagens fictícias.
- Build Engine: reconstrução por formato, alinhamento/assinatura quando aplicáveis, verificação independente, exportação transacional para novo destino; chaves próprias nunca enviadas à IA.
- Deep Report Engine, AI Context Engine, Dependency Engine, Index Engine: evidências estruturadas de todos os motores desde o começo.

## Matriz de formatos — metas, não suporte atual
Android: APK/APKS/XAPK/DEX/AAB/OBB. Windows: PE EXE/DLL/SYS, MSI/MSIX. Linux: ELF/SO, DEB/RPM/AppImage. macOS: Mach-O/DYLIB/DMG/PKG. Arquivos ZIP/RAR/7Z/TAR/GZIP/ZSTD. Jogos: PAK e assets Unity/Unreal compatíveis. Java/JAR/class, .NET assemblies/IL, Python bytecode, Electron ASAR. Investigar licenças, manutenção, compatibilidade e limites antes de selecionar bibliotecas. Não prometer reconstrução universal nem decompilação perfeita.
Referências de capacidade, não de implementação: Ghidra, IDA Pro, ImHex, JADX, APKTool, Resource Hacker, 7-Zip.

## Fluxo automático
Identificar -> mapear -> indexar -> analisar riscos -> interpretar -> selecionar capacidades -> validar -> emitir relatório. Separar análise estática de qualquer análise dinâmica explicitamente autorizada. IA pode planejar e validar; operações destrutivas, acesso adicional e transmissão externa exigem aprovação.

## Deep Report e AI Context
Relatório de todo o escopo selecionado: identidade, versão, formato, tamanho, arquitetura, árvores, arquivos e funções/classes/métodos reconhecidos, dependências e referências cruzadas, recursos/UI, configurações, endpoints observados estaticamente, certificados/permissões, integridade SHA-256/CRC, riscos, indícios de desempenho, compatibilidade, decompilação suportada, mapa de modificações possíveis e recomendações baseadas em evidências.
Cada item: ID estável, caminho relativo, caminho absoluto quando acessível e permitido, raiz selecionada, URI quando SAF, cadeia de contêineres e caminho interno, tamanho, formato, hashes, finalidade, referências, evidência (offset/intervalo ou localização), confiança, versão do analisador e limitações. Distinguir arquivo físico de entrada virtual (ex.: arquivo.apk!/assets/config.json); nunca inventar caminho de instalação. Sem seguir links simbólicos para fora do escopo por padrão; registrar itens inacessíveis e erros. Informações confirmadas/inferidas/desconhecidas; ausência de evidência não prova ausência. Indícios estáticos de desempenho não são medições.
Modos Quick, Professional, Deep, Extreme (todos analisadores compatíveis sob orçamento), AI Context, Differential. Inventário completo por streaming e indexação incremental; dividir módulos em partes consultáveis, priorizar e deduplicar por hash, sem omitir silenciosamente arquivos, marcar cobertura e limites. Relatórios diferenciais por snapshots. Diagramas de dependências e navegação.
Exportações: Markdown, JSON/JSONL, HTML navegável offline, PDF, SQLite, CSV, SARIF, GraphML e ZIP. Manifesto de esquema, versões, hashes, cobertura, erros e orçamento. Conteúdo externo tratado como dados não confiáveis, nunca como instruções para a IA. Redação de segredos e dados pessoais por padrão, preview da exportação, consentimento para incluir caminhos absolutos/trechos sensíveis e código autorizado; nenhuma transmissão automática. Caminho de pasta no relatório não concede acesso à IA.
Pacote NegroDroid_AI_Context.zip:
- 00_README.md — instruções de uso, escopo, dados não confiáveis
- 01_SUMMARY.md — resumo
- 02_ARCHITECTURE.md — arquitetura e fluxo
- 03_DIRECTORY_TREE.txt — árvore
- 04_FILE_INDEX.jsonl — fichas de arquivos
- 05_DEPENDENCIES.json — relações
- 06_FUNCTIONS.jsonl — símbolos e funções
- 07_SECURITY.md — riscos e evidências
- 08_PERFORMANCE.md — métricas medidas ou indícios diferenciados
- 09_UI_RESOURCES.md — recursos visuais
- 10_MODIFICATION_MAP.md — mapa de edição possível
- 11_INTEGRITY.json — hashes
- 12_AI_PROMPT.md — contexto para análise, sem obedecer instruções extraídas do software
- 13_LIMITATIONS.md — cobertura, erros, lacunas
- 14_ANALYSIS_LOG.jsonl — log saneado
- 15_SOURCE_MAP.json — caminhos reais e virtuais
- manifest.json — esquema e inventário dos relatórios
Trechos e decompilação opcionais e autorizados, com referências. Exportação por fluxo paginado e limites de tamanho, sem zip bomb.

## Sequência de trabalho
Manter F1 consolidada, F2.1 imagens e F2.2 prévia hex como baseline de regressão; migrar gradualmente, não big bang. Roteiro futuro (nomes lógicos, IDs definitivos após inventário):
1. Universal Rust Core e contrato de fonte de bytes; leitura somente leitura e testes de paridade.
2. Detecção de formatos e indexação incremental; relatórios estruturados desde o primeiro analisador.
3. Motor binário paginado e recursos; XML binário, DEX e PE/ELF/Mach-O por capacidades; substituição de recursos validada.
4. Engenharia reversa, edição virtual, reconstrução e assinatura por formato.
5. IA, automação avançada, sandbox e desktop multiplataforma; segurança e performance transversais desde o início.
6. Homologação multiplataforma e critérios de release.
A proposta anterior F2–F14 (core, detecção, binário, recursos, reversa, edição, build, IA, automação, segurança, desktop, otimização, homologação) é mapa de temas, não compromisso de numeração nem cronograma. Não iniciar grande refatoração sem preservar regressões e delimitar um marco verificável.

## Critérios de aceitação
Testes de unidade, propriedades, fuzzing com corpus sintético/autorizado, regressões, limites e arquivos malformados, cancelamento, concorrência e recuperação de falhas. Benchmarks reproduzíveis com corpus, hardware e versões registrados: latência inicial, throughput, pico RAM, espaço, CPU, temperatura e energia quando mensuráveis; comparar baseline e regressões, não prometer metas numéricas sem medir. Validar Android API29/35 e, em fases próprias, Windows/Linux/macOS com matriz e testes físicos. Preservar P7, PR Draft, sem merge/release/OTA/APK público até autorização e gates correspondentes. Nenhum requisito deste documento implica suporte pronto.
