# PE-S2.14 | Identificador de sessão escolhido fora da VM (HOLD)

**Estado:** correção de integridade na revisão offline. Não foi executado um guest Arch independente; nenhuma publicação de APK/OTA ou merge está autorizada.

## Falha identificada na PE-S2.13

A revisão correlacionava os dois logs de runtime e cleanup pelo campo `session_id`, mas esse campo era extraído **somente dos arquivos apresentados pelo operador/observador**. Dois logs de uma sessão antiga podiam ser reapresentados com todos os hashes refeitos e uma nova assinatura, enquanto o validador apenas verificava que os IDs internos coincidiam.

## Gate da PE-S2.14

O revisor deve fornecer por canal separado e **antes da coleta** um novo ID de 64 dígitos hexadecimais minúsculos, não nulo, **diferente do desafio e dos hashes de arquivos** e reservado para uma única sessão. Esse parâmetro obrigatório `--expected-session-id` é exigido tanto pelo preparador S1.65 (antes de criar manifesto) quanto pela revisão agregada S1.64 (após conferir as assinaturas). `pe_arch_vm_s2_13_runtime_log_chain.py` compara os dois logs com o ID externo, além de SHA, desafio, domínio/UUID, hash de runtime e escopo.

O campo não é uma assinatura, não deve ser calculado a partir de bytes dos logs e NÃO é um sensor independente. Esta alteração não muda o esquema de recibo local v2 nem o manifesto externo v1, porque o valor já aparece dentro dos dois logs que são amarrados à assinatura do manifesto por SHA256. Trata-se de uma exigência adicional de **pin externo**, não de autoridade sobre o kernel.

## Verificações

Regressões impedem ID errado, zero, maiúsculas, truncado, duas observações coerentes de outra sessão com hash atualizado, manifesto pré-assinatura indevido e aceitação de um pacote realmente assinado sob o ID externo incorreto. As execuções de teste usam chaves descartáveis e dados sintéticos.

**Permanece HOLD:** sem confirmação independente do hipervisor, sem journald com cota de kernel observada por sensor externo, sem execução cgroup+seccomp autenticada no Arch nativo, sem análise de PE desconhecido, sem merge, APK ou OTA.
