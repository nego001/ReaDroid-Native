# NegrecoDroid — motor primeiro | M1: transação de rebuild confiável

**Decisão de produto (25/10/2026):** congelar modificações cosméticas P7. A prioridade de desenvolvimento passa a ser o motor de análise/edição de APK; aparência volta ao fim. A PR visual #13 continua em rascunho sem merge. Não lançar APK/OTA durante esta fase.

## Inventário real, não promessas

| Etapa | Implementação presente | Limite atual |
| --- | --- | --- |
| Entrada de APK | SAF e preflight de tamanho e espaço; cópia para cache | APK importado até o teto de 1 GiB; provedor externo pode errar tamanho |
| Exploração | Inventário ZIP, análise estática e índice SQLite paginado | Leitura de arquivos, não descompilação de recursos/DEX |
| Edição | Plano textual para `.json`, `.txt`, `.properties`, `.html`, `.css`, `.js`, `.md`, `.csv` | Não edita classes DEX, Smali, manifesto binário, recursos compilados |
| Exportação | Reconstrução experimental de ZIP APK com saída **sem assinatura**, gravação SAF, SHA-256 do original, resultado e leitura de volta | Não garante zipalign, assinatura v2/v3/v4 ou instalação |
| Recuperação | Cofre local criptografado e plano de alterações | Não garante recuperação de aplicativos de terceiros instalados |

## Defeito do motor tratado por M1

Antes, `ApkRebuilder.rebuild` verificava apenas se todas as entradas declaradas no plano foram encontradas e só então movia o ZIP temporário atomicamente para o destino. A verificação estrutural/criptográfica profunda ficava por conta de um **chamador posterior** (`MainActivity` usa `RebuildVerifier.verifyAgainstOriginal`). Isso permitia ao método de motor, usado diretamente, **substituir um arquivo anterior íntegro por um ZIP ainda não validado**. Além disso, a comparação de SHA-256 lia bytes do ZIP sem comparar o checksum CRC-32 armazenado no diretório central: `java.util.zip.ZipFile` não deve ser tratado como prova de CRC validado por si só.

### M1 implementada

1. A reconstrução só confirma o destino **depois** de executar `RebuildVerifier.verifyAgainstOriginal(original, staged, safeEdits)` na saída temporária. Assim, antes do movimento atômico, a transação valida a estrutura mínima APK (AndroidManifest.xml + classes*.dex), todas as entradas editadas, presença das entradas originais, ausência de assinatura v1 antiga, igualdade SHA-256 dos arquivos não editados e rejeição de entradas inesperadas.
2. `RebuildVerifier.entryDigest` agora também valida **CRC-32 da entrada vs o declarado no ZIP** e quantidade de bytes descomprimidos vs o tamanho declarado, além de SHA-256. Aplica-se tanto à origem quanto ao resultado para cada arquivo não editado.
3. Regressões Android reais rejeitam central directory com CRC manipulado, ZIP válido que **não é APK** e APK sem DEX; verificam que o arquivo anterior no destino sobrevive byte a byte à falha. Os testes existentes comprovam preservação do original, edição correta, exclusão da assinatura antiga, limite de 128 KiB, Unicode, interrupção e comparação completa.
4. Workflow dedicado `engine-m1-core-validation.yml`: roda `ApkRebuilderInstrumentedTest` no Android10/API29 e Android15/API35, e um terceiro job de ponta a ponta SAF no Android10: abrir fixture, alterar texto, reconstruir, conferir os demais arquivos e o SHA-256 exportado. Guarda **somente relatórios e capturas**, jamais APK/instalador de distribuição.

### Critério de aceitação

- Cada um dos três jobs do motor precisa concluir em verde no **SHA exato**, e o teste do fluxo SAF deve confirmar que o APK original não foi alterado.
- Não relaxar as verificações de CRC, SHA-256, atomicidade ou assinatura em caso de erro.
- `Source checks` da PR também devem passar.
- A verificação exige mais I/O (hash do original e do arquivo temporário), aceitável nesta fase de segurança, a medir antes de otimizar.
- Isto **não comprova instalabilidade**, decompilação, assinatura nem compatibilidade com todos os ZIP/APK do mundo. A validação real com o APK oficial de teste é distinta de modificar apps de terceiros.

## Próximas etapas do motor (planejadas, não prontas)

- **M2 Importação e análise:** testes com APKs grandes/corrompidos, limites contra ZIP bombs, diagnóstico de falhas determinísticas e relatórios de progresso.
- **M3 DEX/Manifesto/recursos:** leitores binários seguros e consultas navegáveis; somente depois considerar alterações profundas.
- **M4 Rebuild instalável:** alinhamento 4/16 KiB conforme bibliotecas, assinatura local moderna v2/v3, verificação `apksigner verify`, teste real de instalação e abertura em Android10/15.
- **M5 Robustez e recuperação:** cancelamento, consumo de RAM, projeto persistente, exportação e auditoria de integridade ponta a ponta.
- **Interface por último:** só depois das fases do motor e dos cenários reais validados; o projeto P7 não se torna versão final por estar visualmente próximo da referência.

**Política:** mudanças motor em branch/PR independente; manter PR #13 draft e `main` intacta; não gerar APK distribuível nem OTA por commits de engenharia. Sem declaração de 1:1, Galaxy A55 físico ou TalkBack como aprovados.
