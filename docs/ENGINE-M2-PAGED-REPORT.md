# NegrecoDroid | Motor M2.3: relatório paginado e catálogo completo

**Escopo:** reduzir alocações temporárias na análise de APK, sem modificar UI, assinatura, OTA ou `main`. Implementação empilhada sobre M2.2 e M1; ambas continuam com suas PRs em draft.

## Defeito identificado

Embora `ApkDiskIndex` já permitisse navegar em páginas de até 120 entradas, `ApkExplorer.inspect` ainda criava um `JSONArray` contendo **todas** as entradas e `JSONObject` por arquivo (até 150 mil). A Activity e `SecurityScanner` também retinham arrays variáveis de DEX, bibliotecas e caminhos. Para um APK hostil ou enorme, a análise poderia consumir RAM desnecessária, inclusive após a validação ZIP M2.1.

## Correção M2.3

- Prévia JSON do explorador limitada a 120 arquivos com `previewCount`, `previewTruncated` e `fileCount`/contagem total exata separados.
- `ApkExplorer.inspect(File)` valida o ZIP via `ApkArchiveSafety`; `inspectVerified` é usado somente após a porta de admissão do mesmo arquivo privado na Activity.
- `ApkIntelligence` recebe quatro indicadores booleanos calculados ao percorrer **todos** os caminhos e conserva a detecção de Unity/Unreal/Flutter/React Native mesmo quando o indício está após a prévia.
- Arrays JSON de classes DEX, bibliotecas nativas e scanner de segurança são limitados a 120 itens, com contadores totais separados.
- **Índice SQLite obrigatório** quando `entries > PREVIEW_LIMIT`. Se a indexação falhar, a candidata NÃO é aceita: a exceção retorna ao fluxo de recuperação transacional e `ApkDiskIndex.build` apaga o índice incompleto. Isso impede a antiga navegação parcial silenciosa.
- Resumo visível diferencia contagem total de lista JSON parcial; a busca completa permanece no índice SQLite.

## Validação

- Nova suíte `ApkReportBudgetInstrumentedTest`: arquivo com 243 itens e indicador Flutter após o limite, busca pelo último item via SQLite, limites das listas de segurança para 307 entradas, corrupção de CRC antes da prévia e falha de destino de índice mantendo arquivo fonte intacto.
- Contrato Python fixa limites, ordem da verificação e obrigatoriedade de indexação.
- Workflow M2 roda M2.1 + M2.2 + M2.3 no Android 10 (API 29) e 15 (API 35). A CI M1 também deve continuar verde no **commit final**.

## Limites honestos

- A prévia/relatório JSON têm tamanho previsível; **não é prova de memória total constante**. A admissão ZIP ainda retém um conjunto de nomes para detectar duplicados, a biblioteca ZIP e SQLite possuem seus próprios custos e `PackageManager` pode gerar análise de manifesto extensa.
- O conteúdo inteiro de cada arquivo é descomprimido durante M2.1, o que consome CPU/I/O, mesmo sem extrair no disco.
- Um SQLite de até 128 MiB pode ser insuficiente para um ZIP com muitos nomes complexos. Nesse caso a importação será recusada, não falsamente apresentada como completa.
- Arquivos com até 120 entradas ficam na prévia JSON e não precisam do índice; diretórios explícitos vazios podem depender de índice para navegação total, ainda a cobrir em uma fase de UX/retenção.
- O teto de importação de 1 GiB, o limite de 2 GiB inflados, cancelamento cooperativo e política de não distribuir APK instalável permanecem inalterados.

**Aceitação:** só concluir M2.3 após workflows M1, M2, Source checks e OTA passarem no SHA final. Não fazer merge automático nem alterar `main` ou publicar APK.
