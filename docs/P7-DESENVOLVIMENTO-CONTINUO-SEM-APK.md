# NegrecoDroid P7 — desenvolvimento contínuo sem APK a cada commit

**Data:** 20/10/2026  
**Origem:** pedido do proprietário para **gerar APK somente em atualizações grandes**.  
**Situação:** desenvolvimento ativo na branch `feature/p7-negrecodroid-visual-foundation`; versão de teste publicada mais recente continua a **Preview 12**. Não elevar `versionCode` nem publicar mais uma preview por correções isoladas.

## Política técnica aplicada

- `.github/workflows/android.yml`: somente `workflow_dispatch` e opção booleana **`major_update_approved`** (padrão `false`) permitem gerar/publicar um APK QA. Foram removidos `push` e `pull_request` deste workflow, a publicação automática do APK debug e as condições legadas ligadas a branches.
- O workflow de instalação aprovado produz **um único artefato QA de marco**, assinado para testes e separado da aplicação principal (`com.readroid.app.qa`).
- `.github/workflows/p7-brand-validation.yml`: continua testando Android 10/API29 e Android 15/API35, mas **não executa `assembleQa` nem publica um instalador** nas alterações rotineiras. O pacote debug de instrumentação é compilado internamente porque os testes Android precisam executar o código real.
- `tests/test_major_apk_policy.py` verifica automaticamente o bloqueio; `.github/workflows/static-check.yml` executa esse teste em `Source checks`.
- Outros workflows históricos de releases V3, caso usados no futuro, devem ser submetidos às mesmas condições de marco. Não usar release tags ou fluxos antigos para contornar esta política.

## Desenvolvimento acumulado após Preview 12, sem criar APK novo

### Explorador (UI nativa, não imagem)

- Novo `P7ExplorerEntryRow`: ícone vetorial verdadeiro de pasta/documento, nomes e metadados reais em componentes separados, marcador de arquivo editado e menu `⋮` independente com área de toque acessível.
- `ExplorerView` passa a usar o componente tanto no modo JSON legado quanto no índice SQLite paginado. Deixa de desenhar pastas/arquivos com strings multilinhas e caracteres de triângulo como interface.
- Um toque na linha da pasta entra naquela pasta. No menu contextual: **Abrir pasta** ou **Copiar caminho**.
- Um toque na linha do arquivo ou em seu menu abre ações verdadeiras: **Ver texto**, **Planejar edição** apenas quando suportado, **Detalhes técnicos** e **Copiar caminho**.
- Os metadados mostrados no subtítulo são **tipo, tamanho e status de edição**. Não inventar data, contagem de filhos, miniaturas ou resultados ausentes do ZIP/SQLite.
- A edição continua seguindo as regras `EditPlan.isEditable`, sem desbloquear edição perigosa de XML binário ou outros formatos não suportados.
- Instrumentações atualizadas: `IndexedExplorerViewInstrumentedTest`, `P7ExplorerChromeInstrumentedTest` e novo `P7ExplorerEntryRowInstrumentedTest`; P7 CI API29/35 acompanha as regressões.

## Quando será gerado o próximo APK

Somente quando houver um conjunto significativo de melhorias funcionais/visuais pronto para testar como uma atualização maior, com:

1. Novidades agrupadas e changelog de release substantivo.
2. Compilação e testes instrumentados Android 10/15 aprovados para o **mesmo commit**.
3. Capturas da Home, Explorador e Design Studio revisadas contra a referência original.
4. Nenhuma regressão conhecida em SAF, planos de edição, segurança/assinatura e projetos recentes.
5. Disparo explícito e confirmado do workflow manual de geração, com artefato, SHA-256 e versão registrados.

**Status atual:** implementação e testes em andamento; nenhuma nova release APK autorizada nesta etapa. `main` preservada, PR #13 continua em rascunho.


## Continuação P7 — aplicação real dos catálogos e ícones diferenciados

### Design Studio: opções que realmente aplicam

- [x] Clicar nas miniaturas de tema, layout ou preset agora abre o diálogo de **confirmação da aplicação** usando `P7ThemeCatalog` e `P7VisualCatalog`, e não apenas desloca o check visual.
- [x] `Cancelar` ou usar o botão **Voltar** restaura a seleção efetivamente salva, evitando mostrar como ativo um tema não aplicado.
- [x] Erros de persistência também restauram o destaque da escolha real, sem alterar APK, cofre, assinatura ou plano de edições.
- [x] O script `tools/p7_design_smoke.py` verifica no emulador a confirmação ao tocar numa miniatura e a recuperação visual após cancelar.
- [ ] A auditoria pixel a pixel das miniaturas oficiais e os editores completos de ícone/logo seguem pendentes.

### Explorador: ícones dependentes do tipo real

- [x] Novo vetor nativo `ic_p7_image.xml` para PNG/WebP/JPG/JPEG/GIF/BMP.
- [x] `P7ExplorerEntryRow.iconResource` diferencia pasta, imagem, XML/Smali/código, DEX/biblioteca/ARSC e documento genérico.
- [x] O ícone é escolhido **pela extensão do arquivo listado**, mas o app nunca executa nem carrega recursos arbitrários do APK nessa operação. Fallback seguro para arquivos desconhecidos.
- [x] `P7ExplorerEntryRowInstrumentedTest` valida as escolhas de ícones e as ações contextuais reais.

### Economia de GitHub Actions

- [x] Concurrency `p7-brand-${{ github.event.pull_request.number || github.ref }}` com `cancel-in-progress: true`: quando chega novo commit, os emuladores de commits ultrapassados são cancelados, preservando a execução mais recente.
- [x] O workflow de APK instalável continua **manual e condicionado à confirmação de atualização grande**.
- [ ] Resultado de CI da revisão atual e inspeção de screenshots deverão ser adicionados após os testes, sem declarar antecipadamente que passaram.

**Nenhum APK QA novo gerado, nenhuma atualização automática de versão.** A última versão instalável deliberada permanece a Preview 12; estas melhorias são código-fonte acumulado para um marco maior.


## CHECKPOINT P7 — ideias futuras não substituem esta etapa (20/10/2026)

**Solicitação do proprietário:** ele deseja apresentar novas ideias, mas **não quer que o desenvolvimento atual seja perdido, substituído ou considerado encerrado**. Este registro fixa a continuidade da P7 antes de organizar novas propostas.

**Referências de continuidade:**
- Branch ativa: `feature/p7-negrecodroid-visual-foundation`.
- Último commit de implementação antes deste checkpoint: `e0ffe4b3c100ed631678296ac64a4d4e5ad023c4`.
- Pull request de implementação [#13](https://github.com/nego001/ReaDroid-Native/pull/13), em rascunho.
- Issue [#11](https://github.com/nego001/ReaDroid-Native/issues/11), com a referência visual 1:1 aprovada para **Home, Explorador e Design Studio**.
- Último APK distribuído ao usuário: **P7 Preview 12**. A partir dele, código e testes seguem normalmente, mas **um novo APK só deve ser gerado numa atualização grande aprovada**, nunca a cada pequeno commit.

**Já desenvolvido e que não deve regredir:** Home com mascote da referência, cartões e navegação; histórico seguro SAF de projetos reais e ícones extraídos dos APKs; Explorador com índice SQLite, chips, lista nativa com ações reais, segurança de planos de edição; Design Studio com galerias, seleção/aplicação de temas, layouts e presets, reversão ao cancelar; Logo Studio com prévia do nome/subtítulo salvos. Preservar também os recursos existentes P0/P1: importação SAF, segurança, edição controlada, exportação, verificações e recuperação.

**Pendências explícitas (NÃO marcar como concluídas):**
1. Comparação visual completa e aprovação **1:1** das três telas, incluindo miniaturas, proporções, ícones, acabamento e avaliação em Galaxy A55.
2. Catálogo avançado e ferramentas de criação de ícones/logos que ainda são parciais.
3. Continuação de testes integrados com APKs reais, regressões e validação do marco antes de qualquer nova distribuição instalável.
4. Homologar o CI Android 10/15 da revisão atual, que deve ser verificado pelo resultado final do GitHub Actions.

**Regra para novas ideias:** registrar as ideias novas em seção ou issue própria como `BACKLOG / NOVAS IDEIAS`, sem alterar critérios de aceite da P7 ou apagar os itens pendentes. Só reordenar prioridades quando o proprietário solicitar; não dar merge na `main` nem produzir APK por conta própria. Quando o usuário pedir para retomar, continuar a partir deste checkpoint e do HEAD atual da branch.

