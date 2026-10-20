# NegrecoDroid P7 — Preview 7: projetos recentes reais

**Data:** 2026-10-20  
**Versão:** `3.0.0-preview.7-p7` (`versionCode 7`)  
**Branch:** `feature/p7-negrecodroid-visual-foundation`  
**Código:** [PR #13](https://github.com/nego001/ReaDroid-Native/pull/13) · [Checklist P7 #11](https://github.com/nego001/ReaDroid-Native/issues/11)

> Preview Android QA independente. **Não é o aceite final 1:1**, nem deve ser promovida à `main` ou OTA sem confirmação do CI da revisão exata.

## Novo histórico da Home

- `P7ProjectHistory`: histórico local limitado a **12 referências SAF**. O Android só deixa a entrada visível se ainda possuir permissão de leitura persistida para aquele documento.
- Cada referência tem nome real do documento, pacote extraído do APK analisado e data do último acesso. **Nunca armazena bytes do APK no histórico**, assinatura, chaves, relatório ou plano de edições.
- Entradas duplicadas por URI são removidas, com o item mais recente no começo. URIs externas ao esquema `content`, metadados malformados, entradas repetidas e documentos sem autorização são descartados.
- O APK é reanalisado sempre que um item do histórico é escolhido; não confia em relatórios antigos nem em snapshots de segurança.
- `P7HomeOverview`: até **três linhas reais** com nomes, pacotes e datas, contador de projetos verificado e botão `Ver todos` que abre a lista de até 12.
- A lista pode ser limpa mediante confirmação. Isso remove só **metadados locais do histórico**, não o APK original, a cópia temporária ativa, o plano de edições, nem revoga outras permissões do Android.
- Sem permissão persistível do fornecedor de arquivos, o APK continua acessível na sessão corrente, mas **não** vira um histórico morto.
- Ao selecionar outro projeto com edições pendentes, uma confirmação avisa que a troca descarta alterações não exportadas e recomenda salvar um checkpoint criptografado antes da troca.

## Regras de segurança preservadas

- `AndroidManifest.xml` mantém `android:allowBackup="false"`; o histórico usa SharedPreferences privadas do próprio app.
- `analysisSequence` é `volatile` para impedir que análises concorrentes validem resultados obsoletos.
- A autorização SAF é obtida somente via `takePersistableUriPermission`, quando o seletor conceder READ. Falha na persistência não impede uma importação de uso único.
- O histórico **não concede acesso** ao que o Android não autorizou.
- Não há sincronização remota de projetos recentes nem exclusão de APKs do usuário quando se limpa a lista.
- A edição textual mantém as regras existentes de formatos permitidos; não transforma XML binário em texto editável.

## Validação

- `P7ProjectHistoryInstrumentedTest`: URI sem grant, esquema `file:` indevido, deduplicação, entrada malformada, nomes com caracteres de controle, três linhas recentes visíveis e lista completa.
- `P7HomeOverviewInstrumentedTest`: estado vazio, projeto da sessão, arquivos reais e indicadores não contabilizados (builds/ameaças permanecem `—`).
- A matriz P7 roda também regressões de Import SAF, Explorer SQLite, Design Studio, temas e layout nos Android 10 (API29) e Android 15 (API35).

**Pendente antes da conclusão:** conferir resultado dos workflows no commit final, reabertura real de vários SAF documents num aparelho físico, screenshots com três projetos preenchidos e comparação com a arte de referência. A aparência completa 1:1, editores avançados e catálogo total seguem pendentes.
