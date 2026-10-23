# P7 — auditoria visual cruzada Android 10/15 (23/10/2026)

**Estado do código:** commit `18a2dcd0` aprovado nos workflows [P7](https://github.com/nego001/ReaDroid-Native/actions/runs/39896431958), [Source](https://github.com/nego001/ReaDroid-Native/actions/runs/39896431971) e [OTA](https://github.com/nego001/ReaDroid-Native/actions/runs/39896431944). A instrumentação terminou com **132/132 testes** em cada API. Foram obtidas 13 capturas por emulador.

## Referências e proveniência

As duas artes originais da issue #11 foram recuperadas em uma cópia local da Biblioteca do proprietário e tiveram suas dimensões (1448×1086) e SHA-256 conferidos:

- `negrecodroid_controle_total_de_apks.png`: `d0232e8a93d793c5cde3d564f90c8c5ecdd870bee497558db0442bf98326461b`
- `identidade_negrecodroid_em_neon_azul.png`: `25f93465b1ad0da45398201d9718cc070f3ba7fce11f84bf81e973c0b06d2765`

**Não foram incorporadas a esta branch.** As referências são VERIFICADAS na cópia local, mas seguem **BLOCKED no GitHub CI** até que os arquivos binários originais sejam versionados em `design/reference/p7/`. O painel não insere screenshots no lugar de referências. Não publicar status VERIFIED remotamente com base apenas nesta documentação.

## Achados das capturas reais

| Área | Observação concreta | Pendência de avaliação |
|---|---|---|
| Home | Saudação, quatro estatísticas, histórico, seis ações e navegação inferior são reais; o mascote e o cabeçalho parecem mais compactos que na prancha. | Medir geometria e tipografia no viewport canônico com a referência oficial. |
| Explorer | Existe estado vazio honesto, busca, barra de filtros e plano de edição; as capturas de CI não carregaram APK. | Capturar com APK **sintético** e validar listagem e breadcrumb populados, sem imitar dados fictícios do conceito. |
| Design | Quatro abas, galeria de temas, opções de layout, dois criadores e presets aparecem. | Conferir miniaturas, dimensões, espaçamento, ícones e comportamento em fontes grandes contra a referência. |
| Icon/Logo Creator | Editores foram abertos e capturados no workflow. | Verificar aparência/legibilidade dos diálogos e resultado real de exportação em ensaio separado. |

Não é apropriado calcular erro pixel a pixel da prancha de marketing com perspectiva de telefone. O critério 1:1 precisa primeiro de **recortes, medidas e viewport canônico aprovados**.

## Novo fluxo de auditoria cruzada

`tools/p7_cross_api_review.py` valida os manifestos e bytes de todas as **26** capturas, exibe imagens de Home/Explorer/Design das duas APIs no mesmo HTML offline e embute as duas referências originais **somente** quando `tools/p7_reference_assets.py` confirmar ambos os hashes. Estado visual e físico sempre permanecem NOT_APPROVED. O job de agregação executa **após** a matriz de emuladores e salva o painel como artefato de QA, sem APK.

Uso local (com os dois artefatos já extraídos):

```bash
python3 tools/p7_cross_api_review.py \
  --api29-dir artifacts/p7-brand-android-29 \
  --api35-dir artifacts/p7-brand-android-35 \
  --reference-dir design/reference/p7 \
  --output p7-cross-api-review.html
```

Os testes unitários rejeitam manifesto com aprovação inventada ou captura ausente, além de exigirem o painel bloqueado quando faltam artes oficiais.

**Restrições:** PR #13 permanece draft, sem merge na main, alteração de APK/assinatura, aumento de versão ou OTA. A homologação física Galaxy A55/TalkBack continua pendente.


## P7.6.1 — Captura do Explorador com APK sintético (23/10/2026)

A nova instrumentação `P7ExplorerPopulatedCaptureInstrumentedTest` gera ZIP **sintético** em cache, indexa-o via `ApkDiskIndex` (SQLite) e carrega seu relatório de teste no `MainActivity` real. Abre a aba Arquivos, exige pastas `assets/`, `res/` e arquivo `AndroidManifest.xml` e obtém um screenshot verdadeiro do sistema Android. O cabeçalho anuncia **APK sintético de QA**; nenhum arquivo pessoal é analisado, instalado, assinado ou exportado. A prova compara os bytes do ZIP antes/depois e exclui a cópia de teste no fim.

O workflow extrai apenas o PNG de captura via `adb run-as`, depois mantém os smokes anteriores. O manifesto passa a validar **14 capturas por API, 28 totais**, incluindo as duas situações distintas: Explorer vazio e Explorer de teste populado. Testes locais do inventário, painel e comparação foram atualizados para não permitir omissões silenciosas.

Essa tela testa a renderização com conteúdo sintético, **não certifica o processo de importação SAF nem decodificação real de AndroidManifest.xml**. Fidelidade visual 1:1 e Galaxy A55 continuam bloqueados. Não fazer merge nem publicar novo APK/OTA até aceite.


## P7.7 — auditoria de 28/28 telas realmente exibidas (23/10/2026)

**CI anterior aprovada:** [39909205962](https://github.com/nego001/ReaDroid-Native/actions/runs/39909205962), com **133/133** instrumentados em API29 e API35, 14 capturas verificadas por API, relatório cruzado, Source e OTA verdes.

A revisão anterior validava 28 arquivos, mas colocava apenas quatro pares de telas no relatório: Início, Explorador vazio, Explorador sintético e Design. Isso escondia do comparativo a Segurança, Construir, criadores, telas compactas (320 dp/130%) e fontes de 200%.

**Correção:** o painel passa a apresentar **todos os 14 pares** em ordem, navegáveis por seção, com ambas as imagens originais incorporadas em HTML, dimensões, SHA-256 e rótulos por cenário. Os unit tests exigem 28 imagens renderizadas e 14 pares, falhando se uma tela desaparecer do comparativo. O painel continua estático e offline, com `visual_1to1=NOT_APPROVED` e `physical=NOT_APPROVED`.

O critério de aceitação visual continua sendo avaliação humana em viewport canônico, porque as referências aprovadas são artes promocionais em perspectiva. As PNGs oficiais permanecem ausentes do repositório até o upload dos binários com SHA original.


## P7.8 — Criadores nativos com fundo temático (23/10/2026)

**Ponto de partida:** [CI P7.7 #39963543711](https://github.com/nego001/ReaDroid-Native/actions/runs/39963543711) verde em API29/API35 e comparativo 28/28.

Nas screenshots do Icon Creator e Logo Studio o Android aplicava um painel **cinza #424242**, incompatível com os cartões escuros do Design Studio. `NegrescoTheme.styleStudioDialog` agora aplica ao `AlertDialog` real o painel da paleta atual, borda fina e raio de canto; o botão Fechar respeita a cor de destaque configurada.

A hierarquia de ações deixa o **PNG principal** em botão preenchido com degradê sutil e o **SVG secundário** em botão de contorno sobre o fundo da interface. Ambos continuam acessíveis, com alvos de 48 dp, labels e os mesmos callbacks para exportação via SAF; nenhuma exportação automática é feita. O tema claro, OLED e cores personalizadas utilizam os tokens de aparência existentes, sem gravar novas preferências.

Dois testes instrumentados novos conferem, nos **dois editores reais**, a cor efetiva de fundo do diálogo, o texto de fechamento, o contraste semântico dos botões, acessibilidade e os cliques disponíveis. **Meta após o commit:** 135 testes por API; não considerar validado até concluir matriz e screenshots.

Não muda app id, versão, política de APK, assinatura, OTA nem `main`; fidelidade 1:1 e A55 físico continuam `NOT_APPROVED`.

 
## P7.9 — captura do Explorer não pode conter ANR do Android

A auditoria de capturas antigas detectou uma falha de qualidade em `p7-explorer-populated-android-35.png` do pacote P7.7: havia um modal claro de sistema **“Pixel Launcher isn't responding”** cobrindo as pastas, mesmo que o PNG, seu SHA e os testes funcionais fossem válidos. Na P7.8, a mesma captura foi obtida **sem o modal**, mas isso antes não era um requisito automatizado.

A instrumentação de evidência `P7ExplorerPopulatedCaptureInstrumentedTest` agora verifica `UiAutomation.getRootInActiveWindow()` e exige que o dono da janela focada seja `com.readroid.app` antes e depois de `takeScreenshot()`. Também mede 35 amostras da área central, rejeitando o padrão de grande modal de sistema claro que ocorreu no tema escuro de QA. Teste sintético reproduz uma caixa clara central e exige rejeição, e a tela escura limpa é aceita.

Este filtro é **focado no Explorador sintético no tema escuro da CI**, não substitui inspeção visual de todas as telas nem identifica todo tipo de modal. O objetivo é impedir que uma sobreposição conhecida do emulador passe por imagem limpa. Meta: **136 testes instrumentados por API**, captura populada limpa, inventário 28/28 e relatório cruzado; estado não aprovado até o workflow finalizar. Sem alteração do app de produção, OTA, `main` ou política de APK.


### P7.9.1 — seleção explícita do único método de captura

A suíte integral inclui o novo teste de rejeição de modal claro mais o teste que gera o PNG, somando 136 testes por API. O script `tools/p7_capture_populated.sh`, entretanto, executa a instrumentação **isolada** após Gradle e exige `OK (1 test)`. Para impedir o conflito, ele agora passa `-e class com.readroid.app.P7ExplorerPopulatedCaptureInstrumentedTest#captureRealActivityWithIndexedSyntheticApk`; não roda o teste sintético puro uma segunda vez. O teste de shell simulado valida o nome completo do método invocado.

 
### P7.9.2 — correção do contrato de janela acessível

A [CI #39969080093](https://github.com/nego001/ReaDroid-Native/actions/runs/39969080093) revelou no Android 10 que `UiAutomation.getRootInActiveWindow()` retornou `null` no emulador, mesmo com o Explorador funcional, causando **uma falha dentre 136 testes instrumentados**. Isso significa que exigir sempre um nó de acessibilidade era uma premissa inválida.

O teste mantém a exigência de janela em primeiro plano via `ActivityScenario.onActivity(... decor.hasWindowFocus())`. Quando a árvore de acessibilidade está disponível, a propriedade do pacote deve continuar sendo `com.readroid.app`. Quando ela está indisponível, o teste **não aprova simplesmente por falta de dados**: verifica obrigatoriamente foco real do aplicativo antes e depois, além da inspeção dos pixels da imagem capturada contra o modal claro de ANR conhecido. O teste de caixa clara sintética e a validação de SHA, PNG e todas as imagens permanecem ativos. API35 e API29 devem ser reexecutados antes de considerar P7.9 verde.

 
## P7.10 — rótulos da barra inferior em fontes ampliadas (23/10/2026)

**Ponto de partida:** CI [39970493729](https://github.com/nego001/ReaDroid-Native/actions/runs/39970493729) validou `136/136` testes nas APIs 29 e 35, 28 capturas e relatório cruzado. A inspeção visual das telas de **320 dp/130%** e **fonte 200%** revelou quebra de palavras na navegação inferior, especialmente `Seguranç/a` e `Arquiv/os`, embora os cinco controles permanecessem acessíveis.

A barra inferior agora usa rótulos visuais curtos **somente em escalas problemáticas**: `Seg.` em 320 dp/130% ou escala efetiva ≥165%; `Arqs.` na escala ≥165%. Na resolução/fonte normal continua `Segurança` e `Arquivos`, como nas referências. Rótulos são sempre **uma linha com elipse como último recurso**, sem cortar palavras no meio. Nomes para TalkBack, navegação, foco e testes de toque continuam completos: `Seção Segurança, selecionada` etc. A altura reservada adapta-se à versão de uma linha sem reduzir o alvo mínimo.

A instrumentação acrescenta um teste para oito cenários de escala e para as cinco labels completas dos controles clicáveis. Meta: **137 testes por API**, 28 screenshots e smoke nas escalas 320dp/130% e 200%. Não afirmar êxito antes da CI da alteração. Não modifica dados, assinatura, versão, APK/OTA ou branch principal.


## P7.11 — as quatro abas do Design Studio visíveis em 320dp/130%

**Base aprovada:** [P7.10, CI #39977864175](https://github.com/nego001/ReaDroid-Native/actions/runs/39977864175), tentativa 2, 137/137 testes por API, inventário 28/28 e auditoria cruzada verde.

Auditoria visual da captura `p7-compact-design-android-35.png`: a aba **Logotipo** aparece truncada no lado direito porque 4 abas com largura mínima de 79dp e espaçamento fixo somam mais que a região útil da tela de 320dp. O scrolling permite alcançá-la, porém o usuário não vê as quatro áreas do Studio de imediato.

Ajuste responsivo conservador em `P7DesignStudio`: somente abaixo de 360dp e com escala efetiva ≤140%, reduzir o mínimo visual para **66dp**, padding para **4dp** e separação para **3dp**; preservar **48dp** de altura mínima, labels integrais e papéis de botão no TalkBack. Com escala de 200% ou escala combinada elevada, **manter a rolagem horizontal** e o `revealActiveTab()`, evitando comprimir texto legível.

O smoke real em 320dp/130% exige agora os **quatro** destinos visíveis e dentro dos limites da tela, além do botão Ver todos, total de 5 alvos de pelo menos 48dp. Novos testes de regressão verificam a seleção da grade compacta e rejeitam a última aba fora do viewport. Meta: **138 testes instrumentados por API** com screenshots 28/28; nenhuma homologação antes da CI. Não altera exportação, APK, OTA, assinatura ou `main`.


## P7.12 — cartão do Explorador não deve truncar o nome do APK

**Base verde:** [CI P7.11 #39981407261](https://github.com/nego001/ReaDroid-Native/actions/runs/39981407261), **138/138** instrumentados por API29 e API35, 28 PNGs e cross-API verde.

Achado visual nas capturas P7.11 de `p7-compact-arquivos-android-35.png` (320dp/130%) e `p7-large-text-arquivos-android-35.png` (200%): o cartão de projeto mostra **“Nenhum AP...”** e corta também a descrição. A causa é o chip de plano de edições com largura fixa **113dp** disputando a mesma linha com o nome do APK.

`P7ExplorerChrome` agora empilha **resumo do APK na linha superior** e **botão de plano de edições abaixo, largura inteira** quando `screenWidthDp < 360` ou escala de fonte combinada `≥ 165%`. Nome e descrição podem ocupar duas linhas nessas condições, com elipse somente para strings muito grandes. A aparência normal permanece horizontal como na referência; a ação `Abrir plano de edição` mantém seu callback, botão focável e altura mínima 48dp. Não cria APK fictício nem altera estado, indexação, exportação ou assinaturas.

Teste instrumentado novo cobre matriz de larguras/escalas, orientação real, limites de linhas e ação nativa. Smokes reais de 320dp/130% e 200% exigem que o nome **“Nenhum APK selecionado”** esteja acima do chip de plano, sem recobrimento. Unidade Python simula bounds corretos e falhos. **Meta: 139 instrumentados por API**. Não homologar sem CI e PNGs do commit.

Sem alterações de versão, OTA, `main`, referências binárias ausentes no repositório ou política do APK do usuário.


### P7.12.1 — instrumentação de captura em fase isolada para Android 15

Na [CI #39990100943](https://github.com/nego001/ReaDroid-Native/actions/runs/39990100943), o Android 10 passou **139/139** instrumentados e gerou as 14 PNGs; o Android 15 executou 139 testes em duas tentativas, mas **o único erro nas duas** foi `P7ExplorerPopulatedCaptureInstrumentedTest.captureRealActivityWithIndexedSyntheticApk`: `Explorer Activity lost foreground window focus`. Os outros 138 testes passaram. O risco da sobreposição de janela do sistema deve continuar sendo rejeitado, sem pular verificação de foco nem aceitar screenshots falsas.

A workflow agora seleciona somente `P7ExplorerPopulatedCaptureInstrumentedTest#detectsSyntheticSystemOverlayBeforeEvidenceExport` na **suíte Gradle geral (138 testes)**; a captura real `#captureRealActivityWithIndexedSyntheticApk` continua executada pela fase **isolada** `tools/p7_capture_populated.sh` após reinstalação do app/teste. O teste isolado exige `OK (1 test)`, foco em primeiro plano, amostragem anti-ANR, PNG válido com SHA e dimensões. Assim **o total permanece 138 + 1 = 139 testes por API**, não 139 no relatório XML principal. Ambos os blocos precisam passar antes de gerar o inventário de 14 PNGs. Teste local de contrato garante os seletores e a fase separada.

Esse isolamento reduz a disputa pelo foco na largada do emulador; **não garante** sucesso em todos os ambientes nem descarta problema real. Se o APK não ganhar foco na fase isolada, a CI deve falhar. Nova execução necessária antes de declarar aprovação. Sem alteração no aplicativo de produção, em arquivos APK, `main` ou OTA.
