# PE-S2.63 | Antes/depois: relógio local autorreportado em ordem crescente (HOLD)

## Desvio verificável

O coletor S2.17 e o revisor offline correlacionam os registros BEFORE/AFTER por domínio/UUID, nonce de sessão, hashes externos e `cpu.time` crescente. Até esta etapa, **não comparavam** `host_time_utc_untrusted` entre as duas amostras. Assim, um arquivo AFTER canonizado novamente, com `cpu.time` maior e data UTC **igual ou anterior** à do BEFORE, podia passar pelo revisor offline se seus hashes fossem repinados; o manifesto V3 podia continuar sendo preparado mesmo com a contradição temporal interna.

Não confundir isto com prova de tempo externo: esse relógio é **não atestado**, pode mentir ou sofrer ajustes NTP. Uma sequência crescente é requisito de coerência local, nunca testemunho independente de execução nem prova do PID Ghidra.

## Correção

- `S2.17._check_reported_chronology()` compara timestamps UTC **somente depois** de ambos serem autenticados quanto a formato e de seus demais campos passarem em `_decode`.
- `capture_phase("after")` recusa publicar o arquivo se o horário local registrado for anterior ou igual ao do BEFORE. O controle é adicional ao aumento de CPU, sem criar novos comandos libvirt/guest.
- `review_pair()` reaplica a mesma regra para barrar arquivos adulterados mesmo com hashes externos recalculados. O V3 volta a exigir a revisão positiva do par antes de publicar manifesto.
- Não se atribui ao relógio a capacidade de comprovar a execução real do trabalho. Se houver ajuste legítimo de relógio para trás, a sessão deve ser revisada/refeita pelo responsável externo; não há normalização ou correção automática das evidências.

## Regressões

Três testes adversariais com dados sintéticos: tentativa de captura AFTER com relógio igual ou retrocedido, recusada antes de publicar; releitura offline com horário igual/anterior e hash AFTER recalculado, recusada enquanto o par original continua HOLD; preparação do manifesto V3 com AFTER rehashado em data igual ao BEFORE, recusada antes da criação do manifesto e de assinatura. Mantidos os testes anteriores de aumento de CPU e correlação de hashes.

## Bloqueio externo

PR #47 continua Draft/unmerged, Issue #48 OPEN. Nenhum desses testes prova controle de host QEMU/libvirt por terceiro, VM Arch nativa, PID Ghidra com cgroup v2+seccomp simultâneos, journald, cleanup ou cronologia BEFORE → WORK → AFTER **testemunhada de forma independente**. Sem PE desconhecido, merge, APK, OTA ou release.
