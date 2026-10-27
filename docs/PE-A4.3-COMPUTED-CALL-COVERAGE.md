# NegrescoDroid PE-A4.3 | Cobertura e chamadas indiretas sem inventar destinos

## Alterações implementadas

Esta etapa aumenta, de forma limitada, a recuperação de evidências sobre funções PE32/PE32+ por Ghidra Headless. Examina até **512 funções** e seleciona até **16** para uma prévia de pseudocódigo e contexto, mantendo as cotas existentes de 24 chamadas diretas, 8 referências WinAPI, 8 strings de até 96 caracteres e 1.800 caracteres de pseudocódigo por função.

### Chamadas calculadas

O Ghidra identifica instruções cujo `FlowType` é simultaneamente `isCall()` e `isComputed()`. Cada ocorrência é registrada **somente com endereço da instrução**, sem indicar o nome da função chamada. A documentação Java oficial distingue computed CALL de chamadas com alvo conhecido: https://ghidra.re/ghidra_docs/api/ghidra/program/model/symbol/FlowType.html.

- O scanner é limitado a **2.048 instruções por função**, compartilhando o orçamento da extração de strings.
- Exporta até **8 endereços** de chamadas calculadas por função, com `computed_call_count` observado dentro da amostra e `computed_calls_truncated` quando exceder o orçamento.
- Declara sempre `computed_call_destinations=not_inferred`. Um alvo eventual resolvido pelo decompilador não é automaticamente afirmado por esta etapa.
- Os campos são validados pelo Python (endereços em hexadecimal, cotas, tipos, duplicatas, consistência entre contagem e truncamento), e aparecem no classificador como `indirect_call_context`. **Não geram hipóteses de comportamento nem simulam a execução.**
- A janela de instruções pode ficar incompleta; a flag `string_scan_truncated` documenta esse limite compartilhado. Nem toda chamada indireta ou tabela virtual será encontrada.

### Comprovação sintética exigida na CI

A fixture C compilada em PE sintético inclui uma chamada através de ponteiro de função `volatile` dentro de `inspect_path` e mantém a API não destrutiva `GetFileAttributesA("negresco_evidence_2026.txt")`. O gate com Ghidra 12.2/JDK25 exige: (1) pseudocódigo, (2) a referência a `GetFileAttributesA`, (3) a string ligada à função correta e (4) ao menos um **computed call site** no corpo de `inspect_path`.

Se a chamada indireta não for reconhecida no binário sintético, o workflow precisa falhar. O Ghidra roda sobre bytes do PE, mas o executável Windows não é iniciado. A opção sem Bubblewrap é utilizada na CI somente com a fixture confiável.

## Limitações e segurança

- Ampliar de 384/12 para 512/16 não significa recuperar todas as funções ou cobrir 100% do executável.
- `computed_call_sites` atesta uma chamada calculada no fluxo estático da função, **não seu destino, intenção ou execução real**. Referências indiretas sem resolução permanecem desconhecidas.
- O classificador ainda é um conjunto de **regras determinísticas locais**, não um LLM. Nomes e strings sugestivas isoladas não sustentam classificação de funcionalidade.
- Ghidra processa entradas potencialmente perigosas; o perfil Bubblewrap ainda carece de teste funcional de isolamento em kernel real. Até lá, usar VM descartável para arquivos desconhecidos.
- Não houve análise do IObit Uninstaller real. A interface Android/PC de um clique ainda não está implementada.

PR em rascunho sobre a PE-A4.2 (#44), sem merge na `main`, sem APK ou OTA publicado.