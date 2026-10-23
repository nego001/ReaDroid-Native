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
