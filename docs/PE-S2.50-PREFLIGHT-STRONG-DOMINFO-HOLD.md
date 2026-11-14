# PE-S2.50 | Alinhar o preflight do host S2.21 à captura S1.70 (HOLD)

## Problema confirmado por auditoria do código

O `reviewer_host_readiness()` do S2.21 reportava `LOCAL_PE_S2_21_READONLY_LIBVIRT_HOST_CANDIDATE_HOLD` para alguns resultados de `virsh` que o produtor S1.70 já rejeita como evidência inválida: `domstate` com grafia `RUNNING` ou `Running`, além de linhas `dominfo` não canônicas, disfarçadas por espaços, com rótulos duplicados (inclusive com maiúsculas diferentes) ou declarações `key=value` extras. O preflight aplicava `line.strip()` e `str.splitlines()` antes de conferir `Name/UUID/State`, além de comparações case-insensitive.

A inconsistência não cria autorização de release, mas podia fazer o revisor avançar com um host “candidato” cujo primeiro registro seria recusado na etapa seguinte, desperdiçando a sessão de coleta e enfraquecendo a clareza do parecer.

## Contrato corrigido

- O S2.21 agora chama **`host._validate_dominfo_shape()`**, função já usada pelo capturador S1.70 e pelo leitor S1.71, antes da checagem semântica dos campos. O preflight deixa de remover espaços de início de linha que escondiam identificadores disfarçados.
- O S2.21 exige `domstate == "running"` literalmente nas leituras anterior/posterior. A forma exata é a mesma exigida pelo S1.70, S1.71 e pelo S1.73 offline.
- Resultado de formato incompatível provoca `ReviewerHostReadinessError`, nunca `CANDIDATE`.
- A saída `CANDIDATE`, quando a resposta é coerente, continua sendo **HOLD** e não atestação. Nenhum comando mutável, arquivo de prova, assinatura, APK ou OTA foi adicionado.

## Testes

Cinco métodos novos em `tests/test_pe_arch_vm_s2_21_reviewer_host_readiness.py` cobrem asserções falsas, linhas indentadas, rótulos duplicados, estado com maiúsculas alteradas, saídas do `dominfo` mal formatadas, tipos errados, aceitação de campos normais estendidos e um teste que exige o compartilhamento da mesma função S1.70. Todos usam respostas `virsh` simuladas e conferem a ausência de arquivos na pasta `observer`.

A fixture do teste usa a mesma forma sem `LF` terminal que `host._virsh_read()` devolve depois de `.strip()`, evitando diferença artificial entre o mock e o retorno real do wrapper.

## Limites

Isso valida apenas a **consistência local dos contratos**. Nem uma resposta `CANDIDATE` nem testes verdes provam identidade e independência do revisor, procedência de host QEMU/libvirt, VM Arch com kernel próprio, Ghidra/seccomp/cgroup simultâneos, journald, cleanup ou cadeia BEFORE → WORK → AFTER.

A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) permanece o bloqueador externo. A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) fica Draft/unmerged. Sem release, APK, OTA ou execução de Windows PE desconhecido.
