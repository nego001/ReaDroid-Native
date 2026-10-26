# NegrescoDroid | PE-A4: identificação automática baseada em evidências

## Objetivo e estado real

Após importar um PE e obter o pseudocódigo limitado da PE-A3.1, o motor passa a produzir **hipóteses locais, sem intervenção manual**, sobre operações sugeridas pelas funções. Esta primeira versão é um conjunto **determinístico de regras offline**, não é um modelo de IA generativa, não reconstrói o código original nem identifica 100% das rotinas de um programa.

## Como o motor decide

- O componente `tools/pe_auto_behavior.py` procura **chamadas com sintaxe de invocação** a APIs Windows reconhecidas **no corpo do pseudocódigo Ghidra recuperado**, removendo comentários, literais de string e declarações de função, para minimizar falsos positivos.
- Distingue consulta de arquivos, modificação de arquivos, consulta de Registro, modificação de Registro, gerenciamento de serviços, processos, rede e gestão de pacotes MSI.
- A tabela de imports PE-A1, quando pode ser lida, é **somente corroborativa**. Um import isolado não prova que a função o chama; nome de função como `UninstallEverything` também não é evidência suficiente.
- Produz no máximo 3 hipóteses por função e 4 evidências de chamada por hipótese. Cada hipótese contém categoria, explicação limitada, chamadas observadas, se o nome aparece na tabela de imports e confiança qualitativa `baixa`/`moderada`. Não declara confiança alta nesta fase.
- Se a decompilação não produzir pseudocódigo, se não encontrar chamadas reconhecidas ou se as evidências forem insuficientes, o resultado é **`unidentified`**. Dados malformados são rejeitados e não geram uma funcionalidade inventada.
- Mesmo quando encontra `RegDeleteKeyW` ou `DeleteFileW`, o relatório não afirma que o programa realmente apagou uma chave/arquivo: a chamada pode estar em um caminho não executado, com argumentos diferentes ou ser somente um stub.

## Integração automática

`tools/pe_auto_ghidra.py` gera `behavior_preview` automaticamente sempre que a análise profunda (`--deep-preview`) está habilitada; também registra `behavior_import_context=available` ou `unreadable_or_unsupported`. A análise não exige um operador para atribuir rótulos. Se a leitura de imports não estiver disponível, o classificador ainda pode emitir hipóteses baixas com base em chamadas explícitas do pseudocódigo.

A CI Ghidra real 12.2/JDK 25 usa apenas PE sintético, testa a integridade do relatório e preserva todas as suítes PE-A0/A1/A2/A3. A suíte PE-A4 inclui regressões para nomes enganadores, importações isoladas, textos em comentários, strings, assinaturas sem corpo, contagens falsificadas, decompilação indisponível, limites e confiança.

## Limites e privacidade

- **Sem upload para nuvem** e sem execução de software Windows. O analisador Ghidra ainda deve executar em ambiente isolado; o perfil Bubblewrap de Linux não tem validação funcional completa e binários hostis exigem VM descartável.
- O classificador só vê até **12 funções** decompiladas, com pseudocódigo de até **1.800 caracteres** por função. Não identifica rotinas escondidas fora da amostra nem conteúdo de instaladores empacotados.
- Não apresenta o IObit Uninstaller como já analisado: a integração usa executável PE criado pela própria CI.
- O sistema pode apresentar funcionalidades prováveis, mas **não garante identificação completa ou nomes reais**, especialmente diante de ofuscação, otimizações, despacho indireto e APIs resolvidas dinamicamente.
- A interface Android/PC de um clique e um modelo opcional de IA local, com avaliações de precisão antes de uso, continuam fora desta fase.

## Próximo passo

Expandir a recuperação de evidências incluindo imports externos ligados a cada função, strings referenciadas com limites e explicações com citações de trechos específicos do pseudocódigo. Depois avaliar cobertura, taxa de falsos positivos e interface sem trabalho manual.

PR em rascunho, sem merge na `main` e sem publicações de APK/OTA.