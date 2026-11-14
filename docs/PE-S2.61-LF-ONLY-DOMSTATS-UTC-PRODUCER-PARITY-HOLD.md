# PE-S2.61 | LF literal e formato UTC do produtor nos registros host domstats (HOLD)

## Divergência entre captura e revisão

A captura S2.15 usa `host._checked_text()`, que rejeita caracteres de controle e devolve apenas texto `virsh domstats` imprimível com delimitador LF. Entretanto, o leitor offline `review_host_domstats()` e o parser `_stats()` usavam `splitlines()`, que reconhece VT (0x0b), FF (0x0c), FS (0x1c), GS (0x1d) e RS (0x1e) como separadores e os descarta. Um arquivo offline adulterado com um destes separadores, novamente hashado e assinado por quem detenha a chave de assinatura, podia conservar a interpretação de domstats sem reproduzir bytes aceitos pela captura real.

Além disso, a captura de S2.15 e S2.17 grava `datetime.now(timezone.utc).isoformat()`. Os revisores aceitavam aliases de `datetime.fromisoformat()` (`Z`, espaço, semana ISO, precisão abreviada) que o produtor não gera, ao contrário das regras já alinhadas no S1.70.

## Correções de contrato

- `S2.15._stats()` passa a usar `split("\\n")` literal, com caracteres ASCII imprimíveis e ausência de separadores de controle ou delimitadores extras. Vale também para o texto `domstats_raw` assinado dentro do JSON S2.17.
- `S2.15.review_host_domstats()` exige sidecar ASCII imprimível, exatamente um LF final, linhas não vazias e `split("\\n")` literal; bytes como VT/FF/FS/GS/RS são recusados mesmo que o SHA256 do sidecar seja novamente calculado.
- S2.15 e S2.17 reaproveitam `host._validate_untrusted_utc_isoformat()` para datas UTC não atestadas em formato **idêntico** ao produtor, sem transformar o horário em atestado confiável.
- Todas as assinaturas, pins, diretórios privados, controle de não overwrite e estados de resultado HOLD permanecem intactos.

## Testes

Cinco novos métodos S2.61:
1. Sidecar S2.15 com cinco separadores ASCII falsos no lugar de LF, repinnado, rejeitado; sidecar original preserva HOLD.
2. Parser `_stats()` rejeita os cinco separadores inválidos antes de interpretar campos.
3. Cinco aliases UTC repinnados no S2.15 são recusados.
4. Cinco timestamps alternativos em amostras BEFORE de S2.17, com JSON canônico recalculado, são recusados.
5. S2.17 rejeita separadores de controle ocultos no `domstats_raw`, mesmo com JSON/horário/assinatura sintaticamente válidos.

## Limitações

A evidência é texto autorreportado. O código não ativa uma VM nem contata um hipervisor durante testes offline. A PR #47 permanece Draft/unmerged e a Issue #48 continua OPEN. Antes de liberar qualquer PE Windows desconhecido, merge, APK, OTA ou release, são exigidos um revisor realmente independente, host QEMU/libvirt sob controle externo, guest Arch nativo, PID real do Ghidra sob cgroup v2 e seccomp, journald, limpeza e cronologia BEFORE → WORK → AFTER testemunhada.
