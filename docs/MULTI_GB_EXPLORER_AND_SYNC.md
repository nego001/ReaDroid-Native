# NegrescoDroid — Explorador multi-GB e sincronização de projetos

> Especificação de produto e arquitetura, 19/10/2026.
> Status: **planejamento**, não funcionalidade disponível. Base Android primeiro;
> Windows e Linux com REA na fase posterior. Tarefas: [#2](https://github.com/nego001/ReaDroid-Native/issues/2),
> [#3](https://github.com/nego001/ReaDroid-Native/issues/3),
> [#4](https://github.com/nego001/ReaDroid-Native/issues/4).

## 1. Escopo da sincronização

- Um **projeto NegrescoDroid** inclui identificador UUID, tipo e hashes das entradas
  originais, revisões do plano de alterações, descritores de recursos, notas,
  relatório de análise e índice de arquivos. O conteúdo original continua
  imutável; alterações são descritas como revisões ou arquivos derivados.
- **Todos os projetos no workspace** podem sincronizar automaticamente após o
  usuário ativar a função e selecionar essa política. Não examinar nem sincronizar
  todo o aparelho/PC, contas Google/GitHub, dados de outros aplicativos ou pastas
  sem consentimento específico.
- Três opções: (1) **somente local** (padrão), (2) **sincronizar projetos** (metadados,
  relatórios, revisões e notas; binários pesados não enviados), (3)
  **sincronizar também arquivos de origem/derivados** (permissão explícita por
  projeto ou política escolhida, estimativa de armazenamento e tráfego).
- Controles: sincronização automática/pausada, usar só Wi-Fi, criptografia,
  fila offline, progresso, limites de dados e armazenamento, dispositivo
  vinculado, política de conflitos, exclusão local vs remota.
- Windows e Linux podem abrir um workspace compartilhado ainda que não possam
  executar uma função específica do Android. Não tentar aplicar mudanças a
  formatos indisponíveis nem executar binários que foram sincronizados.

## 2. Segurança e arquitetura de sincronização

- **Offline-first** e armazenamento local estruturado, com journal/transações,
  formato do workspace versionado e migrações reversíveis.
- **E2EE por objeto** com chave de projeto e chaves derivadas para chunks
  mediante protocolo revisado. Criptografia autenticada (AEAD), verificação de
  integridade e autenticidade de cada revisão, replay/cross-project prevention,
  quotas e cancelamento. Não reutilizar diretamente chaves não exportáveis
  de Android Keystore em Windows ou Linux. Projeto de recuperação/pareamento
  de chaves **antes** da sincronização real; nunca chave compartilhada no código.
- Provedor/back-end ainda **não definido**. Não conectar contas nem fazer
  upload sem consentimento explícito.
- Transfers multipart/chunking, retomada após queda de conexão, deduplicação
  somente quando segura para o desenho E2EE, limites de memória e tráfego,
  hashes finais após remontar em local temporário.
- Conflitos geram **revisões paralelas**, sem sobrescrever silenciosamente.
  Comparação de diferenças, escolha consciente do usuário, histórico e rollback.
- Sem enviar APKs, EXEs, arquivos internos, segredos, resultados ou logs a IA
  ou a servidor terceiro fora da sincronização autorizada; sincronizar não
  significa executar, instalar ou modificar arquivos remotamente.
- Verificação de segurança e teste de falhas: perda/revogação de acesso,
  repetição de chunks, arquivos truncados, servidor hostil, versões
  incompatíveis, expiração de autenticação, despareamento, exclusão e restauração.
- Não apresentar o sistema como nível Bitwarden ou superior sem auditoria
  independente de protocolo, implementação, armazenamento e UX.

## 3. Explorador de arquivos de vários GB

- Explorar tanto **diretórios locais autorizados** quanto **conteúdo interno
  de APK/ZIP64 e outros formatos suportados**. No Android, usar SAF sem
  permissões indiscriminadas; no desktop, APIs nativas.
- Navegação: pastas, breadcrumbs, busca, filtros, favoritos, ordenação, seleção
  múltipla, informações, abas/projetos e permissões revogáveis.
- **Virtualização de UI, busca/indexação paginada em disco, leitura em fluxo,
  amostras/preview limitados e canceláveis**. Não materializar todo o arquivo
  em memória, não instanciar um componente visual por entrada do ZIP.
- Etapas de operações: leitura, SHA-256, inspecionar ZIP/PE/ELF, comparar;
  depois cópia/movimentação/extração/edição com fluxo transacional, destino
  separado e confirmação. Operações grandes precisam de progresso real,
  pausa/cancelamento e espaço reservado.
- Tratamento seguro de ZIP bombs, contagens exageradas, tamanhos desconhecidos,
  paths inválidos, symlinks e nomes duplicados. Não executar EXE/ELF/APK
  desconhecido automaticamente. Sem extrair arquivos fora do destino aprovado.
- Importação para análise de arquivo multi-GB exige acesso aleatório ou
  índice próprio em disco e capacidade documentada por dispositivo. Arquivos
  com extensão .xapk/.apks/split e OBB precisam de tratamento específico,
  não devem ser presumidos APK monolítico.
- O limite Android atual de APK **1 GiB**, índice **150 mil entradas** e
  total descompactado **2 GiB** continua até haver implementação e testes;
  não simplesmente elevar constantes.

## 4. Marcos verificáveis

1. **Base Android / P0:** modelo local de workspace versionado e índice
   incremental de diretórios, preview limitado e hashes por streaming.
2. **Infra multi‑GB / P1:** testes com arquivo sintético de 2 e 5 GiB,
   cancelamento, quota, pouco armazenamento e muitas entradas; medir RAM,
   latência e estado da UI no Samsung e em emuladores.
3. **Persistência/P2:** revisões imutáveis, integridade de originais, projetos
   restauráveis sem depender somente do cache e sem quebrar o cofre atual.
4. **Protocolo sync / P3:** proof-of-concept local, depois E2EE e sincronização
   opcional de metadados, testes adversariais e revisão de segurança.
5. **Arquivo pesado na nuvem / P4:** upload criptografado resumível com permissão
   explícita e checagem SHA-256 após download.
6. **Windows e Linux / P5:** integrar motor de workspace, explorador e sync
   aos executáveis PE/ELF e REA, mantendo sistemas de chaves independentes.

### Critérios de aceitação (não executados ainda)

- Uma pasta de **100 mil itens** navega com lista virtualizada e busca
  paginada sem travar, com memória monitorada.
- Arquivo de **5 GiB** produz SHA-256 por streaming com RAM limitada;
  cancelamento deixa o original idêntico.
- Um projeto criado Android pode ser visto em Windows/Linux sem expor
  automaticamente APK/EXE privados.
- Conflitos offline em dois dispositivos mantêm **duas revisões recuperáveis**.
- Transferência cifrada multi-GB pausada/resumida verifica hashes e versão;
  nenhum terceiro vê a chave ou o conteúdo em claro.
- Falta de espaço, provedor SAF que não fornece tamanho, revogação de
  permissões e perda de chave têm falhas seguras e mensagens compreensíveis.

## 5. Limites / ordem do projeto

- **Agora:** continuar base Android, correções funcionais, recuperação,
  explorador e homologação física. Não parar isso por versões desktop.
- **Depois:** Windows/Linux focados em EXE/PE/ELF, com [REA](https://github.com/morluto/rea)
  como ferramenta auxiliar de análise e sem prometer editor universal.
- Redesenho visual dos diálogos do editor separado na [issue #1](https://github.com/nego001/ReaDroid-Native/issues/1).
- Nenhum backend, conta, credencial, chave, sincronização ou leitura multi-GB
  ilimitada foi criado com este documento.
