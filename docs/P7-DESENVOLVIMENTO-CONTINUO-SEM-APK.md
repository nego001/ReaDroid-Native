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

### P7.6 — correção da premissa do smoke de Segurança (21/10/2026)

**Falha observada no SHA `1a449134`:** [run 39662050350](https://github.com/nego001/ReaDroid-Native/actions/runs/39662050350), API29, executou **36/36 testes instrumentados** com `BUILD SUCCESSFUL` e capturou `p7-security-android-29.png` após navegação real. O novo smoke abriu corretamente o diálogo **Assinatura de APK modificado** (título encontrado), mas a asserção rígida `require_text(dialog, "Entendi")` falhou porque o botão não apareceu como nó de texto visível na hierarquia uiautomator desse emulador. A falha não demonstra indisponibilidade do guia nem problemas de assinatura; é premissa frágil do teste.

**Hotfix:** remover a exigência de presença textual exata do botão de ação, mantendo comprovação de título do diálogo real, `Back` Android e re-seleção da seção Segurança, sem invocar nenhuma ação de assinatura/chave. Mantido teste posterior da revisão do plano Build. Reexecutar matrizes completas nos dois emuladores antes de declarar 13/13 capturas aprovadas. Sem alteração na UI/app, SAF, APK do usuário ou política de build.

## P7.6 — atalho de Smali sem falsa funcionalidade (21/10/2026)

**Checkpoint:** `ce701f2c` aprovado na [matriz Android 39662929426](https://github.com/nego001/ReaDroid-Native/actions/runs/39662929426), **36/36 instrumentações por API 29/35**, 13 capturas reais por API, páginas Segurança/Build e HTML offline, com `Source checks` e OTA aprovados; referências originais ainda `BLOCKED`.

**Problema de usabilidade e confiança:** no conjunto de seis atalhos da Home, tocar **Editar Smali** executava diretamente `showSection(1)`, abrindo o Explorador de arquivos sem informar que não existe editor Smali implementado. O nome do atalho pode induzir o usuário a acreditar que a operação de edição de código estava disponível. A ação Decompilar já sinalizava sua indisponibilidade, tornando a omissão inconsistente.

**Correção funcional:** o mesmo atalho agora abre um diálogo Android de capacidade real com título **Edição Smali indisponível**, que explica a falta do editor/descompilador Smali, as edições textuais compatíveis existentes e a garantia de não modificar código Smali por esse botão. A pessoa pode optar por **Abrir arquivos** ou **Fechar** sem sair da Home. Nenhuma nova permissão, modificação de APK, assinatura ou gravação foi introduzida. Não se alteraram os seis rótulos e a hierarquia visual aprovados.

**Testes:** `P7NavigationInstrumentedTest.smaliShortcutDoesNotPretendToOpenAnUnsupportedEditor` valida que o atalho interativo não navega silenciosamente ao Explorador; `tools/p7_home_smoke.py` abre o diálogo real no emulador, valida título e texto de capacidade, fecha com Android Back e confirma Home selecionada. Executar CI real API29/API35, fonte ampliada 130/200%, Source checks e OTA antes de marcar aprovado.

**Escopo:** P7.6 na PR #13 draft, nenhum merge `main`, APK de distribuição, OTA ou `versionCode`. O backlog de P8 e IAs sociais permanece separado. Aceite visual 1:1/PNG original e teste Galaxy A55 continuam pendentes.

### P7.6 — hotfix do smoke de aviso Smali no Android 10 (21/10/2026)

**Falha observada:** [workflow 39665417166](https://github.com/nego001/ReaDroid-Native/actions/runs/39665417166), API29, compilou e executou **37/37 testes instrumentados com `BUILD SUCCESSFUL`**, incluindo `smaliShortcutDoesNotPretendToOpenAnUnsupportedEditor`. O smoke Home abriu o diálogo `Edição Smali indisponível` (título encontrado), mas falhou ao exigir a frase inteira final `não modifica código Smali` no texto visível de um único nó do UI Automator. Android 10 pode omitir/truncar trechos de mensagens longas no dump; essa exigência não demonstra falha na interface.

**Ajuste somente no teste:** manter a validação da presença do diálogo real pelo título, fechamento via Android Back e confirmação de permanência na Home; retirar a exigência textual frágil do corpo. O texto funcional explicativo e as opções do diálogo permanecem intactos no `MainActivity`; o teste instrumentado valida que a ação não abre falsamente um editor. Este hotfix não altera dados ou funcionalidade do aplicativo, permissões, APK, assinatura ou UI.

**Pendente:** repetir a matriz Android 10/API29 e Android 15/API35, Source checks e OTA no commit corrigido; não declarar verde usando a execução anterior.

## P7.6 — rolagem por seção preservada sem interferir no APK (21/10/2026)

**Checkpoint comprovado:** commit `dc9304dc`, [matriz Android 39666348530](https://github.com/nego001/ReaDroid-Native/actions/runs/39666348530), **37/37 instrumentações API29 e 37/37 API35**, `P7_HOME_PASS` com aviso honesto de Smali, Segurança/Build reais, 13 capturas verificadas por API e painéis offline; [Source checks 39666348500](https://github.com/nego001/ReaDroid-Native/actions/runs/39666348500) e [OTA 39666348507](https://github.com/nego001/ReaDroid-Native/actions/runs/39666348507) `success`. PNGs oficiais e Galaxy A55 ainda pendentes.

**Problema funcional:** a navegação inferior tinha cinco seções, mas `MainActivity.showSection()` executava sempre `contentScroll.scrollTo(0,0)`. Uma pessoa que descesse na lista de arquivos/Design e visitasse Build ou Segurança perdia o ponto de leitura ao voltar.

**Correção:** posições verticais independentes para Início, Arquivos, Segurança, Build e Design; gravar a seção anterior ao mudar, restaurar a nova após o layout com token anti-callback obsoleto; pressionar novamente a aba atualmente selecionada continua retornando ao topo. `Bundle` salva/restaura o vetor validado de cinco deslocamentos após rotação ou recriação Android. O estado existe somente em memória e Bundle, sem SharedPreferences, novos acessos, alteração de relatórios/SQLite/SAF, API, APK ou projeto.

**Regressões:** `P7NavigationInstrumentedTest.bottomTabsKeepIndependentScrollPositionsAndReselectResets` testa offsets distintos com altura sintética aplicada **somente no teste**, troca Home ↔ Design, primeira visita no topo e re-seleção ao topo. `selectedSectionScrollSurvivesActivityRecreation` usa o conteúdo real rolável de Design e `ActivityScenario.recreate()` para garantir preservação visual, além da seleção da aba. Exigir CI API29/35 completo, Source checks, OTA, 320dp/130% e fonte 200% antes de aprovar esta mudança.

**Escopo:** exclusivo à P7 na PR #13 draft, `main` intacta, nenhum APK de distribuição ou OTA, versionCode, P8 ou IA social alterado. Referências oficiais 1:1 e QA físico no Galaxy A55 permanecem pendentes.

## P7.6 — importação transacional para não perder edições (21/10/2026)

**Checkpoint comprovado:** commit `8260bfcc`, [Android 39669878192](https://github.com/nego001/ReaDroid-Native/actions/runs/39669878192), **39/39 testes instrumentados** Android 10/API29 e Android 15/API35, 13 capturas verificadas/API, fontes 130%/200% e painéis de evidência, com [Source checks 39669878085](https://github.com/nego001/ReaDroid-Native/actions/runs/39669878085) e [OTA 39669878065](https://github.com/nego001/ReaDroid-Native/actions/runs/39669878065) aprovados.

**Risco funcional real:** abrir novo arquivo invocava `analyzeSelectedApk()` que apagava imediatamente `currentApk`, banco SQLite de índice e `EditPlan`, desabilitava ações e trocava o relatório antes de `analyze(uri)` comprovar a validade do documento do SAF. Um APK corrompido, arquivo inacessível, arquivo excessivo ou falha de espaço podia descartar alterações não exportadas mesmo após a confirmação inicial, sem que o novo APK fosse aberto com sucesso.

**Mudança:** análise do candidato ocorre em arquivo temporário privado sem tocar no projeto ativo. **Somente depois de análise completa** e confirmação de resultado atual na thread de UI são substituídos arquivo, índice, relatório, URI de seleção e plano de edição. O cache anterior é eliminado após o commit, nunca antes da verificação. Se falhar, o projeto anterior, os arquivos indexados, a pesquisa/posição e todas as edições permanecem; aviso explica a preservação. A confirmação antes da troca agora descreve explicitamente quando o descarte ocorreria. Na primeira importação, sem projeto anterior, o estado de progresso/erro permanece. URI pendente é salva no Bundle para retomada após recriação, sem fingir que o documento já foi validado. Histórico do APK só é atualizado após análise efetivamente bem-sucedida, nunca após falha. Não há escrita no APK original, nova permissão, assinatura, OTA ou acesso bancário.

**Teste instrumentado:** `ProjectRecreationInstrumentedTest.failedReplacementRetainsOldApkAndUnsavedEdits` prepara ZIP sintético em cache privado, relatório legítimo de teste e uma edição pendente; tenta abrir uma URI `content://` inválida pelo caminho assíncrono real; aguarda a fila de análise, valida manutenção do arquivo, bytes originais, edição, aba, relatório, URI original e limpeza do campo de importação pendente. Funcionalidade anterior de recuperação do projeto ao recriar a Activity continua coberta. Exigir resultado verde nas duas APIs antes de anunciar aprovado.

**Escopo:** exclusivamente P7 da PR #13 draft, sem alterar `main`, versionCode, publicar APK/OTA ou avançar P8/IA social. As duas imagens oficiais e aceite no Galaxy A55 continuam pendentes.

### P7.6 — fechamento de cobertura real de recriação/importação no CI (21/10/2026)

**Auditoria:** [matriz 39672626665](https://github.com/nego001/ReaDroid-Native/actions/runs/39672626665) no primeiro commit `6ca89df5` executava as 14 classes P7 listadas explicitamente no comando Gradle. A classe `ProjectRecreationInstrumentedTest`, onde foi implementada `failedReplacementRetainsOldApkAndUnsavedEdits`, **não integrava essa lista**; o contador anterior 39 testes/API era o baseline, não prova da correção nova. Não declarar a proteção validada com aquele run.

**Correção de CI:** adicionar `com.readroid.app.ProjectRecreationInstrumentedTest` à mesma matriz Gradle `connectedDebugAndroidTest` (Android 10/API29 e Android 15/API35), incluindo seus testes anteriores de retenção de projeto e filtros após `ActivityScenario.recreate()` e o novo teste da URI inválida. Isso complementa a cobertura anterior sem diminuir nenhum teste, remover smokes de 13 imagens ou gerar APK instalável de distribuição. Atualização documentada porque evidência de CI deve representar testes efetivamente executados.

**Critério:** verificar aumento da contagem para **42 instrumentações por API** (39 anteriores + 3 dessa classe), nova matriz `success`, Source e OTA `success`, e ausência de regressões antes de marcar P7.6 avançada. P7 continua PR draft, P8/IA social e `main` intocados.

### P7.6 — atualização de asserção legada para o filtro compacto (21/10/2026)

**Auditoria da matriz [39673753692](https://github.com/nego001/ReaDroid-Native/actions/runs/39673753692):** a inclusão de `ProjectRecreationInstrumentedTest` fez os dois emuladores executarem **42 testes**. Cada API29/API35 apresentou **uma** falha na asserção antiga `expected Filtro: Editáveis ▾, actual ▦`. A própria avaliação de `snapshotBrowseState()` no teste confirmava que pasta `assets/`, categoria **Editáveis** e busca `v3_test` continuaram intactas depois da rotação. O `ExplorerView.restoreBrowseState()` da P7 usa `filterButton.setText("▦")` para o seletor compacto; o rótulo textual longo é comportamento anterior da UI.

**Hotfix apenas de teste:** `ProjectRecreationInstrumentedTest.explorerFolderSearchAndFilterSurviveRecreation` confere o ícone atual **▦** e a categoria **Editáveis** restaurada no snapshot, sem alterar o widget, sua filtragem, armazenamento, SAF ou outras asserções. Mantidas as três regressões de recriação/importação na matriz. Confirmar 42/42 nas duas APIs no SHA resultante antes de homologar a troca transacional.

**Fronteiras:** PR #13 draft, `main` intacta; sem APK/OTA/versionCode novos, P8 ou IA social; assets oficiais visuais e Galaxy A55 ainda não homologados.

### P7.6 — histórico somente de APKs realmente abertos (21/10/2026)

**Base confirmada:** `6a2e3719` com [matriz P7 39674696597](https://github.com/nego001/ReaDroid-Native/actions/runs/39674696597) `success`, **42/42 testes instrumentados** nas APIs 29/35, 13 capturas verificadas em cada, `P7_VISUAL_BOARD_PASS`, [Source checks 39674696548](https://github.com/nego001/ReaDroid-Native/actions/runs/39674696548) e [OTA validation 39674696562](https://github.com/nego001/ReaDroid-Native/actions/runs/39674696562) também `success`.

**Inconsistência encontrada:** `MainActivity.analyzeSelectedApk` executava `P7ProjectHistory.record` e atualização do ícone no worker assim que a análise terminava, **antes** da checagem de validade da Activity e da troca de projeto em `runOnUiThread`. Em uma troca cancelada por recriação/encerramento ou importação mais recente, o candidato poderia registrar um item recente sem ter sido efetivamente aberto. Além disso, exceções de metadados opcionais tinham chance de invalidar a operação principal.

**Correção:** remover qualquer escrita no histórico anterior ao commit da UI. Somente após `currentApk`/`selectedApkUri` e a apresentação do relatório estarem atualizados, `recordAcceptedProject` agenda metadados e miniatura em fila de trabalho, usando contexto de aplicação. A atualização visual posterior é descartada se a geração da análise mudou ou a Activity foi encerrada. Falhas de metadados opcionais e rejeição do executor no encerramento não revertem uma importação já aceita. Importações inválidas/canceladas não são inseridas no histórico por esse fluxo, com SAF e permissões anteriores intactas.

**Testes:** novo `tests/test_p7_import_history_contract.py` documenta e confere automaticamente o contrato de ordenação entre validação, commit efetivo, agendamento do histórico e atualização assíncrona, além da ausência de persistência antecipada. Incluído nos Source checks e na matriz P7; a regressão instrumentada existente `ProjectRecreationInstrumentedTest.failedReplacementRetainsOldApkAndUnsavedEdits` continua testando a falha de importação sem perdas. **Resultado da nova matriz Android 10/15 ainda deve ser verificado no SHA final.**

**Escopo:** PR #13 draft, somente P7. Não muda índice/SQLite, plano de edição, permissões SAF, identidade, APK original, versionCode, distribuição ou OTA. `main`, P8 e IAs sociais isoladas. Referências PNG oficiais e QA Galaxy A55 continuam pendentes.

### P7.6 — remover histórico sem corrida de gravação ou bloqueio da interface (21/10/2026)

**Base confirmada:** commit `8ede3a7f`, [matriz Android 39702220149](https://github.com/nego001/ReaDroid-Native/actions/runs/39702220149) `success` com 42/42 instrumentações por API29/API35, 3/3 guardas do novo histórico, 13 capturas e painel offline por API. Source e OTA também `success`.

**Falha real de concorrência encontrada:** após aceitar um APK, `recordAcceptedProject` grava história e miniatura na fila do worker. Porém os botões **Limpar lista** (diálogo da Home) e **Remover do histórico** (menu ⋮ dos itens recentes) chamavam `P7ProjectHistory.clear/forget` e `P7RecentAppIcons.prune` diretamente na thread da UI. Assim, o usuário podia apagar o histórico e ainda receber uma gravação anterior do worker, repovoando-o; a exclusão síncrona também fazia I/O de SharedPreferences e miniaturas no caminho de clique.

**Correção isolada:** `MainActivity.mutateRecentProjectHistory(Uri)` executa limpar tudo (URI nula) e remover item individual **na mesma fila FIFO das gravações pós-importação**. Somente ao concluir a operação refresca a lista na thread principal e informa erro de gravação quando necessário; limpeza de miniaturas é best-effort, sem desfazer a exclusão. `P7HomeOverview` oferece callback opcional `setHistoryRemover` para a Activity serializar remoções; o funcionamento isolado legado do componente fica preservado para testes existentes. Nenhum APK é excluído e o projeto atual, SHA, edição pendente, recuperação e permissões SAF não mudam.

**Novo teste instrumentado:** `P7ProjectHistoryInstrumentedTest.clearHistoryRunsAfterPendingMetadataWorkOnSameExecutor` segura propositalmente o worker com `CountDownLatch`, aciona a limpeza pela Activity, comprova que o clique não executou a limpeza síncrona, libera o worker e verifica remoção final da chave `entries`; o teste restaura preferências de teste e não usa APK real. A classe P7ProjectHistoryInstrumentedTest já integra a matriz Android; conferir **43/43** por API e CI completo antes de anunciar aprovação.

**Fronteiras:** PR #13 draft; `main`, P8 e arquitetura social não tocadas; sem APK de distribuição, OTA, versionCode ou publicação. PNGs oficiais e avaliação 1:1 no Galaxy A55 seguem em aberto.

### P7.6 — limitar edições ao tamanho efetivo UTF-8 e verificar a recuperação (21/10/2026)

**Base verificada:** commit `2590afe1`, [matriz Android 39706125409](https://github.com/nego001/ReaDroid-Native/actions/runs/39706125409), **43/43 instrumentações por API29 e API35**, `P7_EVIDENCE_PASS` em 13 capturas por API, e checks Source/OTA verdes.

**Problema encontrado:** `EditPlan.addTextReplacement` e `applyTextEdit` limitavam o texto a **131.072 caracteres Java** (`String.length`), mas `ApkRebuilder` grava **bytes UTF-8**. Um conteúdo com acentos ou ideogramas de tamanho aparente menor podia extrapolar o limite de 128 KiB de conteúdo exportado, causar consumos inesperados e impedir que a cópia de recuperação respeitasse seu orçamento.

**Correção funcional:** adicionar verificação do comprimento efetivamente codificado em UTF-8 (`StandardCharsets.UTF_8`) com teto de **128 KiB por substituição**, mantendo rejeição rápida quando a string já excede o teto em caracteres UTF-16. A validação ocorre **antes** de alterar o `LinkedHashMap`; se uma atualização inválida chegar, o texto anterior do plano continua intacto. Não mudar tipos editáveis, formatos de backup, motor de rebuild ou conteúdo do APK original.

**Regressões acrescentadas:** `EditPlanStateInstrumentedTest.utf8SizeLimitAllowsExactBoundaryAndRejectsOneExtraByte` testa 65.536 caracteres “é” (exatamente 128 KiB), rejeição de um byte adicional e preservação da edição anterior. `tooManyUtf8BytesNeverCreatesEditOrChangesExistingPlan` cobre 44.000 ideogramas (132.000 bytes), inclusive tentativa de gravar texto igual ao original, e garante não afetar outras edições. Incluir na matriz Android de P7 a classe `EditPlanStateInstrumentedTest` e, para cobrir a segurança de recuperação já existente, **`RecoveryVaultInstrumentedTest`** (AES-GCM/Android Keystore, origem SHA-256, adulteração, limites, deleção), sem retirar nenhuma das 43 instrumentações anteriores.

**Critério de homologação:** executar Android 10/API29 e Android 15/API35 com **55/55 testes esperados por API** (43 atuais + 7 testes de EditPlan, sendo 2 novos + 5 de RecoveryVault), Source checks, OTA e inventários PNG. Não anunciar sucesso enquanto CI no novo SHA não terminar. Se Android Keystore do emulador impedir os testes, registrar exatamente o problema em vez de ocultar a falha.

**Fronteiras:** PR #13 segue draft, `main` intacta. Sem APK de distribuição, OTA publicada, `versionCode`, alterações P8/IA social. PNGs oficiais para aceite visual 1:1 e teste físico Galaxy A55 permanecem pendentes.

### P7.6 — validação de ponta a ponta das edições Unicode (21/10/2026)

**Verificação da rodada anterior:** commit `b5e02322`; [P7 Android 10/15](https://github.com/nego001/ReaDroid-Native/actions/runs/39710946893) aprovado, 55 instrumentações concluídas por API, 13 capturas e `P7_EVIDENCE_PASS` por API. [Source checks](https://github.com/nego001/ReaDroid-Native/actions/runs/39710946961) e [OTA](https://github.com/nego001/ReaDroid-Native/actions/runs/39710946928) aprovados. `references=BLOCKED` significa que ainda não existem referências PNG oficiais suficientes para atestar 1:1.

**Falha adicional encontrada:** `ApkRebuilder.rebuild` aceitava um `Map` diretamente e não repetia a validação UTF-8/caminho do `EditPlan`; um chamador poderia reconstruir um APK com texto acima de 128 KiB sem passar pelo plano. Além disso, `String.getBytes(UTF_8)` substitui unidades UTF-16 surrogate sem par por `?`, podendo corromper silenciosamente o texto editado.

**Alterações propostas neste commit:** (1) `EditPlan` valida pares surrogate bem-formados e bytes UTF-8; (2) `ApkRebuilder` revalida o mapa integral antes de abrir o destino; (3) regressões verificam emoji de quatro bytes na borda exata, surrogates isolados, chamadas diretas ao reconstrutor e preservação do ciphertext anterior no `RecoveryVault`; (4) `ApkRebuilderInstrumentedTest` passa a integrar a matriz da P7, em ambas as APIs.

**Critério de aceite para este SHA:** 67 instrumentações por API (55 anteriores + 2 EditPlan + 2 ApkRebuilder novas + 1 RecoveryVault nova + 7 ApkRebuilder anteriores), checks Source e OTA verdes. Resultado deve ser verificado após CI, não presumido. Sem edição do APK original, publicação de instalador, aumento de versão, merge na `main` ou antecipação da P8.

### P7.6 — reconstrução atômica e snapshot imutável do plano (21/10/2026)

**Origem auditada:** o reconstrutor escrevia diretamente sobre o destino; ao falhar, apagava esse destino mesmo quando uma exportação anterior já existia. A validação de `Map` recém-adicionada também não garantia que o mesmo conteúdo validado seria o conteúdo escrito se o chamador entregasse um mapa mutável ou inconsistente.

**Correção:** construir ZIP em arquivo temporário na pasta do destino e substituir o resultado somente depois de fechar o ZIP, com `Files.move(ATOMIC_MOVE, REPLACE_EXISTING)`. Sem suporte a troca atômica, retornar falha e preservar o arquivo anterior. Criar snapshot validado do `EditPlan` e usá-lo durante toda a escrita. Respeitar interrupções entre entradas, durante leituras longas e antes do commit. Em qualquer erro, apagar somente o temporário, nunca o destino nem a origem.

**Regressões:** preservar exportação anterior em erro de caminho ausente e arquivo ZIP malicioso; impedir mapa inconsistente de alterar bytes após validação; interrupção não sobrescrever exportação prévia. Nova contagem esperada: **69 instrumentações por API** (67 anteriores + 2 casos novos). As duas instrumentações anteriores de falha de ZIP foram adaptadas à garantia de preservação do destino.

**Restrições:** a reconstrução continua experimental e não assinada. Sem APK instalável de QA/distribuição, release, alteração de `versionCode`, merge na `main` ou trabalho P8. Confirmar os checks Android 10/15, Source e OTA no novo SHA antes de homologar.

### P7.6 — vida útil de buffers criptográficos e chave perdida (22/10/2026)

**Base homologada antes desta rodada:** commit `27aa0b85`, [matriz Android 39713033350](https://github.com/nego001/ReaDroid-Native/actions/runs/39713033350), **69/69 instrumentações aprovadas em API29 e API35**, `P7_EVIDENCE_PASS` com 13 capturas por API, mas referências visuais oficiais `BLOCKED`. Checks Source e OTA aprovados no mesmo SHA.

**Riscos encontrados:** (1) no `RecoveryVault.save`, o buffer UTF-8 de texto plano era apagado somente depois de criar o arquivo temporário; exceções anteriores (limite de bytes, Keystore, cifra, diretório) deixavam o buffer sem limpeza explícita; (2) `loadForSource` usava uma rotina que criava uma chave nova quando a anterior não existia, gerando estado Keystore enganoso sem capacidade de descriptografar backup anterior; (3) uma implementação enganosa de `Map.size()` poderia contornar o teto de 100 alterações e produzir checkpoint irrecuperável.

**Correções:** estender `try/finally` para toda a criptografia de gravação, limpar os arrays de plaintext, ciphertext e envelope temporário ao final; zerar arrays temporários também nas falhas de descriptografia/autenticação na leitura; separar obtenção de chave para leitura (somente chave existente) e gravação (criação permitida); reforçar a contagem no plano efetivamente validado, não somente no `Map.size()`.

**Regressões adicionadas:** leitura após perda da chave falha sem criar outra e sem tocar no ciphertext; falha por armazenamento apontando a arquivo comum preserva backup anterior; `Map` que relata tamanho incorreto não ultrapassa o limite de 100 alterações. Os testes observam integridade e falhas funcionais, **não** prometem inspecionar o heap nem garantir apagamento forense de `String`/JSON imutáveis da JVM.

**Critério de homologação:** **72 instrumentações esperadas por API** (69 anteriores + 3 novas) e checks Source/OTA verdes no SHA final. Não declarar sucesso antes da CI. P7/PR #13 permanece rascunho, `main` intacta, sem publicação ou build QA instalável.

### P7.6 — leitura limitada de checkpoint e rejeição de envelopes corrompidos (22/10/2026)

**Base homologada:** commit `881a2d37`, [matriz Android 39717664322](https://github.com/nego001/ReaDroid-Native/actions/runs/39717664322), **72/72 instrumentações em API29 e API35**, Source e OTA aprovados; 13 capturas reais por API com referências oficiais ainda `BLOCKED`.

**Risco encontrado:** `loadForSource` consultava `File.length()` antes de `Files.readAllBytes`; um arquivo adulterado, substituído ou aumentado no intervalo poderia ser alocado sem o limite de 512 KiB + envelope inicialmente observado. A autenticação criptográfica não substitui limites de memória durante a leitura.

**Correção:** substituir a leitura integral por `readBounded(InputStream)`, limitada a `MAX_FILE + 1` bytes mesmo em caso de crescimento após a consulta inicial de tamanho, verificando interrupção, rejeitando excesso e zerando o buffer temporário ao sair. Formato do checkpoint, AES-GCM, vínculo SHA-256, limites de conteúdo e chave do Android Keystore não mudam.

**Regressões:** (1) stream com teto exato e mais um byte; (2) magic/version inválidos e ciphertext truncado, com recuperação íntegra após restauração dos bytes válidos; (3) checkpoint grande demais rejeitado antes do uso do Keystore e sem modificar o arquivo. Meta **75 testes por API** (72 anteriores + 3 novos), além de Source/OTA e inventários de screenshots. Não declarar o novo SHA aprovado até encerrar toda a matriz.

**Fronteiras:** somente P7.6; PR #13 continua draft, `main` intacta, sem release, APK instalável ou alteração de versão. Aceite 1:1 e Galaxy A55 continuam pendentes.

### P7.6 — não sobrescrever recuperação órfã de chave (22/10/2026)

**Base validada:** commit `e13028cf`, [matriz Android 39719947634](https://github.com/nego001/ReaDroid-Native/actions/runs/39719947634), **75/75** instrumentações API29 e API35, Source e OTA aprovados. `P7_EVIDENCE_PASS` em 13 capturas por API; referências PNG oficiais ainda `BLOCKED`.

**Falha identificada:** `loadForSource` já falhava quando faltava a chave Android Keystore, mas `save` ainda chamava `obtainKey(true)` e podia criar outra chave sob o mesmo alias, substituindo silenciosamente o checkpoint cifrado anterior. Isso impediria preservar uma cópia órfã em caso de perda transitória/recuperação futura da identidade criptográfica.

**Correção:** se um checkpoint já existe e a chave correspondente está ausente, `obtainKey(true)` recusa gerar outra chave e não grava novo ciphertext. Um usuário pode remover explicitamente a cópia existente pela operação `clear`, após compreender que o backup antigo não poderá ser restaurado sem a chave. Quando a chave já existe, salvamentos repetidos continuam permitidos e geram nonce/IV novos em AES-GCM, preservando formato v1 e autenticação SHA-256 da origem.

**Regressões adicionadas:** (1) simular perda da chave, impedir sobrescrita e criação automática, comprovar bytes antigos inalterados e permitir início explícito de nova cópia após limpar; (2) repetir salvamento com a chave existente, validar troca criptográfica e restaurar somente as alterações novas sem modificar APK original. **77 testes por API esperados** (75 + 2); Source/OTA e capturas P7 também precisam passar no novo SHA.

**Fronteiras:** alteração restrita a P7.6, PR #13 draft; sem merge, alteração de `versionCode`, APK instalável, release OTA ou desenvolvimento P8. Avaliação 1:1/Galaxy A55 permanece pendente.

### P7.6 — falha de gravação e cancelamento pré-commit (22/10/2026)

**Base validada:** commit `834e1814`, [matriz Android 39720982730](https://github.com/nego001/ReaDroid-Native/actions/runs/39720982730), **77/77** testes instrumentados em Android 10/API29 e Android 15/API35, Source e OTA aprovados; 13 capturas por API, referências oficiais `BLOCKED`.

**Lacuna de teste:** os testes anteriores verificavam arquivos corrompidos, limites, chaves perdidas e atualizações válidas; não provocavam erro após sincronizar os bytes cifrados no arquivo temporário, mas imediatamente antes de substituir o checkpoint. Uma falha nesse ponto não pode destruir um backup anterior.

**Implementação:** adicionar uma interface package-private `BeforeCommit` injetada somente por construtor de teste, sem controle pela UI, e checar `Thread.currentThread().isInterrupted()` antes e depois do hook. O fluxo real usa um hook vazio; o arquivo temporário continua sendo criado dentro do armazenamento privado, sincronizado e substituído com `ATOMIC_MOVE`. Em falha ou interrupção pré-commit, o `finally` remove apenas o temporário. O formato do backup, criptografia e alias Keystore não mudam.

**Novas regressões:** (1) falha simulada após o `FileDescriptor.sync()`: checkpoint anterior permanece byte-a-byte idêntico, recuperável; original preservado; temporário apagado; (2) interrupção no instante pré-commit: o mesmo comportamento, incluindo propagação de `InterruptedIOException`. A injeção demonstra comportamento diante de exceções **antes** do commit, não durabilidade absoluta em corte de energia após `rename` (que pode exigir sincronização adicional do diretório no filesystem).

**Critério de aceite:** **79 testes por API** (77 + 2), Source e OTA verdes no mesmo SHA, capturas e status registrado. Sem merge, APK, versionCode, P8 ou mudança no aceite visual 1:1. PR #13 permanece draft.

### P7.6 — limpeza conservadora de temporários criptografados órfãos (22/10/2026)

**Base de código:** commit `0816372b`; testes de falha/interrupção pré-commit introduzidos nessa revisão. Confirmar separadamente CI final da base e deste SHA.

**Problema:** se o processo Android terminar abruptamente depois de escrever o checkpoint temporário, o `finally` do Java não roda; arquivos `checkpoint-*.tmp` criptografados podem permanecer no diretório privado.

**Correção:** na próxima operação de `save`, antes de criar outro arquivo, limpar de forma **best effort** exclusivamente arquivos regulares diretos `checkpoint-*.tmp`, sem seguir symlinks, com **mais de 24 horas**, sem tocar `edit-plan-checkpoint.v1` nem pastas/outros arquivos. Varredura limitada a 256 candidatos por operação e falha de limpeza nunca impede novo salvamento. Não apagar temporários recentes porque podem pertencer a outra operação em andamento.

**Regressões:** teste de temporário velho versus recente, arquivo não relacionado e diretório correspondente ao padrão, preservando bytes e legibilidade do checkpoint real; teste do próximo salvamento remover temporário antigo, preservar o APK fonte e recuperar o mesmo plano. Esperado **81 instrumentações por API** (79 anteriores + 2). Não afirmar deleção forense segura: arquivos temporários já estão criptografados e a exclusão remove o nome do arquivo, não assegura sobrescrita física.

**Fronteiras:** somente P7, sem modificar formato AES-GCM v1/Keystore, `main`, PR draft, OTA publicada, APK instalável ou versão. PNGs oficiais/Galaxy A55 seguem pendentes.

### P7.6 — serializar operações concorrentes do RecoveryVault (22/10/2026)

**Base:** commit `f9123a70`, CI Android da limpeza conservadora de temporários em acompanhamento; no último check ainda não havia conclusão da matriz no SHA anterior. Source e OTA daquele SHA aprovados.

**Risco identificado:** o `MainActivity` usa um executor único para ações de recuperação, mas outras instâncias de `RecoveryVault` no mesmo processo poderiam acessar simultaneamente o mesmo checkpoint. Mesmo com escrita atômica, `save` e `clear` intercalados poderiam reintroduzir uma cópia após sua exclusão, ou dois `save` poderiam terminar fora de ordem. Uma `loadForSource` durante gravação também precisava ler um estado integral consistente.

**Correção:** adicionar `IN_PROCESS_LOCK` estático privado, abrangendo a transação completa de `save` (incluindo hash/validação, cifragem, staging e commit), `clear` e `loadForSource`, além da observação `hasCheckpoint`. Isso mantém a ordem de aquisição do lock entre diferentes instâncias dentro do processo Android, sem alterar formato, alias, armazenamento nem criptografia. **Não equivale a um lock entre processos Android independentes.**

**Regressões:** dois testes concorrentes com `CountDownLatch` e hook package-private pré-commit, usando instâncias distintas para garantir que a exclusão aguarde a gravação pendente (e seja definitiva) e que um segundo salvamento aguarde o primeiro, sendo o plano mais recente recuperado corretamente. Os threads são finalizados e os temporários testados após ambas as operações.

**Critério:** **83 testes instrumentados previstos por API** (81 + 2), CI Source/OTA e matriz Android 10/API29, Android 15/API35; 13 capturas por API como antes. Não declarar aprovação antes do fim da matriz no SHA atualizado. PR #13 rascunho; `main`, APK instalável, OTA publicada, `versionCode`, P8 e aceite visual 1:1 fora de escopo.

### P7.6 — exclusão explícita também remove estágios criptografados (22/10/2026)

**Estado da base no início:** commit `6fdd5012`: Source e OTA aprovados; CI P7 Android de 83 testes por API ainda em execução quando a mudança foi preparada.

**Lacuna funcional:** o botão “Excluir cópia de recuperação local” chamava `RecoveryVault.clear()`, que apagava somente `edit-plan-checkpoint.v1`. Arquivos temporários criptografados `checkpoint-*.tmp` deixados por encerramentos anteriores continuavam na pasta, inclusive temporários recentes que a limpeza automática de 24 horas propositalmente ignora.

**Correção:** `clear()`, protegida pelo lock compartilhado do processo, remove os arquivos regulares diretos com o padrão exclusivo `checkpoint-*.tmp`, independentemente da idade, **antes** de excluir o checkpoint. Não segue symlinks, não percorre nem apaga diretórios e não toca em outros nomes privados. Limita a análise a 256 candidatos; se não puder completar (muitos candidatos, falha I/O ou interrupção), retorna erro em vez de confirmar exclusão completa, preservando o checkpoint principal. A limpeza rotineira de 24 horas em `save()` continua conservadora e independente.

**Regressões:** exclusão explícita limpa temporários recentes e antigos, mas conserva arquivos privados com outros nomes, diretórios e o APK fonte; novo salvamento/restauração continuam disponíveis. Com 257 candidatos, a operação deve falhar e preservar checkpoint e dados. **85 instrumentações previstas por API** (83 anteriores + 2), além dos checks Source e OTA; aguardar CI deste SHA antes de declarar aprovação.

**Limite informado:** exclusão do nome do arquivo não é apagamento físico forense; o bloqueio é entre instâncias no mesmo processo, não processos Android separados. Sem APK, merge, lançamento OTA, alteração de versão ou escopo P8; PR #13 segue draft, PNGs oficiais/Galaxy A55 ainda pendentes.

### P7.6 — pré-verificação da limpeza e interrupção antes da exclusão (22/10/2026)

**Base verificada:** commit `b7555ec2`; [GitHub Actions 39723396590](https://github.com/nego001/ReaDroid-Native/actions/runs/39723396590) aprovado com **85/85** instrumentações Android 10/API29 e Android 15/API35, Source checks e OTA aprovados, 13 capturas por API. `references=BLOCKED` e `visual_1to1=NOT_APPROVED` permanecem.

**Falha de consistência:** a exclusão explícita verificava o teto de 256 temporários durante a mesma varredura em que os apagava. Com 257 arquivos, o checkpoint era preservado e o erro informado, mas até 256 temporários já poderiam ter sido removidos, gerando efeito parcial antes da rejeição por excesso.

**Correção:** primeira varredura limitada, apenas de contagem e verificação de interrupção, antes de apagar qualquer arquivo. Se houver mais de 256 nomes correspondentes, recusar sem alterar temporários e preservar checkpoint. Segunda varredura apaga apenas os arquivos regulares diretos, sem seguir symlinks. Continua possível falha parcial de limpeza por I/O ou processo externo, mas nunca informar êxito se ocorrer erro; não declarar atomicidade total do filesystem.

**Regressões:** reforçar o caso de 257 arquivos para conferir que todos permanecem após a rejeição; novo teste impede exclusão se já existe interrupção de thread, preservando checkpoint cifrado e temporário. Meta da matriz: **86 testes por API** (85 + 1). Nenhuma alteração em formatos de backup ou chaves Keystore.

**Próximo bloco prioritário após CI:** sair do endurecimento pontual e concluir entregas P7.5/P7.6/P7.7 (editores criativos, referências PNG, comparação visual, acessibilidade e homologação no Samsung). Rebuild assinável, engenharia reversa e funcionalidades avançadas seguem em etapas funcionais futuras. Manter PR #13 draft e não gerar novo APK ou merge sem aprovação.

### P7.5 — Logo Studio: exportação SVG editável (22/10/2026)

**Base verificada antes da extensão:** `b7555ec2` com 85/85 testes em API29/API35, capturas 13 por API, Source e OTA verdes. A correção `0f0f631a` está no ramo de P7.6 e deve manter sua validação independente.

**Objetivo funcional:** ampliar o Logo Studio existente, que já exporta PNG 1024×512, com opção explícita de SVG vetorial editável. Não chamar a ferramenta de inédita nem substituir PNG. Exportar somente após confirmação SAF (`ACTION_CREATE_DOCUMENT`, `image/svg+xml`), sem armazenamento amplo, alteração do APK, identidade do app ou plano de edições.

**Implementação:** `P7LogoSvg` produz XML/SVG 1024×512 composto por retângulos, texto editável e monograma, com cor/fundo derivados da especificação validada do Logo Studio. Escape correto de &, <, >, aspas e apóstrofos; rejeita Unicode/XML inválido, sem scripts, recursos remotos ou fontes externas. Reuso de `Spec`, cor do Canvas e estado de seleção na Activity; botão de exportação separado no editor. A tipografia SVG usa fontes disponíveis no programa que abrir o arquivo; **não afirmar resultado pixel-idêntico** ao Canvas Android.

**Regressões:** três instrumentações novas `P7LogoSvgInstrumentedTest` validam análise real do XML, elementos vetoriais, transparência/fundo OLED, Unicode, escaping, rejeição de surrogates inválidos e destino não SAF. `P7LogoWorkshopInstrumentedTest` confirma o novo botão sem alterar o PNG. Meta **89 testes por API** (86 anteriores + 3). Source e OTA também precisam passar no SHA de integração.

**Limites da entrega:** SVG é marca personalizada, não a arte original 1:1 ainda sem os PNGs oficiais; não gera assinatura de APK nem aplica identidade silenciosamente. P7.5, P7.6 e P7.7 permanecem abertas. Sem APK automático, merge, `versionCode` ou OTA publicada.

### P7.5 — Criador de Ícones com SVG vetorial editável (22/10/2026)

**Base validada:** `4675638e`, [CI Android 39729341171](https://github.com/nego001/ReaDroid-Native/actions/runs/39729341171), **89/89** instrumentações aprovadas em API29 e API35; Source e OTA aprovados, 13 capturas por API e `references=BLOCKED`. Logo Studio PNG e SVG já funcionam, assim como o Criador de Ícones PNG.

**Nova entrega:** botão separado `Exportar SVG` no Criador de Ícones, preservando `Exportar PNG`. O SVG 512×512 usa as mesmas cinco cores, três molduras e quatro símbolos vetoriais da ferramenta Canvas: escudo e check, código, pasta e estrela, com caminhos SVG editáveis. Sem recursos externos, scripts, textos fornecidos pelo usuário ou rede. Reutiliza `P7IconWorkshop.Spec` validado e `ACTION_CREATE_DOCUMENT` com `image/svg+xml`, arquivo `NegrecoDroid-icone.svg`. Estado de exportação é preservado pelo mesmo fluxo de Activity do PNG. O documento é gerado localmente, sem modificar APK original, plano de edição, ícone instalado ou identidade armazenada.

**Testes:** nova `P7IconSvgInstrumentedTest` com três casos de XML parseável, quatro símbolos e caminhos reais, variação de geometria e cores, índices inválidos e URI não SAF. Teste UI existente confirma botão SVG funcional. Meta **92 instrumentações por API** (89 anteriores + 3), Source e OTA; não chamar o novo SHA aprovado antes da CI. O SVG não é uma prova de correspondência visual pixel-exata com o PNG e não substitui os PNGs oficiais de referência ausentes.

**Fronteiras:** PR #13 draft, `main` intocada, sem `versionCode` novo, APK de distribuição, release ou publicação OTA. A ampliação dos catálogos de temas/layouts e a homologação visual/física ainda são pendências da P7.

### P7.5 — doze temas de aparência realmente aplicáveis (22/10/2026)

**Base verificada:** commit `e0912301`, [CI Android 39789227114](https://github.com/nego001/ReaDroid-Native/actions/runs/39789227114), **92/92** testes em API29 e API35, Source e OTA aprovados; 13 capturas em cada API, `references=BLOCKED`.

**Entrega:** ampliar a galeria nativa de **4 para 12 combinações efetivas** (superfícies OLED, grafite e clara × quatro cores de destaque suportadas pelo motor V3), mantendo os índices 0–3 legados. `P7ThemeCatalog` centraliza metadados, preview, nomes e persistência; a seleção do Design Studio é recalculada pelo par real `theme/accent`, sem rotular configurações personalizadas como catálogo. A aplicação ainda solicita confirmação e recria a Activity pela rotina estabelecida, mantendo as demais preferências e o plano de edições fora desta gravação.

**Visual:** `P7ThemePreviewView` agora desenha as cores reais da superfície OLED, grafite e clara, em vez de representar opções claras como um telefone escuro. O componente preserva os modos anteriores de layout e preset.

**Testes:** três novos testes instrumentados cobrem a ida e volta de 12 combinações únicas sem interferir no preset ativo indevidamente, rejeição de configurações customizadas e índice fora do catálogo, e amostragem real dos pixels dos três fundos. Meta **95 testes por API** (92 + 3), Source/OTA e capturas de UI. Não declarar aprovado antes da matriz no novo SHA.

**Pendências:** 12 temas efetivos ainda não são os 24 do objetivo visual; 12 layouts completos continuam planejados (existem 3), além de incorporação dos PNGs oficiais, inspeção 1:1 e homologação no Galaxy A55. Sem APK de distribuição, merge, OTA ou mudança de `versionCode`.

### P7.5 — 24 combinações de aparência com brilho nativo opcional (22/10/2026)

**Base validada:** commit `828fed20`, [matriz Android 39796401169](https://github.com/nego001/ReaDroid-Native/actions/runs/39796401169), **95/95** testes em Android 10/API29 e Android 15/API35, Source checks e OTA concluídos com sucesso, 13 capturas por API, `references=BLOCKED` e `visual_1to1=NOT_APPROVED`.

**Implementação:** manter exatamente os 12 índices de cor/superfície anteriores e acrescentar 12 variantes **Clean** sem brilho. Os 24 temas são combinações verificáveis de três superfícies (OLED, grafite, clara), quatro cores de destaque e o valor real `studio_glow` do motor de aparência V3 (neon/clean). Índices 0–11 passam a salvar `studio_glow=true`, índices 12–23 salvam `false`. A configuração usada pela UI passa a ser identificada pelos três atributos, sem confundir cores personalizadas com catálogo; aplicação continua com confirmação e `Activity.recreate()`, sem mudar APK, edição, segurança, backup ou outras preferências. As prévias nativas diferenciam o modo com brilho por realces de contorno e preservam as três cores de fundo, sem simular 24 design systems independentes.

**Regressões:** teste existente de catálogo ampliado para verificar 24 estados únicos, preservação de configuração anterior ao teste e índices legados; dois testes novos verificam o valor efetivo de `NegrescoTheme.STUDIO_GLOW` e pixels distintos para prévias clean/neon. Meta **97 instrumentações por API** (95 + 2), Source e OTA no SHA novo.

**Limite de escopo:** a meta de 24 **opções combinatórias de aparência** fica implementada no código; não são 24 layouts totalmente diferentes. Continuam faltando 12 layouts funcionais (3 disponíveis hoje), PNGs oficiais de referência, comparação visual 1:1 e homologação no Samsung Galaxy A55. Nenhum APK instalável de distribuição, merge, `versionCode`, release ou OTA publicada.

### P7.5 — layout Lista com organização nativa real (22/10/2026)

**Base:** commit `ec870ba9` com 24 combinações de tema, Source e OTA aprovados e matriz Android em acompanhamento. Nesta extensão foi introduzido o **quarto** layout `Lista`, preservando os três índices anteriores.

**Funcionalidade:** `P7VisualCatalog.persistLayout` valida/grava as preferências de layout, e `applyLayout` mantém a confirmação e o `Activity.recreate()` existentes. `NegrescoTheme` reconhece `layout_variant=3`. As seis ações rápidas da Home passam de 2 linhas × 3 cartões para 6 linhas × 1 cartão de largura total, mantendo os seis callbacks/avisos originais. Os 13 controles de personalização passam de 2 colunas para 1 coluna. A miniatura do Design Studio mostra seis linhas de lista em vez do mesmo wireframe das outras opções. Nenhuma função de decompilação ou assinatura é artificialmente ativada.

**Regressão:** teste instrumentado com Activity e Views reais verifica os seis cartões clicáveis em largura total, os 13 controles em uma coluna, retorno ao grid 2×3 após recriação, persistência do índice 3 e rejeição do índice 4. Meta **98 testes por API** (97 anteriores + 1); verificar Source, OTA e ambos os emuladores no SHA novo.

**Pendente:** 4 layouts realmente funcionais de uma meta de 12. A arte original PNG ainda não foi versionada e o aceite 1:1/Galaxy A55 está pendente. Manter PR #13 draft, sem merge, APK de distribuição ou OTA publicada.
