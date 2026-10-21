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



## P7 — Criador de Ícones nativo (trabalho acumulado, sem APK)

**Origem:** conclusão gradual do Design Studio 1:1, sem iniciar a P8 nem abandonar o aceite visual da Home e do Explorador.

### Implementado no código-fonte

- [x] Novo `P7IconWorkshop`: oficina local aberta na aba **Ícones** e no cartão **Criador de Ícones**, com prévia nativa criada por `Canvas`.
- [x] Paleta com cinco cores, quatro desenhos originais (escudo, código, pasta e estrela) e três formatos (arredondado, circular e quadrado). Opções de cor roláveis para caber em telas pequenas.
- [x] Renderização determinística de ícone **PNG 512 × 512** com transparência real fora da forma selecionada.
- [x] Exportação pelo seletor `ACTION_CREATE_DOCUMENT` do Android; **não solicita acesso irrestrito ao armazenamento** e não escreve em arquivos do projeto ou altera o ícone instalado.
- [x] `MainActivity` guarda temporariamente os três índices da escolha do usuário durante o fluxo do seletor, inclusive ao girar a tela, sem armazenar imagem temporária privada desnecessária.
- [x] Novo `P7IconWorkshopInstrumentedTest` verifica dimensões, assinatura PNG, mudança real de pixels entre estilos, transparência, rejeição de esquema `file:` e acesso ao editor a partir da aba Ícones; execução obrigatória no CI Android 10 e 15.
- [ ] Revisão final de interação e screenshot em Galaxy A55 ainda pendente. A ferramenta **não é um editor vetorial completo** com importação de SVG e camadas; este é o primeiro compositor de ícones autêntico.

### Estado da integração

- Nenhum APK QA produzido e `versionCode` permanece o da última prévia disponibilizada.
- `main` preservada, [PR #13](https://github.com/nego001/ReaDroid-Native/pull/13) permanece em rascunho.
- A [Issue P8 #14](https://github.com/nego001/ReaDroid-Native/issues/14) mantém separadamente todos os laboratórios, IP Locator e investigações futuras; **a P7 continua prioritária**.
- Homologar os testes do **HEAD exato**, não reutilizar resultados da Preview 12 nem declarar 1:1 visualmente concluído por somente compilar.


## Correção P7 — botão de exportação no Criador de Ícones (21/10/2026 UTC)

**Falha reproduzida:** a execução [39535239581](https://github.com/nego001/ReaDroid-Native/actions/runs/39535239581) concluiu 24/24 testes instrumentados no Android 10, mas o smoke visual do Design falhou nos Androids 10 e 15: `Exportar PNG` não aparecia na hierarquia acessível do diálogo. Home e Explorador passaram nos dois emuladores. A aprovação dos testes JUnit isoladamente não era aprovação da P7.

**Alteração de código:** a ação primária `Exportar PNG` passa a ser um `Button` nativo, com texto, descrição acessível, estado clicável e altura de toque, posicionado logo após a prévia dentro do editor. Removido o botão positivo redundante do rodapé do `AlertDialog`, mantendo `Fechar` e o fluxo original `ACTION_CREATE_DOCUMENT` com autorização SAF. O editor continua local, sem alterar APK, projeto, preferências ou ícone instalado.

**Regressão acrescentada:** instrumentação verifica o botão real e seu nome acessível. `tools/p7_design_smoke.py` exige uma única ação clicável no Android 10 e 15, e salva `p7-icon-workshop-android-<api>.png` antes de cancelar; o workflow guarda essa imagem mesmo em caso de falha posterior.

**Status:** alteração proposta na branch P7; CI Android 10/15 e capturas do commit exato devem ser conferidos antes de marcar aprovado. Sem novo APK, sem versão nova, sem merge para `main`, sem iniciar a P8.

## P7 — Logo Studio nativo com exportação PNG (21/10/2026)

**Problema real:** a aba Logotipo antes mostrava apenas a prévia da identidade visual salva e permitia editar as preferências; não havia exportação nativa de logotipos.

**Implementação:** novo `P7LogoWorkshop` com compositor Android Canvas, prévia em tempo real, campos de nome e subtítulo (pré-carregados da identidade salva), quatro cores, fundo transparente ou OLED, nome central e monograma. Exportação PNG **1024×512**, usando exclusivamente o seletor Android `ACTION_CREATE_DOCUMENT`. A ação foi integrada à aba Logotipo e ao cartão Logo Studio da aba Temas.

**Segurança:** edição temporária não altera `display_name`, `display_subtitle`, ícone instalado ou arquivos do projeto. A identidade exibida no aplicativo continua sendo modificada somente pela função separada `Editar nome e subtítulo`. Nome e subtítulo têm limites de tamanho/caracteres válidos; destino precisa ser URI `content:`. A escolha de exportação é mantida na recriação da Activity durante o seletor SAF.

**Regressões:** novos testes instrumentados conferem PNG, transparência, mudanças de pixels por cor/fundo, rejeição de dados inválidos/URI não autorizada e acesso à ferramenta. Smoke de Design Studio abre o editor real nos Androids 10/15, verifica prévia e ação acessível, salva uma captura `p7-logo-workshop-android-<api>.png` e fecha sem alterar preferências.

**Aceite ainda pendente:** executar a matriz Android 10/15 no novo HEAD e revisar imagens contra a referência. Sem APK de distribuição, sem versionCode novo, sem merge na main. P8 continua backlog separado.

## P7 — revisão OLED real e acessibilidade do Explorador (21/10/2026)

A matriz do commit `b9f8f0e4` concluiu com sucesso: [GitHub Actions 39537487473](https://github.com/nego001/ReaDroid-Native/actions/runs/39537487473) aprovou **27/27 testes instrumentados no Android 10 e 27/27 no Android 15**, além dos smokes de Home, Explorador e Design Studio e imagens do Criador de Logos. Source checks e OTA aprovados.

**Correção funcional do logo:** a opção `OLED preto` exportava um retângulo azul-marinho arredondado sobre transparência, apesar do nome. Passou a exportar **preto #000000 sólido no PNG inteiro**, com alfa 255 nos cantos; a opção Transparente continua com exterior de alfa 0. A prévia local mostra um xadrez discreto quando o fundo é transparente, sem contaminar o PNG exportado. Novas afirmações por pixel nos testes previnem retorno do azul-marinho falso.

**Explorador acessível:** controles nativos de voltar, menu, revisar plano, filtros avançados, chips rápidos, trilha de pastas e menu contextual de cada arquivo foram ajustados para alvos de toque de **48 dp no eixo pertinente**, sem mudar callbacks, planos de edição, pesquisa ou índice SQLite. Testes de UI foram ampliados para conferir dimensões reais dos controles principais.

**Pendente:** resultado da próxima matriz Android 10/15 no HEAD exato e inspeção visual manual; screenshots não são, sozinhos, homologação 1:1. Continuam proibidos APK de distribuição automático, incremento de versionCode, merge na main ou antecipação da P8.

## P7 — continuidade do Explorador após rotação (21/10/2026)

**CI anterior:** [execução 39539885544](https://github.com/nego001/ReaDroid-Native/actions/runs/39539885544) concluiu com sucesso em Android 10 e 15, além de [Source checks](https://github.com/nego001/ReaDroid-Native/actions/runs/39539885632) e [OTA](https://github.com/nego001/ReaDroid-Native/actions/runs/39539885555) aprovados.

**Defeito identificado:** o `ExplorerView.restoreBrowseState` validava a pasta ativa apenas pelos caminhos do JSON de fallback. Em arquivos grandes cujo índice SQLite traz centenas de pastas, a lista JSON pode estar parcial, e uma pasta profunda real era indevidamente descartada na recriação da Activity/rotação.

**Correção:** `ApkDiskIndex.containsDirectory` verifica a linha exata de diretório (incluindo pastas vazias) em SQLite somente leitura e valida a origem por tamanho + data modificada, sem ler o conteúdo do APK. O Explorador agora restaura diretórios válidos presentes no índice, mesmo quando ausentes do fallback. Caminhos absolutos, com travessia ou inexistentes voltam à raiz de modo seguro. Nomes legítimos contendo `..` como parte do nome não são rejeitados automaticamente; a validação opera por segmentos.

**Regressão:** `IndexedExplorerViewInstrumentedTest` criou fixture ZIP com 145 arquivos, fallback parcial limitado a 120, pasta aninhada fora do fallback e pasta explicitamente vazia. Verifica navegação real, restauração, diretórios inexistentes e tentativas de path traversal nas APIs 29/35.

**Pendente:** validar a compilação, instrumentação Android 10/15 e evidências de navegação no commit exato antes de homologar esta correção. Mantidas as regras sem APK novo, sem versionCode, sem integração à main; P8 segue backlog.

## P7 — filtros Editáveis/Alterados em índice completo (21/10/2026)

O commit anterior `123d05b6` passou nos dois emuladores: **28/28** testes por plataforma, e smokes de Home, Explorador, Design e exportações visuais, na [matriz 39541545036](https://github.com/nego001/ReaDroid-Native/actions/runs/39541545036).

**Falha de fidelidade funcional detectada:** os filtros avançados `Editáveis` e `Alterados` ignoravam o SQLite completo e percorriam apenas o JSON de fallback, potencialmente parcial. Isso ocultava arquivos editáveis/alterados além da amostra de 120 entradas.

**Correção:** `ApkDiskIndex.page` ganhou predicados SQL indexados para extensões textuais autorizadas (`EditPlan.isEditable`), preservando pastas navegáveis. `ApkDiskIndex.pageChanged` consulta o plano temporário contra linhas reais do índice em modo somente leitura, ignora caminhos antigos/inexistentes, agrupa pastas e pagina a até 120 entradas com metadados verdadeiros, sem carregar conteúdos. `ExplorerView.currentIndexPage` integra ambos sem alterar o fluxo de preview/edição, o plano ou a assinatura.

**Testes:** fixture ZIP com 145 arquivos, JSON apenas das primeiras 120, edição na última página e um caminho de edição inexistente. Verifica que `Alterados` encontra o item real mas nunca fabrica a pasta `ghost/`; `Editáveis` oferece segunda página e exclui binários. Cobertura SQL de extensões, caixa alta e subpastas incluída em `P7IndexedFiltersInstrumentedTest`.

**Pendente:** executar matriz e revisar resultados deste commit exato; resultado anterior não homologa automaticamente esta mudança. Mantidas as restrições sem APK de distribuição, sem versionCode, sem merge na main, P8 separada. UI 1:1 ainda aguarda referências oficiais e homologação física.

## P7 — aviso explícito quando índice SQLite não está disponível (21/10/2026)

**Risco:** quando a validação de tamanho/data ou a leitura do índice falhava, o Explorador substituía silenciosamente o índice pelo JSON de fallback, que pode conter apenas as primeiras entradas. Isso apresentava uma listagem possivelmente parcial como se fosse a navegação completa do APK.

**Correção:** `ExplorerView` mostra agora um aviso de acessibilidade e texto visível: "Índice indisponível. A lista pode estar incompleta. Reabra o APK para analisar novamente." O contador da lista passa a indicar `Prévia possivelmente incompleta`. O aviso só surge quando um índice esperado está ausente ou falha; não aparece em uso normal sem índice. Ao iniciar uma nova sessão `setFiles`, o alerta é limpo. Nenhum arquivo, plano de edição ou preferência é modificado pelo mecanismo de fallback.

**Regressão:** `IndexedExplorerViewInstrumentedTest.staleIndexShowsPartialWarningWithoutLosingEdits` cria ZIP sintético de 145 entradas, limita o fallback a 120, constrói índice e depois altera apenas o ZIP temporário para invalidá-lo. Verifica alerta visível, honestidade do contador, preservação do plano temporário e limpeza do aviso na nova sessão.

**Pendente:** compilar e validar o novo commit nas APIs 29 e 35. A P7 continua draft, sem merge na main, APK de distribuição ou versionCode. As referências visuais 1:1 e a homologação física continuam pendentes.

## P7 — identificação e remoção de filtros avançados (21/10/2026)

**Checkpoint:** revisão `dc477f0e` concluiu [matriz Android 10/15](https://github.com/nego001/ReaDroid-Native/actions/runs/39542835377) com **31/31 testes instrumentados em cada API**, smokes de Home/Explorador/Design e código-fonte/OTA aprovados.

**Defeito de usabilidade corrigido:** após selecionar `Editáveis`, `Alterados` ou outra categoria avançada, nenhum chip da barra rápida ficava selecionado e o botão avançado exibia apenas um ícone, sem indicar qual filtro permanecia ativo.

**Solução:** a barra de cinco chips e o botão avançado mantêm a estrutura aprovada; um chip complementar de 48 dp aparece somente com categoria avançada, exibindo `Filtro ativo: [categoria] • Toque para remover`. O chip tem rótulo de acessibilidade específico (`Remover filtro [categoria]`) e limpa a seleção para `Todos`, preservando a pesquisa e o plano temporário e reiniciando apenas a paginação. Filtros rápidos ocultam automaticamente essa faixa.

**Teste:** `P7ExplorerChromeInstrumentedTest` agora cobre tanto `Editáveis` como `Alterados` com seleção acessível, visibilidade e remoção funcional, retornando ao conjunto completo de entradas.

**Ainda não validado neste commit:** nova matriz Android APIs 29/35 e avaliação visual manual. Sem APK de distribuição, versionCode ou merge; P8 permanece separada, fidelidade 1:1 aguarda PNGs oficiais.

## P7 — pesquisa limitada à capacidade segura do índice (21/10/2026)

**Defeito:** `ApkDiskIndex.page()` rejeita consultas acima de 256 caracteres. A pesquisa do `ExplorerView`, porém, aceitava texto sem limite; colar mais de 256 caracteres lançava exceção e fazia o aplicativo abandonar definitivamente o índice SQLite, exibindo somente a prévia JSON resumida. A restauração também tolerava até 512 caracteres e podia reproduzir o problema.

**Correção:** a entrada de pesquisa nativa usa `InputFilter.LengthFilter(256)` e a restauração limita a consulta a 256 caracteres, alinhados ao contrato de `ApkDiskIndex.page()`. O filtro continua preservando pesquisa Unicode sem tocar no APK. A limitação impede uma pesquisa grande de ser erroneamente classificada como índice corrompido.

**Regressão:** `IndexedExplorerViewInstrumentedTest` cola string de 300 caracteres e verifica o corte para 256, ausência de alerta de índice inválido, preservação de busca em arquivo na terceira página (`assets/a300.txt`) e restauração segura da busca. A execução do novo commit ainda depende da matriz Android 10/15.

**Escopo:** P7 apenas, PR draft, `main` intacta, sem APK distribuível nem versionCode, P8 separada. Fidelidade 1:1 e teste no aparelho físico pendentes.

## P7.0 — verificador de integridade das artes oficiais (21/10/2026)

**Bloqueio confirmado:** `design/reference/p7/` ainda não contém os dois mockups PNG aprovados na issue #11. Não é possível declarar conformidade visual 1:1 sem os bytes originais.

**Preparação verificável:** `tools/p7_reference_assets.py` valida os dois nomes fixos, dimensões 1448×1086, chunks/CRC da estrutura PNG, IEND e o SHA-256 exato documentado. Arquivos ausentes, regravados ou danificados resultam em `P7_REFERENCE_BLOCKED` com exit code diferente de zero, sem geração de substitutos. README documenta a inserção dos PNGs oficiais em `design/reference/p7/`.

**Testes automáticos da ferramenta:** `tests/test_p7_reference_assets.py` utiliza apenas PNGs sintéticos pequenos para verificar integridade, dimensões incorretas, adulterações, dados adicionais e exigência dos dois arquivos. `.github/workflows/static-check.yml` executa esses testes, sem tentar homologar como presente uma referência não versionada.

**Pendente:** obter as duas imagens originais do proprietário, confirmar seus hashes e só então integrar comparação 1:1 das capturas reais. A validação do novo commit Android 10/15 e CI ainda precisa ser confirmada. Sem APK distribuível, sem merge na main e sem antecipar P8.

## P7.0 — correção do teste sintético do validador (21/10/2026)

O workflow [Source checks 39548519373](https://github.com/nego001/ReaDroid-Native/actions/runs/39548519373) falhou no teste `test_both_official_files_are_required`: a fixture utiliza um PNG sintético de **3×2**, enquanto o coletor de verificação aplicava implicitamente o tamanho oficial **1448×1086** também a essa fixture. A verificação de integridade propriamente dita e os outros três testes passaram.

**Correção objetiva:** o coletor `check_references` mantém **1448×1086 como padrão imutável para produção** mas recebe uma dimensão explicitamente injetada pelos testes sintéticos. Os dois cenários (uma imagem faltante e as duas presentes) passam a testar somente os PNGs 3×2 sem afrouxar a validação das artes oficiais. Novo commit exige nova execução de Source checks, OTA e emuladores, sem declarar aceite visual 1:1.

## P7.6 — teste real de viewport estreito 320 dp e fonte 130% (21/10/2026)

**Checkpoint anterior:** commit `bdb4828c`, [matriz 39548681956](https://github.com/nego001/ReaDroid-Native/actions/runs/39548681956): Android 10 e 15 aprovados (31/31 cada), smokes de Home/Explorer/Design, Source checks e OTA verdes; testes de integridade das duas referências PNG aprovados com fixtures, mas imagens oficiais ainda ausentes.

**Lacuna:** as capturas de P7 validavam exclusivamente o viewport comum do emulador. A issue #11 exige uso em **320 dp com fonte ampliada**, especialmente cabeçalhos e navegação inferior que não podem desaparecer ou sair da tela.

**Implementação:** `tools/p7_compact_smoke.py` descobre densidade e resolução efetivas via `wm`, aplica temporariamente 320 × 720 dp e fonte Android de 130%, reinicia apenas o aplicativo de QA, confirma cabeçalho visível e cinco abas inferiores com coordenadas na viewport e largura mínima de 48 dp em Home/Arquivos/Design, verifica navegação realmente selecionada e salva três screenshots por API. Em `finally`, restaura exatamente o override anterior de resolução ou o estado físico e o valor original de `font_scale`, reiniciando o app normalmente. Tudo em emulador, sem abrir ou modificar APKs pessoais.

**CI:** `.github/workflows/p7-brand-validation.yml` roda esse smoke depois das evidências normais e inclui `p7-compact-*-android-*.png` nos artefatos; testes Python `tests/test_p7_compact_smoke.py` cobrem extração de estado físico/override, densidades, conversão dp↔px e entradas malformadas.

**Pendente:** compilar/executar nos Androids 10/15, corrigir eventuais falhas de UI ou calibração identificadas. Imagens aprovadas originais e homologação física Galaxy A55 ainda ausentes; não declarar visual 1:1. PR #13 draft, main preservada, sem APK para distribuição e P8 separado.

## P7.6 — alvos de toque e estado acessível das abas do Design Studio (21/10/2026)

**Checkpoint prévio:** commit `05473bd7` passou em [Android 10 e 15, execução 39551315389](https://github.com/nego001/ReaDroid-Native/actions/runs/39551315389): 31/31 testes instrumentados por API, validação 320 dp / 130% em Home/Arquivos/Design, seis screenshots e restauração confirmada do emulador. Source checks e OTA aprovados.

**Falha objetiva:** quatro abas internas do Design Studio tinham hitboxes com altura de apenas **36 dp** (o scroller pai tinha 43 dp). Os controles `Ver todos` tinham **37 dp**, inclusive o contêiner pai, menos que os 48 dp exigidos pelo contrato P7.6. O estado selecionado era indicado visualmente, mas não no rótulo do TalkBack.

**Correção aplicada:** abas internas com 48 dp de altura mínima e explícita, faixa horizontal com 52 dp, selecionabilidade/foco declarados, e `contentDescription` dinâmica `[aba], aba selecionada` ou `[aba], selecionar aba`. Cabeçalhos com `Ver todos` passam para 48 dp sem aumentar limite de paginação nem afetar temas/planos de edição. Não há alteração em APK, assinatura, identidades do projeto ou preferências.

**Teste novo:** `P7NavigationInstrumentedTest.designTabsAndCatalogButtonsMeetMinimumTouchTargets` abre a aba Design de verdade, valida dimensões físicas em dp de todas as quatro abas, foco/descrição para TalkBack, altura do botão de catálogo e do pai; também navega entre abas Ícones e Logotipo para verificar atualização do estado acessível. Matriz Android 10/15 e smoke compacto devem ser confirmados para o commit atual.

**Restrições:** P7 ainda draft, `main` sem merge, sem APK de distribuição e P8 separada. Homologação 1:1 depende das duas artes originais ausentes e de Galaxy A55 físico.

## P7.6 — checagem real de alvos do Design em tela compacta (21/10/2026)

**Problema que motivou a revisão:** o novo commit `cee06523` corrige botões das abas do Design Studio para 48 dp e amplia o controle `Ver todos`, mas a matriz Android anterior (**05473bd7**) não cobre o novo código e não há run novo comprovado no GitHub Actions. A API da PR #13 continuou apontando `05473bd7`, enquanto a ref da branch já estava em `cee06523`; foi confirmada a diferença na própria API GitHub. Não atribuir aprovação da versão anterior à nova.

**Incrementos em commits de conteúdo:** `77a744b3` adicionou `require_accessible_target` ao `tools/p7_compact_smoke.py`. Em 320 dp / 130% de fonte, verifica na hierarquia real de Android que `Temas, aba selecionada`, `Layout, selecionar aba` e `Ver todos: Previews de Temas` são únicos, clicáveis, íntegros dentro da viewport e têm pelo menos **48 dp de largura e altura** usando a densidade real do emulador. Não verifica por aparência desenhada nem usa PNGs falsos. `8099f00c` expandiu `tests/test_p7_compact_smoke.py` com testes unitários de 48 dp exatos, largura/altura insuficientes, corte da viewport, falta de clique, duplicatas e ausência de controle. Todos os testes foram adicionados à matriz existente, ainda dependentes de execução real para serem declarados PASS.

**Sincronização/CI pendente:** uma atualização de conteúdo via GitHub Contents API também moveu a branch, porém a PR/Actions não apresentou novo run na consulta imediata. Antes de declarar verde, confirmar que a PR indexou o HEAD e que Source, OTA e Android API 29/35 realmente rodaram sobre o SHA mais recente. A ausência de run não significa sucesso nem falha técnica da implementação.

**Restrições mantidas:** PR #13 draft, `main` intacta, sem APK de distribuição, sem versionCode nem P8. O aceite visual 1:1 continua pendente dos dois PNGs oficiais e homologação real.

## P7.6 — ajuste pós-CI da altura mínima do Design Studio (21/10/2026)

**Teste real:** commit `8099f00c`, matriz [39613408541](https://github.com/nego001/ReaDroid-Native/actions/runs/39613408541), terminou **failure nas APIs 29 e 35** no caso `P7NavigationInstrumentedTest.designTabsAndCatalogButtonsMeetMinimumTouchTargets`: `Tab minHeight too short: Temas`. Em ambas as plataformas, testes Python auxiliares de viewport passaram e a compilação concluiu; a falha foi na instrumentação do layout, sem inferir sucesso do restante do smoke que não rodou.

**Causa:** `TextView.setMinHeight(48dp)` controla o mínimo do layout de texto, mas o teste consulta `View.getMinimumHeight()`, cuja propriedade independente `View.setMinimumHeight()` não havia sido configurada. A altura explícita em `LayoutParams` já era 48 dp, mas o contrato de acesso nativo continuava incompleto.

**Correção `5027da70`:** `P7DesignStudio.java` agora chama também `setMinimumHeight(dp(48))` em todas as quatro abas internas e em `Ver todos`, preservando o `setMinHeight(48dp)`, `LayoutParams`, foco e descrições acessíveis. Não altera controles de escolha, preferências, exportação nem o plano de edição.

**Validação pendente:** executar o teste instrumentado atualizado + smokes regulares e compactos nas APIs 29/35 no SHA final. O HEAD da PR/Actions estava atrasado em relação ao ref GitHub após commits feitos pelo conector, portanto toda conclusão precisa citar o SHA exato. Nenhum APK de distribuição, merge na main, versionCode ou avanço de P8. Aceite 1:1 segue bloqueado pelas duas referências oficiais e teste físico.

## P7.6 — regressão de densidade após expansão dos alvos (21/10/2026)

**Falha nova observada:** commit `5027da70`, matriz [39614346419](https://github.com/nego001/ReaDroid-Native/actions/runs/39614346419): os **32 testes instrumentados Android 10 terminaram** sem registrar o erro anterior de `minHeight`, mas o smoke `tools/p7_design_smoke.py` falhou com `Missing Design Studio element: Dark OLED`. Os cabeçalhos `Ver todos` + abas tiveram suas áreas reais expandidas para 48dp; essa expansão empurrou o primeiro preset para fora da viewport inicial. No momento do diagnóstico, Android 15 ainda executava. O erro não deve ser resolvido afrouxando a verificação do screenshot ou reduzindo a área clicável.

**Correção `f135eacc`:** miniaturas de Temas passam de 88 para 74 dp; layouts de 69 para 57 dp; presets de 56 para 46 dp. Espaçamento do título de cada miniatura reduzido de 5 para 3 dp, cabeçalhos de 6 para 4 dp e margem superior das abas de 12 para 8 dp. As abas e `Ver todos` mantêm **48dp de alvo**, foco, rótulos dinâmicos e ações funcionais. Não há alteração em preferência, APK, SQLite nem exportações.

**Verificação necessária:** repetir Android 10/15 e ambos os smokes, inclusive compact viewport (320dp/fonte 130%), e confirmar que `Dark OLED` voltou ao primeiro viewport sem violar os alvos de 48dp. `f135eacc` é código ainda não homologado até o resultado da nova matriz. PR #13 segue draft, main e P8 intocadas.

## P7.6 — área de toque real em Home e breadcrumb do Explorador (21/10/2026)

**Checkpoint anterior:** `486df0b8`, matriz [39615323314](https://github.com/nego001/ReaDroid-Native/actions/runs/39615323314), **success Android 10/15** com instrumentações, smokes regulares, viewport 320dp e fonte 130%; Source [39615324276](https://github.com/nego001/ReaDroid-Native/actions/runs/39615324276) e OTA [39615323505](https://github.com/nego001/ReaDroid-Native/actions/runs/39615323505) aprovados. Relacionado a issue #11/PR #13.

**Deficiência identificada:** os botões reais de menu e personalização da Home mediam **38×38dp**, inferiores ao mínimo de **48×48dp** usado na P7. A raiz "APK" do breadcrumb tinha texto curto sem largura mínima nativa explícita, e o botão do plano de edições usava `TextView.setMinHeight` sem `View.setMinimumHeight`, inconsistência já observada no Design Studio.

**Correção:** `P7HomeToolbar` usa botões de 48×48dp e View.minimumWidth/Height 48dp mantendo os mesmos ícones, descrições e ações. `P7ExplorerChrome` impõe ambos os mínimos TextView/View de 48dp na raiz e demais chips de breadcrumb, além da altura mínima View de 48dp no acesso ao plano de edição. Nada alterado em índice SQLite, SAF, filtros, importação/exportação ou assinatura.

**Regressões:** `P7NavigationInstrumentedTest` valida os alvos de menu e configurações quanto a dimensões, acessibilidade e funcionalidade. `P7ExplorerChromeInstrumentedTest` verifica dimensões mínimas, rótulo e foco do breadcrumb e do plano de edição. O smoke de **320dp/fonte 130%** passa a medir a geometria **real da hierarquia Android** nos dois botões da Home e em raiz/plano do Explorer, não só no Design. Em caso de corte ou alvo menor que 48dp, falha explicitamente, sem alegar conformidade.

**Estado:** alteração implementada e pendente de matriz Android 10/15 e Source/OTA no novo SHA. PR #13 continua draft, main intocada, sem release/distribuição APK, P8 #14 separada e projeto social #15/#16 em documentação independente. Aceite visual 1:1 depende dos dois PNGs oficiais ausentes e homologação física Galaxy A55.

## P7.6 — Home com 48dp e ensaio de fonte 200% (21/10/2026)

**Ponto inicial verificado:** commit `d191fe23` em [CI P7 39641678565](https://github.com/nego001/ReaDroid-Native/actions/runs/39641678565), **32/32 instrumentados** em Android 10/API29 e Android 15/API35; smokes normais e compactos 320dp/fonte130%, além de [Source](https://github.com/nego001/ReaDroid-Native/actions/runs/39641678537) e [OTA](https://github.com/nego001/ReaDroid-Native/actions/runs/39641678588), todos green.

**Achados:** seis atalhos da Home (`StudioDashboard.referenceAction`) tinham `View.setMinimumHeight(47dp)`; o acesso `Ver todos os projetos recentes` tinha 43dp e não declarava foco; menus `⋮` de histórico SAF tinham 40×40dp. São ações funcionais, mas ficam menores que o piso P7 de 48dp.

**Modificações:** mínimo 48dp para as seis ações rápidas; `Ver todos` com `TextView.setMinHeight` e `View.setMinimumHeight(48dp)` e foco; menus de histórico de 48×48dp, mínimos View/TextView, mantendo `Remover do histórico` com confirmação que só exclui referência e não APK original. Testes instrumentados de ação/teclado/áreas no `P7NavigationInstrumentedTest` e histórico sintético no `P7HomeOverviewInstrumentedTest`.

**Novo QA complementar:** `tools/p7_large_text_smoke.py` aplica fonte do sistema **200%** no viewport padrão do emulador, verifica via UI Automator navegação Home/Arquivos/Design, títulos, barra inferior e alvos >=48dp onde visíveis, captura PNG independente das três telas por API e restaura a fonte original no `finally`, inclusive em falha. Não altera tamanho, densidade, APK do usuário, importador SAF, dados de projetos, assinatura, versionCode ou OTA. Rodar após smoke 320dp/130% no workflow P7 Android 10/15; armazenar seis novas capturas no artifact.

**Status:** alterações submetidas a validação da matriz atual; não considerar cobertura de 200% aprovada até CI verde no SHA correspondente. P7 continua draft, P8 e IAs sociais documentadas em branches/PRs diferentes; visual 1:1 aguarda PNGs oficiais e teste real no Galaxy A55.

### P7.6 — ajuste dos testes após CI da fonte 200% (21/10/2026)

**Matriz inicial SHA `4f1a06c`:** Source checks [39644800099](https://github.com/nego001/ReaDroid-Native/actions/runs/39644800099) e OTA [39644800122](https://github.com/nego001/ReaDroid-Native/actions/runs/39644800122) aprovados; Android 10/API29 [39644800187](https://github.com/nego001/ReaDroid-Native/actions/runs/39644800187) acusou falha na **nova** instrumentação `homeQuickActionsAndRecentHistoryLinkMeet48dpContract` com `History link not found`, antes dos smokes da fonte 200%. O botão `Ver todos` **deve ficar oculto quando histórico real está vazio** (conforme `P7HomeOverview.renderHistory`) e o teste incorretamente assumiu um histórico não vazio. Isso é erro de premissa do teste, não autorização para inventar projetos.

**Correção:** `bb7de25f` removeu a exigência de link visível do teste genérico de Home vazia; `291d52af` mudou o teste `recentProjectMenuIsAccessibleWithoutDeletingOriginal` para criar referência sintética **não persistida**, ligar callback auditável e verificar que `Ver todos` aparece, mede >=48dp, recebe foco e aciona callback **somente no estado com projeto**. Mantida a verificação de 48dp para os seis atalhos e menu `⋮`. Sem alterar dados reais, grants SAF ou a lógica da UI.

**Pendência:** rodar novamente os 34 testes instrumentados nas APIs 29 e 35 e os smokes de 130%/200% no SHA atualizado. Não usar as execuções anteriores como aprovação da correção; registrar incidentes novos separadamente.

### P7.6 — harmonização do smoke de fonte 200% com estado vazio (21/10/2026)

**Revisão preventiva:** o ensaio `p7_large_text_smoke.py` usava originalmente a mesma premissa errada da instrumentação de Home: `Ver todos os projetos recentes` constava como obrigatório mesmo quando o histórico está vazio e o controle deve ter `View.GONE`. A verificação estática do fluxo `renderHistory()` confirma esse contrato.

**Correção `05711fa7`:** o teste de 200% verifica sempre os controles Home menu/personalização e **somente quando existe no XML visível** verifica o tamanho do link `Ver todos`. O teste instrumentado separado, com uma referência sintética e callback sem efeitos colaterais, já valida o caminho em que o histórico existe. Mantidos os 48dp da UI, as capturas reais e restauração de `font_scale`. Não introduzir histórico falso no app só para satisfazer QA.

**Matriz final:** o último ciclo de emuladores deve validar o novo script e as 34 instrumentações por API; Source/OTA do SHA anterior passaram, mas status completo do SHA novo precisa ser verificado.

## P7.6 — preservar aba interna do Design Studio ao recriar Activity (21/10/2026)

**Checkpoint antes desta alteração:** `a0ab36da` com [matriz Android 10/15 39646626656](https://github.com/nego001/ReaDroid-Native/actions/runs/39646626656), [Source 39646626666](https://github.com/nego001/ReaDroid-Native/actions/runs/39646626666) e [OTA 39646626941](https://github.com/nego001/ReaDroid-Native/actions/runs/39646626941) aprovados. Testes anteriores também cobrem fonte 200%, alvo 48dp, histórico vazio e regressões reais.

**Falha funcional identificada na leitura de código:** `MainActivity` preservava a seção principal `active_studio_section`, mas `P7DesignStudio` construía cada nova instância sempre com `activeTab=0` (Temas). Após rotação/recriação da Activity ou mudanças de configuração, a pessoa podia perder a seção interna Ícones, Logotipo ou Layout, mesmo permanecendo no Design. Isso compromete o contrato de navegação/restauração P7, sem ser uma diferença apenas cosmética.

**Correção implementada:** salvar o índice da aba interna do Design no `Bundle` da Activity, chave `p7_design_active_tab`, somente durante recriação; reconstituir `P7DesignStudio` com tab validada na faixa 0–3 (caso inválido = Temas) e reexibir seu conteúdo/seleção acessível no fluxo de `render()`. A opção atual não é gravada em SharedPreferences nem em dados do APK, não muda temas, ações, edições, histórico ou permissões. MainActivity mantém o estado principal original.

**Novo teste real:** `P7NavigationInstrumentedTest.designSubtabSurvivesRealActivityRecreation` navega para Design → Ícones, executa `ActivityScenario.recreate()`, valida seção e conteúdo visíveis, muda para Logotipo, recria novamente e confirma rótulo TalkBack e conteúdo `Logo Studio`, sem criar ou alterar APK do usuário. Requer CI API29/35 e regressão dos smokes 130%/200% antes de declarar aprovado.

**Escopo e limites:** alteração da PR #13 exclusivamente P7, sem alterar `main`, `versionCode` ou OTA. Issue #14 P8 e documentação de IAs #15/#16 permanecem separadas. PNGs oficiais e aceite físico no Galaxy A55 ainda faltam para 1:1 completo.

## P7.6 — aba horizontal selecionada visível em viewport estreita (21/10/2026)

**Checkpoint confirmado:** `ff29525e` passou na [matriz Android 10/15 39649241257](https://github.com/nego001/ReaDroid-Native/actions/runs/39649241257): **35/35 testes por emulador**, telas normais/320dp com fonte 130% e 200%, e restauração da fonte. Source [39649241261](https://github.com/nego001/ReaDroid-Native/actions/runs/39649241261) e OTA [39649241377](https://github.com/nego001/ReaDroid-Native/actions/runs/39649241377) também passaram.

**Pendência UX:** preservar a aba interna após recriação não garantia que ela fosse visualmente acessível. Em viewport estreito, a faixa de quatro abas é rolável e abria à esquerda: a aba restaurada Logotipo poderia ficar fora da área visível.

**Correção:** `P7DesignStudio` agora mantém a referência ao `HorizontalScrollView` das abas e executa `revealActiveTab()` após o layout, deslocando somente o necessário para manter os limites da aba ativa dentro da largura medida. Um retorno para Temas recua automaticamente para o início. Não toca em estado do APK, aparência persistida, plano de edição, nem faz movimentação vertical ou animações custosas.

**Teste novo:** `P7NavigationInstrumentedTest.narrowDesignKeepsSelectedTabVisible` cria widget Android real em viewport artificial de **240dp**, começa com aba Logotipo selecionada, aguarda layout, verifica que a aba está inteiramente dentro da região rolada, seleciona Temas e confirma scroll horizontal zerado. Matriz Android 10/15 e Source/OTA ainda precisam validar o novo SHA.

**Limites:** P7 segue isolada em PR #13 draft, sem merge main, APK de distribuição, OTA ou versionCode alterados; P8 e IA social seguem separados. Aceite 1:1 segue condicionado aos PNGs oficiais e QA no A55.

## P7.6 — inventário automático e verificável de capturas Android (21/10/2026)

**Base comprovada:** commit `31519ea7` e [matriz Android 39650804366](https://github.com/nego001/ReaDroid-Native/actions/runs/39650804366) com 36/36 instrumentações por Android 10/API29 e Android 15/API35, telas funcionais, viewport 320dp/130% e fonte 200%; Source/OTA verdes. Duas referências oficiais PNG continuam ausentes e a conferência Galaxy A55 continua pendente.

**Lacuna na auditoria P7.6:** o workflow armazenava várias capturas isoladas mas não tinha inventário legível por máquina com autoria da execução (API/densidade), cenário, dimensão, hash por PNG e distinção explícita entre evidência estrutural e aprovação visual 1:1. Falta de qualquer captura podia passar despercebida caso não houvesse teste específico.

**Implementação planejada nesta revisão:** adicionar `tools/p7_capture_manifest.py`, com verificação de todos os **11** PNGs obrigatórios em cada Android: Home, Explorador, Design, Icon Workshop, Logo Studio, três telas 320dp/130%, três telas com fonte 200%. Cada PNG será inspecionado quanto a assinatura, IHDR, dimensões, CRC de chunks, IDAT, IEND e ausência de lixo após IEND; os hashes SHA-256 e tamanhos são registrados em `p7-evidence-android-{api}.json` com API, densidade real e resolução ADB. Nome ausente, PNG inválido ou dimensão incorreta falham fechados. A execução consulta o validador oficial de PNGs e registra `BLOCKED` enquanto as artes não estiverem disponíveis, sem transformar isso em falso aceite.

**Testes:** `tests/test_p7_capture_manifest.py` com PNGs sintéticos **apenas dentro do teste unitário**, cobrindo inventário completo, cena ausente, dimensões erradas, CRC/IHDR/IEND/trailing e API inválida. O workflow passa a executar os testes antes dos emuladores, gerar o JSON após os smokes e fazer upload junto dos screenshots. Não gera APK de distribuição nem altera aplicativo/SAF/SQLite.

**Status inicial:** código de auditoria novo; aprovação real da matriz Android 10/15, source e OTA deve ser verificada **no SHA do commit final**. Este JSON não compara pixels do app com as imagens promocionais originais. PR #13 draft, main/P8/IA social intactos.

## P7.6 — painel de revisão visual offline auditável (21/10/2026)

**Base:** `75ce95a6` aprovado: [P7 Android 39653392928](https://github.com/nego001/ReaDroid-Native/actions/runs/39653392928) (**36/36 instrumentações nas APIs 29 e 35**), [Source 39653392910](https://github.com/nego001/ReaDroid-Native/actions/runs/39653392910) e [OTA 39653393020](https://github.com/nego001/ReaDroid-Native/actions/runs/39653393020) em `success`; manifestos listam 11 capturas PNG por API e `official_references=BLOCKED`. Artes originais e Galaxy A55 seguem ausentes da homologação.

**Incremento:** `tools/p7_visual_review_board.py` produz `p7-visual-review-android-{api}.html`, uma galeria HTML responsiva **offline** para revisar Home, Explorador, Design, workshops, 320dp/130% e fonte 200%. Reconstrói o inventário dos PNGs reais, verifica a igualdade de todos os campos do manifesto, CRC, dimensões, origem esperada e hashes SHA-256. Qualquer adulteração de imagem, metadado, estado de aprovação ou ausência de captura falha fechada. As artes oficiais só aparecem embutidas se ambas coincidirem com os hashes e dimensões aprovados. Sem artes oficiais, mostra bloqueio explícito. Nunca marca `pixel_perfect_approved` nem `physical_device_approved`. Evita comparar automaticamente pixels desalinhados do painel promocional e screenshots verticais.

**Pipeline:** workflow P7 roda testes unitários, depois gera o HTML após a coleta das 11 imagens e envia HTML + manifest JSON + PNGs no mesmo artefato Android 10/15; sem arquivos/cópias de APK de distribuição. Testes `tests/test_p7_visual_review_board.py` cobrem integridade do material, status bloqueado, ausência de recursos externos, não modificação de PNGs, falsificação de aprovação, hash divergente, imagem danificada ou faltante.

**Status:** esta entrega de documentação/ferramenta não é aprovação 1:1. Confirmar Source/OTA/matriz API29/35 no SHA resultante antes de marcar PASS; nunca presumir aprovação a partir do código enviado. PR #13 draft, `main`, P8 e arquitetura das IAs intocadas.

## P7.6 — evidência das cinco seções principais (21/10/2026)

**Base verificada:** commit `d512f14c`, [matriz Android 39656969573](https://github.com/nego001/ReaDroid-Native/actions/runs/39656969573) `success`, **36/36 instrumentações nas APIs 29 e 35**, fontes 130% e 200%, `P7_EVIDENCE_PASS` e `P7_VISUAL_BOARD_PASS` nos dois Androids. [Source 39656969676](https://github.com/nego001/ReaDroid-Native/actions/runs/39656969676) e [OTA 39656969535](https://github.com/nego001/ReaDroid-Native/actions/runs/39656969535) aprovados. API35 recuperada de erro transitório do SDK no rerun, sem alteração de código.

**Lacuna:** a navegação já tem cinco seções (Início, Arquivos, Segurança, Build, Design), mas as capturas da P7 não documentavam as páginas Segurança e Construir, apesar de terem ações importantes como o guia de assinatura e a revisão de edições.

**Melhoria:** novo `tools/p7_security_build_smoke.py` visita as abas Segurança e Build, valida títulos e seleção, captura os PNGs reais `p7-security-android-{api}.png` e `p7-build-android-{api}.png`, abre somente o guia informativo de assinatura e o diálogo de revisão do plano, e volta sem modificar o projeto. Não importa APK, não cria chave/assinatura, não exporta APK nem limpa o plano. Inventário passa de **11 para 13** PNGs obrigatórios por API, com integridade CRC, dimensões e SHA-256; painel visual offline expõe Segurança e Construir; testes unitários exercitam os novos cenários e rejeição de captura ausente. O workflow executa o smoke antes do Design e inclui imagens e relatório no mesmo artefato.

**Homologação:** depende de matriz API29/35 `success` no commit desta mudança. As artes oficiais ainda faltam, por isso `official_references=BLOCKED`; nenhum aceite visual 1:1, Galaxy A55, merge, APK distribuível, OTA ou versionCode novo. PR #13 draft, P8/IA social intactos.
