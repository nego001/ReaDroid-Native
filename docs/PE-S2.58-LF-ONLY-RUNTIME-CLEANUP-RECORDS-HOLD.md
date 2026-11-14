# PE-S2.58 | Somente LF nos registros de runtime e cleanup (HOLD)

## Vulnerabilidade de integridade textual

`tools/pe_arch_vm_s2_13_runtime_log_chain.py` validava a estrutura dos registros de runtime e limpeza usando `raw.decode("ascii").splitlines()`. Em Python, `splitlines()` interpreta caracteres ASCII de controle como VT (0x0b), FF (0x0c), FS (0x1c), GS (0x1d) e RS (0x1e) como separadores de linha. Esses bytes **desapareciam antes** da validação de cada linha, de modo que um arquivo reescrito com separadores incompatíveis podia passar pela análise semântica caso o SHA-256 do runtime fosse atualizado dentro do registro de limpeza.

Esse problema está na análise **offline** de texto autorreportado. Não representa uma exploração do hipervisor nem torna a informação de origem falsa em uma medição confiável.

## Correção

- A parser S2.13 agora exige um LF final, remove **somente** esse LF e executa `split("\\n")` literal.
- Qualquer controle ASCII restante nos registros é rejeitado pelo filtro existente de caracteres imprimíveis (`ord(ch) >= 33`), inclusive VT/FF/FS/GS/RS inseridos no lugar do LF.
- SHA-256, session, scope, quotas, modo seccomp e status de limpeza continuam sob os mesmos requisitos fail-closed. Não há código de execução de PE nem modificação do ambiente do revisor.

## Regressões

Três novos testes S2.58: adulteração do runtime com **cinco separadores ASCII diferentes** seguida de recálculo da referência hash no cleanup; adulteração do cleanup sem modificar o runtime; controle positivo de dois arquivos exclusivamente LF ainda com resultado HOLD. As entradas são sintéticas, não derivadas de uma VM real.

## Regresso de mensagens da primeira CI

A primeira execução da CI rejeitou corretamente os bytes adulterados, mas antes do filtro de caracteres passou pelo teste de número de campos e produziu `Incomplete or extra runtime observation fields`. A rotina passou a **testar primeiro os caracteres de controle**, retornando `Noncanonical runtime observation line`. Não foi relaxada a aceitação de nenhuma linha. O teste continua verificando a classificação específica do byte de controle.

## Limites de homologação

[PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) Draft/unmerged. [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) OPEN. A CI não mede host QEMU/libvirt independente, guest Arch nativo, PID de Ghidra, seccomp+cgroup v2 simultâneos, journald real, cleanup ou cadeia BEFORE → WORK → AFTER com testemunho externo. Não executar PE desconhecido, fazer merge ou publicar APK/OTA/release.
