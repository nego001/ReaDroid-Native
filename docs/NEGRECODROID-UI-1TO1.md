# P7 — NegrecoDroid: interface e identidade visual 1:1

> **Aprovação visual:** 20/10/2026. **Situação: EM IMPLEMENTAÇÃO NA BRANCH P7; mockup completo ainda NÃO implementado.**
> **Tarefa oficial:** [issue #11](https://github.com/nego001/ReaDroid-Native/issues/11).
> **Nome oficial exibido ao usuário:** `NegrecoDroid` — grafia exata, sem "s".
> **Referência obrigatória:** as duas artes aprovadas pelo proprietário nesta conversa.
> **Trabalho funcional prioritário:** estabilização Android (explorador SQLite, SAF, plano de edição, recuperação e exportação).

## 0. Congelamento da referência / DoD

**Fonte da verdade visual:**
- `negrecodroid_controle_total_de_apks.png` — 1448 × 1086 — SHA-256 `d0232e8a93d793c5cde3d564f90c8c5ecdd870bee497558db0442bf98326461b`.
- `identidade_negrecodroid_em_neon_azul.png` — 1448 × 1086 — SHA-256 `25f93465b1ad0da45398201d9718cc070f3ba7fce11f84bf81e973c0b06d2765`.

**Os arquivos binários PNG devem ser adicionados ao repositório** em `design/reference/p7/` antes de aprovar correspondência visual 1:1. Esta primeira etapa contém a **especificação e identificação por hash**, não anexa esses PNGs ao GitHub. Se existir uma versão alterada, aprovar formalmente outra referência em vez de substituí-la silenciosamente. Não converter mockup em screenshot falsamente descrita como app real.

**Interpretação da exigência 1:1:** reconstruir hierarquia, geometria, espaçamento, escala relativa, estilo, cores, ícones e superfícies da arte. No telefone o app terá três páginas funcionais separadas; a prancha artística com três celulares não é a tela inicial do APK. Diferentes tamanhos, barras do SO, fontes e insets precisam de adaptação responsiva.

## 1. Estrutura exata das telas do conceito

### 1.1 HOME / INÍCIO (celular esquerdo)
1. Fundo OLED preto (`#000000`) com superfícies carvão/azul-escuro e detalhes ciano/azul, contraste nítido.
2. Status bar do sistema, menu superior esquerdo e configurações à direita; padding respeitando safe areas.
3. Lockup `NegrecoDroid` no topo: `Negreco` em branco/prata, `Droid` em azul elétrico. Subtítulo técnico curto; preservar grafia.
4. Arte do mascote encapuzado com olhos neon azul à direita do cabeçalho, como arte **decorativa**; não bloquear informações.
5. Card de boas-vindas com título "Olá, Desenvolvedor" e texto curto. Ajustar acessibilidade e escalas de fonte.
6. Quatro cards de estatísticas em grade 2×2, cada um com ícone, contagem e legenda: Projetos, Arquivos, Builds e Segurança.
7. Cabeçalho "Projetos recentes" com ação "Ver todos" e linhas de projetos reais, metadados e menu de opções. Os nomes Spotify/Netflix/YouTube da referência são **somente amostras artísticas**, jamais alegar que o usuário possui esses projetos.
8. Cabeçalho "Ações rápidas" e grade 3×2 de cards "Abrir APK", "Analisar", "Build APK", "Decompilar", "Editar Smali", "Assinar APK". Habilitar **somente** operações implementadas; sinalizar claramente indisponíveis. Não confundir exportação unsigned com assinatura válida.
9. Bottom navigation com CINCO abas de ícone + legenda, Início ativo azul.

### 1.2 EXPLORADOR DE ARQUIVOS (celular central)
1. Barra superior com Voltar, título "Explorador de Arquivos", subtítulo técnico e menu de opções.
2. Card com ícone/metadados do APK aberto e indicador "Plano de Edição" com quantidade **verdadeira**.
3. Breadcrumbs com setas e pastas selecionáveis; abre pasta sem perder plano de edição.
4. Campo de busca grande com lupa, hint em português; estados de busca, loading e vazio.
5. Chips de filtros: Todos, Smali, Recursos, Imagens, XML; filtro que ainda não tiver motor funcional ficará desabilitado ou ausente (não fingir).
6. Listagem de itens com ícones azuis para diretórios e documentos, nome à esquerda, metadados complementares e menu à direita.
7. Listagem conectada à camada real `ApkDiskIndex` e/ou ao fluxo legado de maneira segura, com paginação/virtualização; nunca materializar telas intermináveis com `TextView` para 100 mil entradas.
8. Preservar preview, edição textual suportada, classificação, offsets de paginação, exportação SAF e hash do original.
9. Barra inferior com Arquivos ativo azul.

### 1.3 DESIGN STUDIO (celular direito)
1. Header "Design Studio", ícone de paleta, subtítulo de personalização e menu.
2. Navegação interna de abas com "Temas", "Layout", "Ícones", "Logotipo".
3. Galeria horizontal de miniaturas de temas, seleção com borda azul e check; "Ver todos".
4. Opções de layout em miniaturas organizadas com seleção e check.
5. Dois cards grandes: "Criador de Ícones" e "Logo Studio" com artes vetoriais, descrição curta e seta de ação.
6. Carrossel de "Presets de Aparência" com miniaturas, nome, borda de seleção e estados.
7. Barra inferior com Design ativo azul.
8. Tema, layout e presets devem mudar UI real e funcionar durante projeto aberto; mudanças não podem apagar plano de edições, relatório ou índice.

## 2. Identidade da marca (segunda referência)

**Lockup principal**
- Símbolo estilizado em formato de escudo hexagonal com monograma `N` angular central e circuitos terminando em nós circulares.
- Paleta: preto profundo, azul elétrico/ciano, prata claro; gradientes e reflexos discretos apenas quando não prejudicarem desempenho.
- Texto **`NegrecoDroid`** com `Negreco` prateado e `Droid` azul, sem espaçamentos ou grafia inventados.
- Versões: logo principal vertical, logo horizontal com símbolo à esquerda, marca monocromática, símbolo isolado e ícone Android com quadrado arredondado.
- `Design Studio` é nome da seção/módulo, **não** deve substituir o nome do aplicativo no launcher.
- Vetor original ajustável para mdpi..xxxhdpi, Android adaptive icon foreground/background/monochrome, splash Android, verificação de contraste e recorte de ícone redondo.
- Não embutir branding de terceiros mostrado apenas como dado ilustrativo. Não alterar o package name ou a assinatura automaticamente.

## 3. Tokens e ergonomia

| Papel | Direção inicial (medir e confirmar sobre PNG) |
| --- | --- |
| Fundo base | #000000 OLED |
| Superfícies | grafite escuro / azul-preto |
| Destaques | azul elétrico próximo de #169FFF a #579FF7, ciano para reflexo |
| Tipografia | branco e cinza legível, hierarquia com pesos nítidos |
| Bordas | fino contorno azul em seleção, contorno carvão nos demais |
| Cartões | cantos arredondados, padding consistente, sem neon excessivo |
| Ícones | lineares azuis/brancos, estados selecionados preenchidos ou acesos |
| Layout | respiro vertical preservado; conteúdo rolável; bottom nav fixa |
| Movimentos | sutis, desativáveis, respeitando 'Remover animações' do Android |

Os tokens acima **não são medidas pixel-exatas**; registrar amostragem das imagens após subir as referências. Escolher um **viewport canônico físico** e registrar density, resolução, API, escala de texto, orientação e insets para comparação consistente.

## 4. Funcionalidade REAL vs arte demonstrativa

A referência artística mostra elementos aspiracionais. Na implementação, cada elemento deve ter contrato:
- **Existente:** abrir APK via SAF, navegar/consultar diretórios, ver relatório, editar textos permitidos, plano de edição, exportar arquivo derivado sem assinatura quando aplicável, configurações visuais já implementadas.
- **Planejado:** decompilação/Smali completa, assinatura operacional homologada, Icon Creator, Logo Studio, layouts editáveis amplos, galerias avançadas. Exibir "Em desenvolvimento" e não criar botões com ação fictícia.
- **Dinâmico:** contadores, projetos, hashes, tamanho, datas, riscos, caminhos, conteúdo da busca. Nenhum valor ornamental vira "dado real".
- **Acessibilidade:** ícones rotulados, foco visível, estados anunciados, alvo mínimo adequado, contraste, TalkBack, texto escalável, sem conteúdo crítico atrás do mascote.

## 5. Implementação faseada — NÃO iniciar enquanto P0/P1 bloquear

| Subfase | Entrega verificável |
| --- | --- |
| P7.0 | PNGs originais versionados por hash, medição, screenshot baseline, contratos de componentes |
| P7.1 | Design system / tokens nativos, marca vetor `N`, ícone/splash, sem tocar em lógica de análise |
| P7.2 | Home funcional 1:1 (cards dinâmicos, projeto, atalhos reais) |
| P7.3 | Explorador 1:1 com SQLite, filtro, navegação, estado e exportação preservados |
| P7.4 | Design Studio 1:1, galeria de temas, layouts selecionáveis e presets funcionais |
| P7.5 | Criadores de ícones e logotipos com formatos limitados e exportação segura |
| P7.6 | Comparação de screenshots reais x referências, testes de funcionalidade, acessibilidade e desempenho |
| P7.7 | Homologação física Samsung Galaxy A55 e aprovação visual final do usuário |

**Dependências:** issue [#1](https://github.com/nego001/ReaDroid-Native/issues/1) redesenho dos diálogos; [#2](https://github.com/nego001/ReaDroid-Native/issues/2) F02 explorador; [#9](https://github.com/nego001/ReaDroid-Native/issues/9) plano mestre e fase P6. O cadastro desta etapa **não autoriza quebrar a base nem antecipar migração do repositório**.

## 6. Validadores e critério de aceite

- **Screenshots:** captura de Home, Arquivos e Design em emulador; comparação em dispositivo/viewport canônico contra cada recorte da arte, com evidências e diffs. Tolerâncias por antialias, tipografia do SO e pixel density documentadas; divergências visuais relevantes corrigidas.
- **Navegação:** 5 abas, retorno, seleção, estado ao girar/trocar tema, Android 10 e Android 15, telas estreitas 320 dp, barras edge-to-edge.
- **Layout:** conteúdo legível em fontes ampliadas 130–200%, teclado aberto, modo claro/escuro quando aplicável.
- **Funcionalidade:** importação SAF, índice SQLite (3 páginas/301 entradas), busca, edição, plano, exportação, hash original, RecoveryVault sem regressões.
- **Marca:** nome correto em launcher e todas as telas, adaptive icon sem clipping, splash sem flicker problemático.
- **Performance:** sem travamentos ao navegar, sem telas estáticas disfarçadas de componentes, sem perda de sessão ao trocar tema.
- **Segurança:** APK original imutável, sem enviar dados à rede nem instalar/assinar automaticamente; logs sem segredos.
- **Homologação:** aprovação de CI, emulador e teste físico; nenhum teste pendente será chamado de PASS.

## 7. Estado deste registro

- [x] Nova etapa P7 especificada.
- [x] Issue #11 aberta.
- [ ] PNGs incorporados na árvore GitHub.
- [ ] Componentes visuais reproduzidos no APK.
- [ ] Logo/ícone exportados como assets definitivos.
- [ ] Screenshots instrumentados e validadores de fidelidade.
- [ ] Aceite final 1:1 em Android.

**Importante:** criação desta documentação **não implementa a interface**. Mudanças de código ocorrerão em PRs de entrega da P7, apenas quando iniciada a fase, para preservar a base estável.


## 8. Entrega técnica P7.1-A (20/10/2026; branch isolada)

- [x] Criar marca vetorial SVG editável em `design/brand/negrecodroid-mark-master.svg`; arte do **primeiro passe**, a refinar com comparação à prancha oficial.
- [x] Criar vetores Android para ícone colorido e monocromático e recurso adaptive icon API 26+.
- [x] Substituir rótulos de launcher `NegrescoDroid` por **`NegrecoDroid`** em app debug/QA, sem alterar applicationId, assinatura ou armazenamento.
- [x] Substituir a marca genérica do cabeçalho por vetor de escudo/N nativo.
- [x] Migrar apenas o nome de marca predefinido de instalações anteriores; nomes personalizados não são substituídos.
- [x] Adicionar testes instrumentados de carregamento do recurso, nome e launcher icon.
- [ ] Validar build, Android 10/15, QA e inspeção visual com evidências dos workflows da PR; não registrar PASS antecipadamente.
- [ ] Incorporar os PNGs aprovados no GitHub; **a identificação via hash não substitui as imagens**.
- [ ] Refinar desenho da logo e ícone 1:1, com validação visual lado a lado.
- [ ] Construir as três telas completas e funcionais. A navegação existente ainda não foi redesenhada.

A P7.1-A é **apenas fundação de identidade visual**. Não altera importação, recuperação, edit plan, SQLite ou exportação e não representa o fechamento de P7.1–P7.7.


## 9. Entrega P7.2-A — Home funcional (20/10/2026)

**Implementado em branch de trabalho, aguardando homologação CI e revisão visual:**

- [x] `P7MascotView`: mascote escuro com olhos ciano desenhado por Canvas nativo, sem bitmap nem efeitos pesados (aproximação, **ainda não validada 1:1** contra a arte original).
- [x] `StudioDashboard.compose`: saudação "Olá, Desenvolvedor", texto de introdução, mascote e cartão do projeto; preserva o botão real de seleção SAF.
- [x] `P7HomeOverview`: quatro cartões em grade 2×2 e seção "Projetos recentes" baseada **no APK aberto na sessão**, com aviso honesto quando não há histórico persistente. Nunca inventar 12 projetos, builds ou zero ameaças.
- [x] Seis atalhos: quatro abas reais anteriores (favorito preservado), "Abrir APK" via seletor do Android e "Plano de edição" ligado à revisão existente. Grade responsiva de duas colunas para preservar acessibilidade.
- [x] Atualização dos contadores ao concluir análise, iniciar novo APK, retornar à Home e restaurar rotação/tema; projeto e plano de edição preservados pela arquitetura existente.
- [x] `P7HomeOverviewInstrumentedTest` de estados vazio/ativo/retorno; adicionado ao workflow P7 API 29 e 35.
- [x] Corrigido workflow CI P7 que falhava por variável `SDK_ROOT` definida em etapa anterior, não dentro do script do emulador. Falha anterior era do próprio script `aapt`, não evidência de APK quebrado.
- [ ] Aguardar execução de CI **no commit final** e registrar evidência de builds e tests, sem presumir sucesso.
- [ ] Fazer comparação lado a lado com mockup da Home e homologação Samsung física. Projeto P7.2 não concluído até obter a semelhança visual aprovada.

**Escopo explicitamente parcial:** P7.2-A é uma primeira implementação nativa da Home; a fidelidade 1:1 integral depende dos PNGs versionados, assets mais refinados, navegação final e testes visuais. Não modificar licença, assinatura, OTA, índice SQLite, recuperação ou exportação nesta entrega.
